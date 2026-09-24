"""Showing a value in the reader's language, without changing what the document said.

An Arabic licence extracts Arabic values. A reader working in English then sees
`تجارة عامة` in a field labelled "Business activity", which is correct and unhelpful.

The rule here is the one that matters for a bank: **the extracted value is evidence.** It is
what the document says, it is what the audit trail keeps, and it is what the posting step sends
to core banking. A translation is a reading aid shown beside it, stored in its own column,
marked with where it came from, and never sent anywhere as the value.

Two backends, the same shape as OCR and extraction:

* `GlossaryTranslator` (demo, and the fallback) knows the standard terms that appear on UAE
  trade licences, Emirates IDs and salary certificates. It is a dictionary: offline, instant,
  reproducible, and honest about what it does not know — an unknown phrase gets no translation
  rather than a guess.
* `FoundryTranslator` (Azure) asks the model, in **one call per document**, for the whole list.
  It is told to transliterate names rather than translate them, because "Falcon Ridge" is what
  the company is called and "قمة الصقر" is not a name anyone can look up.

What is never translated: numbers, dates, licence numbers, IBANs and anything without Arabic
letters. Translating an identifier would be actively harmful.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.agent.classifier import normalise

logger = logging.getLogger(__name__)

# Arabic letters, plus the presentation forms a PDF text layer may hold (see classifier.normalise).
_ARABIC = re.compile("[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
# A value made only of digits, separators and Latin letters is an identifier, not prose.
_IDENTIFIER = re.compile(r"^[A-Za-z0-9\s\-/.,:()]+$")


@dataclass(frozen=True, slots=True)
class Translation:
    """A reading aid. `source` says who produced it, so the UI can say so too."""

    text: str | None
    source: str  # "glossary" | "model" | "none"


NOT_TRANSLATED = Translation(None, "none")


# Standard terms on UAE commercial documents. Keys are normalised (see `classifier.normalise`),
# so a different alef or a vowel mark still matches. Values are the wording a UAE bank uses.
_GLOSSARY: dict[str, str] = {
    # legal forms
    "ذ.م.م": "LLC",
    "ذمم": "LLC",
    "شركة ذات مسؤولية محدودة": "Limited Liability Company",
    "شركة الشخص الواحد": "Sole Proprietorship",
    "مؤسسة فردية": "Sole Establishment",
    "شركة مساهمة عامة": "Public Joint Stock Company",
    "شركة مساهمة خاصة": "Private Joint Stock Company",
    "فرع شركة أجنبية": "Branch of a Foreign Company",
    # licensing authorities
    "دائرة التنمية الاقتصادية": "Department of Economic Development",
    "دائرة التنمية الاقتصادية بأبوظبي": "Abu Dhabi Department of Economic Development",
    "سلطة المنطقة الحرة": "Free Zone Authority",
    "غرفة التجارة والصناعة": "Chamber of Commerce and Industry",
    # activities
    "تجارة عامة": "General trading",
    "تجارة التجزئة": "Retail trade",
    "مقاولات عامة": "General contracting",
    "خدمات لوجستية": "Logistics services",
    "استشارات إدارية": "Management consultancy",
    "خدمات تقنية المعلومات": "Information technology services",
    "نقل بضائع": "Freight transport",
    "تجارة مواد البناء": "Building materials trading",
    "خدمات بحرية": "Marine services",
    "تجارة المعدات الطبية": "Medical equipment trading",
    # document titles and common labels
    "رخصة تجارية": "Trade licence",
    "الرخصة التجارية": "Trade licence",
    "شهادة راتب": "Salary certificate",
    "عقد التأسيس": "Memorandum of association",
    "بطاقة الهوية": "Identity card",
    "جواز السفر": "Passport",
    # status words a licence may carry
    "سارية": "Valid",
    "منتهية": "Expired",
    "ملغاة": "Cancelled",
    "قائمة": "Active",
    # salary certificate terms
    "درهم": "AED",
    "مدير عمليات": "Operations Manager",
    "مهندس أول": "Senior Engineer",
    "محاسب": "Accountant",
    "مدير مالي": "Finance Manager",
    "موظف": "Employee",
    # nationalities that appear on an Emirates ID
    "الإمارات العربية المتحدة": "United Arab Emirates",
    "مصر": "Egypt",
    "الهند": "India",
    "لبنان": "Lebanon",
    "باكستان": "Pakistan",
    "الفلبين": "Philippines",
}

_LOOKUP = {normalise(key).strip(): value for key, value in _GLOSSARY.items()}

# Hyphen, en dash, em dash, slash, Arabic comma, comma, pipe — written by code point, because a
# dash that looks like a hyphen but is not one is exactly the kind of character a reader cannot
# see in a diff.
_SEPARATORS = "-" + chr(0x2013) + chr(0x2014) + "/" + chr(0x060C) + ",|"
_SEPARATOR_CLASS = "[" + re.escape(_SEPARATORS) + "]+"


def needs_translation(value: str | None) -> bool:
    """True only for text that actually contains Arabic letters and is not an identifier."""
    if not value or not value.strip():
        return False
    if _IDENTIFIER.match(value.strip()):
        return False
    return bool(_ARABIC.search(value))


class TranslatorBackend(ABC):
    """Translate values into English. Order in, order out — callers zip the two lists."""

    name: str = "translator"

    @abstractmethod
    def translate(self, values: list[str]) -> list[Translation]: ...


class GlossaryTranslator(TranslatorBackend):
    """Dictionary lookup. Never guesses: an unknown phrase comes back untranslated."""

    name = "glossary"

    def translate(self, values: list[str]) -> list[Translation]:
        results: list[Translation] = []
        for value in values:
            key = normalise(value).strip()
            english = _LOOKUP.get(key)
            if english is None:
                # A value like "ذ.م.م - تجارة عامة" is two known terms with a separator.
                separators = _SEPARATOR_CLASS
                parts = [part.strip() for part in re.split(separators, value) if part.strip()]
                if len(parts) > 1:
                    pieces = [_LOOKUP.get(normalise(part).strip()) for part in parts]
                    if all(pieces):
                        english = " - ".join(piece for piece in pieces if piece)
            results.append(
                Translation(english, "glossary") if english else NOT_TRANSLATED
            )
        return results


_backend: TranslatorBackend | None = None


def get_translator() -> TranslatorBackend:
    """The translator this deployment is configured for.

    Foundry only when the model is configured; otherwise the glossary. The import sits inside
    the branch so demo mode never loads an Azure SDK.
    """
    global _backend
    if _backend is None:
        from app.core.config import settings

        if settings.foundry_enabled:
            from app.azure.foundry import FoundryTranslator

            _backend = FoundryTranslator()
        else:
            _backend = GlossaryTranslator()
    return _backend


def reset_translator() -> None:
    """Tests and the settings screen rebuild the backend after configuration changes."""
    global _backend
    _backend = None


def translate_values(values: list[str | None]) -> list[Translation]:
    """Translate the ones that need it, leave the rest alone, never fail the pipeline.

    A translation is a convenience. If the backend raises — a model timeout, a bad response —
    the case carries on with no translation and the failure is logged. Losing a reading aid
    must never lose a case.
    """
    wanted = [index for index, value in enumerate(values) if needs_translation(value)]
    results: list[Translation] = [NOT_TRANSLATED] * len(values)
    if not wanted:
        return results

    backend = get_translator()
    try:
        produced = backend.translate([str(values[index]) for index in wanted])
    except Exception as exc:  # a reading aid may never break a case
        logger.warning("translation unavailable (%s): %s", backend.name, exc)
        return results

    for index, translation in zip(wanted, produced, strict=False):
        results[index] = translation
    return results
