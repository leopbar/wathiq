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
class LineBox:
    """Where one line sits on its page, and how sure the engine was of it.

    `bbox` is normalised `[x, y, w, h]` in 0..1, so the UI can overlay it on a render of any
    size — which is the form `ExtractedField.bbox` has stored since M1 and the form
    `DocumentViewer.tsx` already draws. Only an engine that reports geometry fills this in.
    """

    text: str
    page: int
    bbox: list[float]
    confidence: float | None = None

    def as_dict(self) -> dict[str, object]:
        """Plain JSON: this travels through the LangGraph state and gets checkpointed."""
        return {
            "text": self.text,
            "page": self.page,
            "bbox": self.bbox,
            "confidence": self.confidence,
        }


@dataclass(slots=True)
class OcrResult:
    text: str
    confidence: float
    page_count: int
    language: str = "en"
    lines: list[str] = field(default_factory=list)
    engine: str = "demo"
    # Geometry, when the engine reports it. Empty for the demo reader: a PDF text layer has
    # no per-line confidence, and inventing coordinates for it would put a highlight box on a
    # reviewer's screen that nothing measured. The UI keeps saying "no source region" instead.
    line_boxes: list[LineBox] = field(default_factory=list)

    @property
    def has_geometry(self) -> bool:
        return bool(self.line_boxes)


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
    """The OCR backend this deployment is configured for.

    Document Intelligence only when its own endpoint is set, which is what makes
    `WATHIQ_MODE=azure` with no OCR endpoint a legitimate state rather than a broken one. The
    import is inside the branch so demo mode never loads an Azure SDK.
    """
    global _backend
    if _backend is None:
        from app.core.config import settings

        if settings.doc_intelligence_enabled:
            from app.azure.doc_intelligence import DocumentIntelligenceOcr

            _backend = DocumentIntelligenceOcr()
        else:
            _backend = DemoOcr()
    return _backend


def reset_ocr() -> None:
    """Drop the cached backend so a test can change the settings and pick a different one."""
    global _backend
    _backend = None


def ocr_label() -> str:
    return get_ocr().label


__all__ = [
    "DemoOcr",
    "LineBox",
    "OcrBackend",
    "OcrResult",
    "get_ocr",
    "ocr_label",
    "reset_ocr",
]
