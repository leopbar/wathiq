"""Document Intelligence: real OCR, with geometry.

This is the adapter the case screen has been waiting for since M2. The demo reader can only
pull out text that is already inside a PDF, and it has no idea *where* on the page anything
sat — which is why every field says "no source region". Document Intelligence reads the pixels
and returns, for every word, a polygon and a confidence. That gives the two things M6 adds:

* **a highlight box** for each field, so a reviewer can see the value on the page instead of
  hunting for it;
* **a per-value read confidence**, which becomes the sixth signal in `agent/confidence.py`.

Why `prebuilt-layout` rather than `prebuilt-document`: the field schema is ours, it is
versioned per document type, and the rule packs are written against its field names. Letting
the service guess key-value pairs would put an unversioned second schema in the middle of
that. We ask for words, lines and geometry, and keep our own mapping. (DECISIONS #65)

Failure is an error, not a fallback. If Document Intelligence is configured and then returns
500, this raises. Quietly dropping back to the demo reader would produce a case that looks
normal, carries confident-looking numbers, and was read by something nobody chose.
(DECISIONS #64)
"""

from __future__ import annotations

import logging
from typing import Any

from app.agent.ocr import LineBox, OcrBackend, OcrResult
from app.azure.credentials import credential_for, describe_credential, require_sdk
from app.core.config import settings

logger = logging.getLogger(__name__)

# Below this, the engine is telling us it could not really read the page. We pass the number
# through rather than deciding here: the confidence signals and the review thresholds are the
# place where "too low" is defined, and they are configurable.
_MIN_REPORTED_CONFIDENCE = 0.0


def _normalise_polygon(
    polygon: list[float], page_width: float, page_height: float
) -> list[float] | None:
    """Turn Document Intelligence's polygon into the `[x, y, w, h]` the UI already draws.

    The service returns eight numbers — four corners, clockwise from top-left — in the page's
    own unit (inches for a PDF, pixels for an image). The viewer overlays a box on a render of
    unknown size, so it needs fractions of the page, not inches. We take the axis-aligned
    bounding box of the four corners, which is what a highlight rectangle is.
    """
    if not polygon or len(polygon) < 8 or page_width <= 0 or page_height <= 0:
        return None
    xs = polygon[0::2]
    ys = polygon[1::2]
    left, right = min(xs), max(xs)
    top, bottom = min(ys), max(ys)

    x = left / page_width
    y = top / page_height
    w = (right - left) / page_width
    h = (bottom - top) / page_height

    # Clamp: a polygon may sit a hair outside the page box, and a negative width would draw
    # an inverted rectangle over the viewer.
    x = max(0.0, min(1.0, x))
    y = max(0.0, min(1.0, y))
    w = max(0.0, min(1.0 - x, w))
    h = max(0.0, min(1.0 - y, h))
    if w <= 0 or h <= 0:
        return None
    return [round(x, 5), round(y, 5), round(w, 5), round(h, 5)]


def _span_offset(item: Any) -> tuple[int, int] | None:
    """The `(offset, length)` of an item's first span, across SDK shapes."""
    spans = getattr(item, "spans", None) or []
    if not spans:
        span = getattr(item, "span", None)
        if span is None:
            return None
        spans = [span]
    first = spans[0]
    offset = getattr(first, "offset", None)
    length = getattr(first, "length", None)
    if offset is None:
        return None
    return int(offset), int(length or 0)


def _line_confidence(line: Any, words: list[Any]) -> float | None:
    """Average the confidence of the words that fall inside this line's span.

    Document Intelligence reports confidence per *word*, not per line. A line is only as
    trustworthy as its least certain word, but a single low word in a long line should not
    condemn the whole thing, so we average and let the weakest-signal display do the rest.
    """
    bounds = _span_offset(line)
    if bounds is None:
        return None
    start, length = bounds
    end = start + length

    scores: list[float] = []
    for word in words:
        word_bounds = _span_offset(word)
        confidence = getattr(word, "confidence", None)
        if word_bounds is None or confidence is None:
            continue
        if start <= word_bounds[0] < end:
            scores.append(float(confidence))
    if not scores:
        return None
    return round(sum(scores) / len(scores), 4)


class DocumentIntelligenceOcr(OcrBackend):
    """`OcrBackend` implemented by Azure AI Document Intelligence."""

    def __init__(self) -> None:
        if not settings.azure_doc_intelligence_endpoint.strip():
            raise ValueError("Document Intelligence endpoint is not configured")
        self._model = settings.azure_doc_intelligence_model
        self._endpoint = settings.azure_doc_intelligence_endpoint.strip()
        self._key = settings.azure_doc_intelligence_key
        self._client: Any | None = None

    def _get_client(self) -> Any:
        """Built on first use, then reused: the client holds a connection pool."""
        if self._client is None:
            module = require_sdk("azure.ai.documentintelligence", "Document Intelligence")
            self._client = module.DocumentIntelligenceClient(
                endpoint=self._endpoint,
                credential=credential_for(self._key, "Document Intelligence"),
            )
        return self._client

    def read(self, data: bytes, mime_type: str) -> OcrResult:
        client = self._get_client()
        models = require_sdk("azure.ai.documentintelligence.models", "Document Intelligence")

        request = models.AnalyzeDocumentRequest(bytes_source=data)
        poller = client.begin_analyze_document(self._model, request)
        result = poller.result()

        lines: list[str] = []
        boxes: list[LineBox] = []
        page_scores: list[float] = []

        for page_number, page in enumerate(getattr(result, "pages", None) or [], start=1):
            width = float(getattr(page, "width", 0) or 0)
            height = float(getattr(page, "height", 0) or 0)
            words = list(getattr(page, "words", None) or [])
            page_scores.extend(
                float(word.confidence)
                for word in words
                if getattr(word, "confidence", None) is not None
            )

            for line in getattr(page, "lines", None) or []:
                text = (getattr(line, "content", "") or "").strip()
                if not text:
                    continue
                lines.append(text)
                bbox = _normalise_polygon(
                    list(getattr(line, "polygon", None) or []), width, height
                )
                if bbox is None:
                    # A line with no usable geometry is still text; it simply cannot be
                    # highlighted. Recording it without a box is more honest than dropping it.
                    continue
                boxes.append(
                    LineBox(
                        text=text,
                        page=int(getattr(page, "page_number", page_number) or page_number),
                        bbox=bbox,
                        confidence=_line_confidence(line, words),
                    )
                )

        # The page-level number is the mean word confidence the service actually reported. We
        # do not invent one: a document with no words scores zero and goes to a person.
        confidence = (
            round(sum(page_scores) / len(page_scores), 4)
            if page_scores
            else _MIN_REPORTED_CONFIDENCE
        )
        page_count = len(getattr(result, "pages", None) or []) or 1
        text = getattr(result, "content", None) or "\n".join(lines)

        logger.info(
            "doc_intelligence: read %d page(s), %d line(s), %d with geometry, confidence %.3f",
            page_count,
            len(lines),
            len(boxes),
            confidence,
        )
        return OcrResult(
            text=text,
            confidence=confidence,
            page_count=page_count,
            lines=lines,
            engine=f"azure-document-intelligence:{self._model}",
            line_boxes=boxes,
        )

    @property
    def label(self) -> str:
        auth = describe_credential(self._key)
        return f"Azure Document Intelligence ({self._model}, {auth})"


__all__ = ["DocumentIntelligenceOcr", "_normalise_polygon"]
