"""Splitting the policy documents into retrievable chunks.

A chunk here is **one policy section**, because that is the unit a finding cites. Splitting a
policy by a fixed number of characters would produce citations like "KYC-POL-004, characters
1200-1800", which is useless to a reviewer, and would regularly cut a rule in half.

Each chunk keeps three things:

* `policy_id` — "KYC-POL-004", taken from the file name;
* `section`   — "§3.2", taken from the heading;
* `citation`  — "KYC-POL-004 §3.2", which is exactly the string a rule pack writes.

That last one is why retrieval works so well here: most of the time we do not need to search at
all, because the rule already names the section. Search is the fallback for findings that have
no citation, and for the "which policy covers this?" question.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

CORPUS_DIR = Path(__file__).parent / "corpus"

_HEADING = re.compile(r"^##\s+(§[\d.]+)\s+(.*)$", re.MULTILINE)
_TITLE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
# The "> SYNTHETIC POLICY" banner is a note to the reader, not policy text.
_BANNER = re.compile(r"^>.*$", re.MULTILINE)


@dataclass(slots=True)
class PolicyChunk:
    policy_id: str
    policy_title: str
    section: str
    heading: str
    text: str

    @property
    def citation(self) -> str:
        return f"{self.policy_id} {self.section}"

    @property
    def embedding_text(self) -> str:
        """What gets embedded: the heading matters as much as the body, so it is included."""
        return f"{self.policy_title} {self.section} {self.heading}\n{self.text}"


def split_document(policy_id: str, markdown: str) -> list[PolicyChunk]:
    title_match = _TITLE.search(markdown)
    policy_title = title_match.group(1).strip() if title_match else policy_id

    headings = list(_HEADING.finditer(markdown))
    chunks: list[PolicyChunk] = []
    for index, match in enumerate(headings):
        start = match.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(markdown)
        body = _BANNER.sub("", markdown[start:end]).strip()
        if not body:
            continue
        chunks.append(
            PolicyChunk(
                policy_id=policy_id,
                policy_title=policy_title,
                section=match.group(1).strip(),
                heading=match.group(2).strip(),
                text=re.sub(r"\n{2,}", "\n\n", body),
            )
        )
    return chunks


def load_corpus(directory: Path | None = None) -> list[PolicyChunk]:
    """Every chunk of every policy on disk."""
    directory = directory or CORPUS_DIR
    chunks: list[PolicyChunk] = []
    if not directory.is_dir():
        return chunks
    for path in sorted(directory.glob("*.md")):
        chunks.extend(split_document(path.stem, path.read_text(encoding="utf-8")))
    return chunks
