"""Failure-mode gallery responses."""

from __future__ import annotations

from pydantic import BaseModel


class GalleryFileOut(BaseModel):
    filename: str
    doc_type: str


class GalleryScenarioOut(BaseModel):
    id: str
    category: str
    title_en: str
    title_ar: str
    problem_en: str
    problem_ar: str
    detection_en: str
    detection_ar: str
    outcome_en: str
    outcome_ar: str
    where_to_look_en: str
    where_to_look_ar: str
    runnable: bool
    case_type: str
    customer_name: str
    expected_codes: list[str]
    files: list[GalleryFileOut]
    evidence: list[str]
