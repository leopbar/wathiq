"""Output sanitisation.

Whatever a model (or a document) produces ends up on a reviewer's screen and in a database
row. Before that happens it is cleaned, because the text arrived from outside:

* HTML and script tags are removed — an extracted value rendered in the console must never be
  able to execute anything;
* zero-width and bidirectional control characters are removed — they are invisible to the
  reviewer and can make a value display differently from what is stored;
* other control characters are removed, and whitespace is collapsed;
* the value is capped, so one malformed document cannot push a megabyte into a field.

This runs in every mode. It is the last thing between untrusted text and our records.
"""

from __future__ import annotations

import re
import unicodedata

_TAG = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")
_SCRIPT_BLOCK = re.compile(r"<\s*(script|style)[^>]*>.*?<\s*/\s*\1\s*>", re.IGNORECASE | re.DOTALL)
_ENTITY = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);")
# PDF text layers use the non-breaking space constantly, so it counts as
# whitespace here. Built with chr() so no invisible character sits in the source.
NBSP = chr(0xA0)
_WHITESPACE = re.compile(f"[ \t{NBSP}]+")
# `javascript:` and `data:` URLs in a value have no legitimate use in a bank document.
_DANGEROUS_URL = re.compile(r"\b(javascript|data|vbscript)\s*:", re.IGNORECASE)

MAX_VALUE_LENGTH = 512
MAX_TEXT_LENGTH = 200_000


def _strip_invisible(text: str) -> str:
    return "".join(
        char
        for char in text
        # Cf = "format" characters: zero-width joiners, bidi overrides, the BOM.
        # Cc = control characters. Tab and newline are kept deliberately.
        if unicodedata.category(char) not in ("Cf", "Cc") or char in "\n\t"
    )


def sanitise_value(value: str | None, *, limit: int = MAX_VALUE_LENGTH) -> str | None:
    """Clean one extracted field value. `None` stays `None` — an empty field is information."""
    if value is None:
        return None
    text = _SCRIPT_BLOCK.sub(" ", value)
    text = _TAG.sub(" ", text)
    text = _ENTITY.sub(" ", text)
    text = _DANGEROUS_URL.sub("", text)
    text = _strip_invisible(text).replace("\n", " ").replace("\t", " ")
    text = _WHITESPACE.sub(" ", text).strip()
    return text[:limit] if text else None


def sanitise_text(text: str, *, limit: int = MAX_TEXT_LENGTH) -> str:
    """Clean a whole document's text, keeping its line structure."""
    cleaned = _SCRIPT_BLOCK.sub(" ", text)
    cleaned = _TAG.sub(" ", cleaned)
    cleaned = _strip_invisible(cleaned)
    lines = [_WHITESPACE.sub(" ", line).strip() for line in cleaned.split("\n")]
    return "\n".join(lines)[:limit]


def changed(original: str | None, cleaned: str | None) -> bool:
    """Whether sanitisation actually removed something — worth recording when it did."""
    return (original or "") != (cleaned or "")
