"""MCP server: document store (READ ONLY).

This one is not simulated — it serves the real uploaded documents. What makes it interesting
is what it *cannot* do: the storage volume is mounted read-only into this container, and the
server exposes no tool that writes. If the agent is ever talked into trying to alter a
customer's document, there is nothing on the other end that could carry it out.

The investigator uses it to go back to the source: "the extractor says the expiry is
2026-03-01 — is that string actually on the page?" Answering that from the document itself,
rather than from the extractor's own output, is what makes the check worth anything.

Path safety: every request is resolved inside the storage root, and anything that escapes it
is refused. A tool that takes a path from a model has to assume the path is hostile.
"""

from __future__ import annotations

import os
import re
import zlib
from pathlib import Path
from typing import Any

from wathiq_mcp.runtime import build_server, serve

DEFAULT_PORT = 9101
STORAGE_ROOT = Path(os.environ.get("WATHIQ_STORAGE_DIR", "/storage")).resolve()

# `(text) Tj` — the PDF operator that draws a string. Same reader as the API's demo OCR: this
# is a text-layer extractor, not optical character recognition, and it says so.
_TJ = re.compile(rb"\((?:[^()\\]|\\.)*\)\s*Tj")
_STREAM = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)

MAX_BYTES = 8 * 1024 * 1024

server = build_server(
    name="wathiq-document-store",
    title="Document store (read only)",
    instructions=(
        "Read the text of an uploaded document, or list the documents of a case. There is no "
        "tool that writes, and the underlying volume is mounted read-only."
    ),
)


def _safe_path(relative: str) -> Path | None:
    """Resolve inside the storage root, or refuse."""
    if "\x00" in relative:
        return None
    candidate = (STORAGE_ROOT / relative.lstrip("/\\")).resolve()
    if candidate == STORAGE_ROOT or STORAGE_ROOT in candidate.parents:
        return candidate
    return None


def _pdf_lines(data: bytes) -> list[str]:
    lines: list[str] = []
    for match in _STREAM.finditer(data):
        raw = match.group(1)
        try:
            content = zlib.decompress(raw)
        except zlib.error:
            content = raw
        for token in _TJ.finditer(content):
            literal = token.group(0)
            literal = literal[literal.index(b"(") + 1 : literal.rindex(b")")]
            literal = literal.replace(rb"\(", b"(").replace(rb"\)", b")").replace(rb"\\", b"\\")
            text = literal.decode("latin-1", errors="replace").strip()
            if text:
                lines.append(text)
    return lines


@server.tool(
    title="List the documents stored for a case",
    description="Returns the relative paths of every file stored under a case id.",
)
def list_case_documents(case_id: str) -> dict[str, Any]:
    folder = _safe_path(case_id)
    if folder is None or not folder.is_dir():
        return {"case_id": case_id, "found": False, "documents": []}
    documents = [
        {
            "path": str(path.relative_to(STORAGE_ROOT)).replace("\\", "/"),
            "filename": path.name,
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(folder.iterdir())
        if path.is_file()
    ]
    return {"case_id": case_id, "found": True, "count": len(documents), "documents": documents}


@server.tool(
    title="Read a document's text",
    description=(
        "Returns the text layer of a stored PDF. This is not OCR: a scanned image has no text "
        "layer and the tool says so rather than inventing content."
    ),
)
def read_document(path: str, max_lines: int = 400) -> dict[str, Any]:
    resolved = _safe_path(path)
    if resolved is None:
        return {"found": False, "error": "path outside the storage root", "path": path}
    if not resolved.is_file():
        return {"found": False, "error": "no such document", "path": path}
    if resolved.stat().st_size > MAX_BYTES:
        return {"found": False, "error": "document too large to read", "path": path}

    data = resolved.read_bytes()
    if data[:5] != b"%PDF-":
        return {
            "found": True,
            "path": path,
            "readable": False,
            "note": "Not a PDF; this store only reads PDF text layers.",
            "lines": [],
        }

    lines = _pdf_lines(data)[: max(1, min(max_lines, 2000))]
    return {
        "found": True,
        "path": path,
        "readable": bool(lines),
        "line_count": len(lines),
        "lines": lines,
        "text": "\n".join(lines),
        "note": (
            "Text layer, not OCR." if lines else "No text layer — this looks like a scan."
        ),
    }


@server.tool(
    title="Check whether a value appears in a document",
    description=(
        "Answers the grounding question directly: is this exact string on the page? Used to "
        "verify an extracted value against the source rather than trusting the extractor."
    ),
)
def find_in_document(path: str, value: str) -> dict[str, Any]:
    document = read_document(path)
    if not document.get("found") or not document.get("readable"):
        return {"checked": False, "reason": document.get("error") or document.get("note")}

    needle = " ".join(value.lower().split())
    lines: list[str] = document["lines"]
    for index, line in enumerate(lines):
        if needle and needle in " ".join(line.lower().split()):
            return {
                "checked": True,
                "found": True,
                "line_number": index + 1,
                "line": line,
                "context": lines[max(0, index - 1) : index + 2],
            }
    return {"checked": True, "found": False, "searched_lines": len(lines)}


if __name__ == "__main__":  # pragma: no cover - container entry point
    serve(server, DEFAULT_PORT)
