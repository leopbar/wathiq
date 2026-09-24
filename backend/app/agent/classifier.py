"""Deciding what kind of document each file is.

The text is scored against keywords that belong to each document type, **in English and in
Arabic**. It is a transparent scorer, not a model: you can read why it chose a type, which
matters when a reviewer asks why a document was refused.

Arabic needs two things English does not:

* **normalisation.** The same word is written several ways: four forms of alef, teh marbuta or
  heh at the end, alef maksura or yeh, optional vowel marks, and the tatweel character used to
  stretch a word when justifying a line. A licence that prints one spelling where the keyword
  holds another is still the same word, and a scorer that misses it refuses an ordinary
  document.
* **its own keywords.** An Arabic trade licence contains the words "trade licence" nowhere at
  all, so an English-only list scores zero and the document is marked unknown. That is exactly
  what happened to the first real Arabic licence put through this system.

The same function runs in Azure mode. There is no model-based classifier: a model could answer
this question, but nothing here calls one, and a docstring claiming otherwise would be a claim
the reader cannot check.
"""

from __future__ import annotations

import re
import unicodedata

from app.db.enums import DocTypeKey

# Arabic vowel marks and the tatweel, which carry no meaning for matching.
_DIACRITICS = re.compile(r"[\u064b-\u0652\u0670\u0640]")
# The alef family (madda, hamza above, hamza below, wasla), all written as a plain alef.
_ALEF = re.compile(r"[\u0622\u0623\u0625\u0671]")
# Anything that is not a letter or digit, in any script, is a word separator: a licence prints
# "رقم الرخصة:" with a colon, and wraps phrases across lines.
_SEPARATORS = re.compile(r"[^\w\u0600-\u06ff]+")


def normalise(text: str) -> str:
    """Fold the spellings of a word onto one, in both scripts, so a keyword can match.

    English is only lowercased. Arabic also loses its vowel marks and tatweel, and alef, alef
    maksura and teh marbuta are each written one way. The result is padded with spaces so a
    caller can match whole words.
    """
    # NFKC first: a PDF's text layer often holds Arabic as *presentation forms* \u2014 the shaped
    # glyph codes a renderer uses (U+FB50\u2026U+FEFF) rather than the letters themselves. They
    # look identical on screen and match nothing at all, which is its own silent failure.
    # NFKC folds them back to the letters; the word order is already logical.
    folded = unicodedata.normalize("NFKC", text).lower()
    folded = _ALEF.sub("\u0627", _DIACRITICS.sub("", folded))
    folded = folded.replace("\u0649", "\u064a").replace("\u0629", "\u0647")
    return f" {_SEPARATORS.sub(' ', folded).strip()} "


def _split_filename(filename: str) -> str:
    """`tradeLicenseFake.jpg` -> `trade License Fake jpg`.

    A filename is weak evidence, but it is evidence, and a camel-cased one scored nothing at
    all before, because its words were never separated.
    """
    return _SEPARATORS.sub(" ", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", filename))


# Words that strongly indicate a type. Weight 3 = a title-level phrase, 1 = a supporting field.
# Arabic entries sit beside the English ones: one list per document type, either language.
_SIGNALS: dict[DocTypeKey, list[tuple[str, int]]] = {
    DocTypeKey.trade_license: [
        ("trade licence", 3), ("trade license", 3), ("licence number", 2),
        ("license number", 2), ("licensing authority", 2), ("business activity", 1),
        ("legal form", 1), ("commercial register", 2),
        ("\u0631\u062e\u0635\u0629 \u062a\u062c\u0627\u0631\u064a\u0629", 3),
        ("\u0627\u0644\u0631\u062e\u0635\u0629 \u0627\u0644\u062a\u062c\u0627"
         "\u0631\u064a\u0629", 3),
        ("\u0631\u0642\u0645 \u0627\u0644\u0631\u062e\u0635\u0629", 2),
        ("\u0627\u0644\u0633\u062c\u0644 \u0627\u0644\u062a\u062c\u0627\u0631"
         "\u064a", 2),
        ("\u062f\u0627\u0626\u0631\u0629 \u0627\u0644\u062a\u0646\u0645\u064a\u0629"
         " \u0627\u0644\u0627\u0642\u062a\u0635\u0627\u062f\u064a\u0629", 2),
        ("\u0633\u0644\u0637\u0629 \u0627\u0644\u062a\u0631\u062e\u064a\u0635", 2),
        ("\u0627\u0644\u0646\u0634\u0627\u0637 \u0627\u0644\u062a\u062c\u0627\u0631"
         "\u064a", 1),
        ("\u0627\u0644\u0634\u0643\u0644 \u0627\u0644\u0642\u0627\u0646\u0648\u0646"
         "\u064a", 1),
        ("\u0627\u0644\u0627\u0633\u0645 \u0627\u0644\u062a\u062c\u0627\u0631"
         "\u064a", 1),
    ],
    DocTypeKey.emirates_id: [
        ("emirates id", 3), ("identity card", 3), ("id number", 2),
        ("nationality", 1), ("card number", 1),
        ("\u0627\u0644\u0647\u0648\u064a\u0629 \u0627\u0644\u0625\u0645\u0627\u0631"
         "\u0627\u062a\u064a\u0629", 3),
        ("\u0628\u0637\u0627\u0642\u0629 \u0627\u0644\u0647\u0648\u064a\u0629", 3),
        ("\u0631\u0642\u0645 \u0627\u0644\u0647\u0648\u064a\u0629", 2),
        ("\u0631\u0642\u0645 \u0627\u0644\u0628\u0637\u0627\u0642\u0629", 1),
        ("\u0627\u0644\u062c\u0646\u0633\u064a\u0629", 1),
    ],
    DocTypeKey.passport: [
        ("passport", 3), ("passport number", 2), ("place of birth", 2),
        ("date of birth", 1), ("nationality", 1),
        ("\u062c\u0648\u0627\u0632 \u0627\u0644\u0633\u0641\u0631", 3),
        ("\u062c\u0648\u0627\u0632 \u0633\u0641\u0631", 3),
        ("\u0631\u0642\u0645 \u0627\u0644\u062c\u0648\u0627\u0632", 2),
        ("\u0645\u0643\u0627\u0646 \u0627\u0644\u0645\u064a\u0644\u0627\u062f", 2),
        ("\u062a\u0627\u0631\u064a\u062e \u0627\u0644\u0645\u064a\u0644\u0627"
         "\u062f", 1),
        ("\u0627\u0644\u062c\u0646\u0633\u064a\u0629", 1),
    ],
    DocTypeKey.moa: [
        ("memorandum of association", 3), ("memorandum", 2), ("shareholder", 2),
        ("share capital", 2), ("articles of association", 2),
        ("\u0639\u0642\u062f \u0627\u0644\u062a\u0623\u0633\u064a\u0633", 3),
        ("\u0639\u0642\u062f \u062a\u0623\u0633\u064a\u0633", 3),
        ("\u0627\u0644\u0646\u0638\u0627\u0645 \u0627\u0644\u0623\u0633\u0627\u0633"
         "\u064a", 2),
        ("\u0627\u0644\u0634\u0631\u0643\u0627\u0621", 2),
        ("\u0631\u0623\u0633 \u0627\u0644\u0645\u0627\u0644", 2),
        ("\u0627\u0644\u062d\u0635\u0635", 1),
    ],
    DocTypeKey.salary_certificate: [
        ("salary certificate", 3), ("basic salary", 2), ("gross salary", 2),
        ("employer", 1), ("designation", 1), ("employee", 1),
        ("\u0634\u0647\u0627\u062f\u0629 \u0631\u0627\u062a\u0628", 3),
        ("\u0634\u0647\u0627\u062f\u0629 \u0627\u0644\u0631\u0627\u062a\u0628", 3),
        ("\u0627\u0644\u0631\u0627\u062a\u0628 \u0627\u0644\u0623\u0633\u0627\u0633"
         "\u064a", 2),
        ("\u0625\u062c\u0645\u0627\u0644\u064a \u0627\u0644\u0631\u0627\u062a"
         "\u0628", 2),
        ("\u0635\u0627\u062d\u0628 \u0627\u0644\u0639\u0645\u0644", 1),
        ("\u0627\u0644\u0645\u0633\u0645\u0649 \u0627\u0644\u0648\u0638\u064a\u0641"
         "\u064a", 1),
        ("\u0627\u0633\u0645 \u0627\u0644\u0645\u0648\u0638\u0641", 1),
    ],
}

# Below this, we refuse to guess and mark the document unknown for a human to look at.
_MIN_SCORE = 3


def classify(text: str, filename: str = "") -> tuple[DocTypeKey, float, list[str]]:
    """Return the best document type, a confidence and the evidence behind it.

    The evidence list is kept so the timeline can show *why* a document was classified, rather
    than only what the answer was.
    """
    haystack = normalise(f"{text}\n{_split_filename(filename)}")

    scores: dict[DocTypeKey, int] = {}
    evidence: dict[DocTypeKey, list[str]] = {}
    for doc_type, signals in _SIGNALS.items():
        total = 0
        hits: list[str] = []
        for phrase, weight in signals:
            # Both sides are normalised, so a keyword written with a different alef, a vowel
            # mark or a stretched letter still matches.
            if normalise(phrase).strip() in haystack:
                total += weight
                hits.append(phrase)
        if total:
            scores[doc_type] = total
            evidence[doc_type] = hits

    if not scores:
        return DocTypeKey.unknown, 0.0, []

    best = max(scores, key=lambda key: scores[key])
    best_score = scores[best]
    if best_score < _MIN_SCORE:
        return DocTypeKey.unknown, round(best_score / 10, 3), evidence.get(best, [])

    # Confidence reflects how far ahead the winner is, so a close call scores lower.
    runner_up = max((v for k, v in scores.items() if k != best), default=0)
    margin = (best_score - runner_up) / best_score
    confidence = round(min(0.99, 0.55 + 0.44 * margin), 3)
    return best, confidence, evidence[best]
