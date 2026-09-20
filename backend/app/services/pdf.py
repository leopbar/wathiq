"""A very small PDF writer.

Only used to produce readable placeholder documents for the seeded demo cases, so the document
viewer has something real to show without checking binaries into git. The real bilingual
synthetic document generator (with Arabic rendering) arrives with the golden dataset in M5.
"""

from __future__ import annotations

PAGE_WIDTH = 595
PAGE_HEIGHT = 842


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _ascii(text: str) -> str:
    """Base-14 PDF fonts cannot encode Arabic; keep the file valid and say so honestly."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


def simple_pdf(title: str, lines: list[tuple[str, str]], footer: str) -> bytes:
    """Build a one-page PDF. `lines` is a list of (label, value) pairs."""
    content: list[str] = [
        "BT /F1 18 Tf 60 780 Td (" + _escape(_ascii(title)) + ") Tj ET",
        "0.6 w 60 768 m 535 768 l S",
    ]
    y = 730
    for label, value in lines:
        content.append(f"BT /F2 10 Tf 60 {y} Td ({_escape(_ascii(label.upper()))}) Tj ET")
        content.append(f"BT /F1 13 Tf 60 {y - 18} Td ({_escape(_ascii(value))}) Tj ET")
        y -= 46
        if y < 120:
            break
    content.append(f"BT /F2 9 Tf 60 90 Td ({_escape(_ascii(footer))}) Tj ET")
    stream = "\n".join(content).encode("latin-1", errors="replace")

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            "/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 4 0 R >>"
        ).encode("latin-1"),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode("latin-1") + body + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("latin-1")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode("latin-1")
    return bytes(out)
