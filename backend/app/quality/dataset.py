"""Synthetic answer keys are authored before extraction; never inferred from its output.

Blurred PDFs have raster-only content. Demo OCR must abstain on them. This tests honest
abstention, not optical recognition accuracy. Arabic is a visible companion column; English
labels are the text-layer extraction contract until the Azure OCR adapter arrives.
"""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageFilter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.db.seed_data import DOC_TYPE_DEFS

VERSION = "golden-1.0.0"
QUALITIES = ("clean", "blurry", "cropped", "wrong_type", "missing_field")


@dataclass
class Sample:
    key: str
    doc_type: str
    quality: str
    language: str
    title: str
    schema: list[dict]
    values: dict[str, str]
    expected: dict[str, str | None]
    expected_type: str


def samples() -> list[Sample]:
    result = []
    for definition in DOC_TYPE_DEFS:
        schema = definition["fields"]
        for language in ("en", "bilingual"):
            for quality in QUALITIES:
                # Distinct identities keep fixtures from being copies with new filenames.
                index = len(result) + 1
                values = {
                    s["name"]: (
                        "2030-12-31"
                        if "expiry" in s["name"]
                        else "2020-01-15"
                        if s["type"] == "date"
                        else "12500"
                        if s["type"] == "number"
                        else f"Synthetic {s['name'].replace('_', ' ')} {index}"
                    )
                    for s in schema
                }
                visible = dict(values)
                if quality == "missing_field":
                    visible.pop(schema[0]["name"])
                if quality == "cropped":
                    visible = {s["name"]: values[s["name"]] for s in schema[: len(schema) // 2]}
                expected = {s["name"]: visible.get(s["name"]) for s in schema}
                if quality in ("blurry", "wrong_type"):
                    expected = dict.fromkeys(values)
                result.append(
                    Sample(
                        key=f"{definition['key']}-{language}-{quality}",
                        doc_type=str(definition["key"]),
                        quality=quality,
                        language=language,
                        title=str(definition["name_en"]),
                        schema=schema,
                        values=visible,
                        expected=expected,
                        expected_type="unknown"
                        if quality in ("blurry", "wrong_type")
                        else str(definition["key"]),
                    )
                )
    return result


@lru_cache(maxsize=64)
def pdf_bytes(key: str) -> bytes:
    sample = next(s for s in samples() if s.key == key)
    pdfmetrics.registerFont(
        TTFont("GoldenArabic", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    )
    stream = io.BytesIO()
    page = canvas.Canvas(stream, pagesize=(595, 842), invariant=1)
    page.setTitle(f"Synthetic fixture: {sample.key}")
    page.setFont("Helvetica-Bold", 19)
    page.drawString(40, 793, "Cafe receipt" if sample.quality == "wrong_type" else sample.title)
    page.setFont("Helvetica", 9)
    page.drawString(40, 771, f"SYNTHETIC TEST DOCUMENT | {VERSION} | {sample.quality}")
    if sample.quality == "wrong_type":
        page.drawString(40, 700, "Two coffees - total AED 24.00")
    else:
        y = 724
        for spec in sample.schema:
            if spec["name"] not in sample.values:
                continue
            page.setFont("Helvetica", 10)
            page.drawString(40, y, spec["label_en"])
            page.setFont("Helvetica", 11)
            page.drawString(40, y - 18, sample.values[spec["name"]])
            if sample.language == "bilingual":
                page.setFont("GoldenArabic", 10)
                page.drawRightString(550, y, get_display(arabic_reshaper.reshape(spec["label_ar"])))
            y -= 55
    page.setFont("Helvetica", 8)
    page.drawString(40, 48, "Fictional data. No bank affiliation. For software testing only.")
    page.save()
    data = stream.getvalue()
    if sample.quality != "blurry":
        return data
    # Rasterise, blur, then embed with NO hidden text layer or answer-key backdoor.
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "source.pdf"
        source.write_bytes(data)
        subprocess.run(
            [
                "pdftoppm",
                "-singlefile",
                "-scale-to",
                "900",
                "-png",
                str(source),
                str(Path(directory) / "scan"),
            ],
            check=True,
            capture_output=True,
            timeout=20,
        )
        with Image.open(Path(directory) / "scan.png") as raster:
            blurred = raster.filter(ImageFilter.GaussianBlur(2.2))
            output = io.BytesIO()
            scan = canvas.Canvas(output, pagesize=(595, 842), invariant=1)
            scan.drawImage(ImageReader(blurred), 0, 0, 595, 842)
            scan.save()
            return output.getvalue()


def archive() -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as bundle:
        bundle.writestr(
            "answer-key.json",
            json.dumps(
                {
                    "version": VERSION,
                    "sample_count": len(samples()),
                    "scope": "Synthetic text-layer checks; blurry scans test abstention, not OCR.",
                    "samples": [asdict(s) for s in samples()],
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        for sample in samples():
            bundle.writestr(f"{sample.key}.pdf", pdf_bytes(sample.key))
    return output.getvalue()
