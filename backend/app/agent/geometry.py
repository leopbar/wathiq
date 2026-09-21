"""Finding where on the page a field's value was printed.

Document Intelligence gives us a box per *line*. A field is a *value*. This module is the
join between them, and it deliberately matches on **text, not on line numbers**.

Line numbers would be the obvious approach and they would be wrong. Between the OCR and the
extractor the text passes through the guardrails, which strip invisible characters, bidi
overrides and markup — so the extractor's line 7 is not reliably the OCR's line 7. Matching on
the text itself survives that, and survives the extractor re-splitting the text as well.

What it must never do is guess. A highlight box on a reviewer's screen is a claim: "the value
is here". If we cannot find the value, the field keeps `bbox = None` and the UI goes on saying
"no source region", which is what it has said honestly since M2.
"""

from __future__ import annotations

import re
from typing import Any

_WHITESPACE = re.compile(r"\s+")
# Below this length a line is too generic to match a value against — "AED", "1", "Ltd" would
# hit the wrong line on most pages.
_MIN_FRAGMENT = 4


def _normalise(text: str) -> str:
    return _WHITESPACE.sub(" ", text or "").strip().lower()


def _union(boxes: list[list[float]]) -> list[float]:
    """The smallest rectangle covering all of them — for a value split across lines."""
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[0] + box[2] for box in boxes)
    bottom = max(box[1] + box[3] for box in boxes)
    return [round(left, 5), round(top, 5), round(right - left, 5), round(bottom - top, 5)]


def locate(
    value: str | None,
    line_boxes: list[dict[str, Any]],
    *,
    label: str | None = None,
) -> tuple[list[float] | None, int | None]:
    """Where this value sits, as `(bbox, page)`.

    Tried in order, most specific first:

    1. a line whose whole text **is** the value — the usual case, since the documents print a
       value on its own line;
    2. a line that **contains** the value, for a value printed inline after its label;
    3. several lines that together make up the value, unioned into one box — a long company
       name wrapped across two lines;
    4. the line **after the label**, when the value itself cannot be found but its label can;
    5. nothing — and then the field honestly has no source region.
    """
    if not line_boxes:
        return None, None

    needle = _normalise(value) if value else ""
    if needle:
        # 1 and 2: a single line that is, or contains, the value.
        for entry in line_boxes:
            text = _normalise(str(entry.get("text", "")))
            if text and text == needle:
                return _box(entry), _page(entry)
        for entry in line_boxes:
            text = _normalise(str(entry.get("text", "")))
            if text and needle in text:
                return _box(entry), _page(entry)

        # 3: the value was wrapped across lines.
        #
        # Done in two steps, and the split matters. First find a *seed*: the longest line that
        # is part of this value and is long enough to be distinctive. Then grow outwards from
        # it while the neighbouring lines are also part of the value and on the same page.
        #
        # Collecting every matching line instead would be wrong in both directions. It would
        # miss "LLC" — three characters, below the distinctiveness floor, but plainly the rest
        # of the company name on the very next line — and it would happily union a stray "LLC"
        # printed somewhere else on the page into a box spanning half the document.
        # Adjacency is what separates "the value continues here" from "that word also appears
        # over there".
        seed = -1
        seed_length = 0
        for index, entry in enumerate(line_boxes):
            text = _normalise(str(entry.get("text", "")))
            if len(text) >= _MIN_FRAGMENT and text in needle and len(text) > seed_length:
                seed, seed_length = index, len(text)

        if seed >= 0:
            page = _page(line_boxes[seed])
            group = [seed]
            for step in (-1, 1):
                index = seed + step
                while 0 <= index < len(line_boxes):
                    entry = line_boxes[index]
                    text = _normalise(str(entry.get("text", "")))
                    if not text or text not in needle or _page(entry) != page:
                        break
                    group.append(index)
                    index += step

            boxes = [
                box for index in sorted(group) if (box := _box(line_boxes[index])) is not None
            ]
            if boxes:
                return _union(boxes), page

    # 4: fall back to the line after the label. The documents are laid out LABEL / value, so
    # the line following the label is where the value was printed even if OCR read it badly —
    # and a box round an unreadable value is exactly what a reviewer needs to see.
    label_key = _normalise(label) if label else ""
    if label_key:
        for index, entry in enumerate(line_boxes):
            if _normalise(str(entry.get("text", ""))) == label_key:
                following = line_boxes[index + 1] if index + 1 < len(line_boxes) else None
                if following is not None and _page(following) == _page(entry):
                    return _box(following), _page(following)
                return _box(entry), _page(entry)

    return None, None


def read_confidence(
    value: str | None, line_boxes: list[dict[str, Any]], *, label: str | None = None
) -> float | None:
    """The engine's own confidence in the line this value was read from.

    `None` when no line matched or the engine reported no confidence — a missing signal, which
    `confidence.combine()` drops rather than scoring as zero.
    """
    if not line_boxes or not value:
        return None
    needle = _normalise(value)
    for entry in line_boxes:
        text = _normalise(str(entry.get("text", "")))
        if text and (text == needle or needle in text):
            score = entry.get("confidence")
            return float(score) if score is not None else None
    return None


def _box(entry: dict[str, Any]) -> list[float] | None:
    box = entry.get("bbox")
    if isinstance(box, list) and len(box) == 4:
        return [float(number) for number in box]
    return None


def _page(entry: dict[str, Any]) -> int | None:
    page = entry.get("page")
    return int(page) if page is not None else None


__all__ = ["locate", "read_confidence"]
