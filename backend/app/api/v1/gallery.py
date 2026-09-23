"""The failure-mode gallery: read the catalogue, download a scenario's synthetic documents.

Running a scenario is deliberately NOT an endpoint here. The browser takes the documents and
goes through the ordinary intake — create, upload, start — exactly as a person uploading them
would, so the gallery can never take a path the product does not.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.core.deps import CurrentUser
from app.core.errors import NotFoundError
from app.schemas.gallery import GalleryFileOut, GalleryScenarioOut
from app.services import failure_gallery

router = APIRouter(prefix="/failure-gallery", tags=["failure-gallery"])


@router.get("", response_model=list[GalleryScenarioOut])
async def list_scenarios(_user: CurrentUser) -> list[GalleryScenarioOut]:
    return [
        GalleryScenarioOut(
            id=s.id,
            category=s.category,
            title_en=s.title_en,
            title_ar=s.title_ar,
            problem_en=s.problem_en,
            problem_ar=s.problem_ar,
            detection_en=s.detection_en,
            detection_ar=s.detection_ar,
            outcome_en=s.outcome_en,
            outcome_ar=s.outcome_ar,
            where_to_look_en=s.where_to_look_en,
            where_to_look_ar=s.where_to_look_ar,
            runnable=s.runnable,
            case_type=s.case_type,
            customer_name=s.customer_name,
            expected_codes=list(s.expected_codes),
            files=[GalleryFileOut(filename=f.filename, doc_type=f.doc_type) for f in s.files],
            evidence=list(s.evidence),
        )
        for s in failure_gallery.scenarios()
    ]


@router.get("/{scenario_id}/files/{index}")
async def scenario_file(scenario_id: str, index: int, _user: CurrentUser) -> Response:
    scenario = failure_gallery.by_id(scenario_id)
    if scenario is None or not 0 <= index < len(scenario.files):
        raise NotFoundError("Gallery document")
    item = scenario.files[index]
    return Response(
        content=item.pdf(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{item.filename}"'},
    )
