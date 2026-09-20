"""OCR behind one interface.

DEMO mode reads the text layer that is already inside the PDF. AZURE mode (M6) calls Document
Intelligence. Callers only see `OcrBackend`, so swapping is a settings change, exactly like
storage.

Honesty note: the demo backend does not do real optical character recognition. It reads text
that is already in the file. For a scanned image it returns nothing and says so, rather than
inventing content. The UI labels this "demo OCR".
"""

from __future__ import annotations

import io
import re
import zlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from pypdf import PdfReader

# `(some text) Tj` — the PDF operator that draws a string.
_TJ = re.compile(rb"\((?:[^()\\]|\\.)*\)\s*Tj")
_STREAM = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)


@dataclass(slots=True)
class OcrResult:
    text: str
    confidence: float
    page_count: int
    language: str = "en"
    lines: list[str] = field(default_factory=list)
    engine: str = "demo"


def _decode_stream(raw: bytes) -> bytes:
    """Streams may be Flate-compressed; ours are not, but real PDFs often are."""
    try:
        return zlib.decompress(raw)
    except zlib.error:
        return raw


def _extract_pdf_lines(data: bytes) -> list[str]:
    lines: list[str] = []
    for match in _STREAM.finditer(data):
        content = _decode_stream(match.group(1))
        for token in _TJ.finditer(content):
            literal = token.group(0)
            literal = literal[literal.index(b"(") + 1 : literal.rindex(b")")]
            # Undo the three escapes `services/pdf.py` writes. Backslash last, so an escaped
            # backslash does not turn the next character into an escape of its own.
            literal = literal.replace(rb"\(", b"(").replace(rb"\)", b")")
            literal = literal.replace(rb"\\", b"\\")
            text = literal.decode("latin-1", errors="replace").strip()
            if text:
                lines.append(text)
    return lines


class OcrBackend(ABC):
    @abstractmethod
    def read(self, data: bytes, mime_type: str) -> OcrResult: ...

    @property
    @abstractmethod
    def label(self) -> str:
        """How this backend is described in the UI, honestly."""


class DemoOcr(OcrBackend):
    """Reads the PDF text layer. No network, no model, fully deterministic."""

    def read(self, data: bytes, mime_type: str) -> OcrResult:
        if mime_type == "application/pdf" or data[:5] == b"%PDF-":
            try:
                reader = PdfReader(io.BytesIO(data))
                lines = [
                    line.strip()
                    for page in reader.pages
                    for line in (page.extract_text() or "").splitlines()
                    if line.strip()
                ]
                pages = len(reader.pages)
            except Exception:
                # Malformed uploads must fail closed, never invent a text layer.
                lines, pages = [], 1
            if lines:
                # A text layer is read exactly, so confidence is high but not a fake 1.0.
                return OcrResult(
                    text="\n".join(lines),
                    confidence=0.97,
                    page_count=pages,
                    lines=lines,
                    engine="demo-text-layer",
                )
            return OcrResult(
                text="",
                confidence=0.0,
                page_count=pages,
                lines=[],
                engine="demo-no-text-layer",
            )
        # Images would need real OCR. Say so instead of pretending.
        return OcrResult(text="", confidence=0.0, page_count=1, lines=[], engine="demo-unsupported")

    @property
    def label(self) -> str:
        return "Demo OCR (reads the PDF text layer)"


_backend: OcrBackend | None = None


def get_ocr() -> OcrBackend:
    global _backend
    if _backend is None:
        # AZURE mode plugs DocumentIntelligenceOcr here in M6 — same interface.
        _backend = DemoOcr()
    return _backend


def ocr_label() -> str:
    return get_ocr().label


__all__ = ["DemoOcr", "OcrBackend", "OcrResult", "get_ocr", "ocr_label"]
