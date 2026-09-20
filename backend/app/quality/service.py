"""Persist measured runs and snapshot synthetic reviewer corrections."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.agent.ocr import get_ocr
from app.core.config import settings
from app.db import models
from app.db.enums import QualityBand
from app.quality.dataset import VERSION
from app.quality.suites import prompt_provenance, run_band
from app.services.storage import get_storage


async def evaluate(db, band, *, actor: str, prompt: dict | None = None):
    regressions = (await db.execute(select(models.RegressionExample))).scalars().all()
    bands = list(QualityBand) if band == "all" else [QualityBand(band)]
    runs = []
    for target in bands:
        started = datetime.now(UTC)
        results = await run_band(target, prompt=prompt, regressions=regressions)
        passed = sum(r.passed for r in results)
        run = models.QualityRun(
            band=target,
            started_at=started,
            finished_at=datetime.now(UTC),
            passed=passed,
            failed=len(results) - passed,
            score=passed / len(results) if results else 0,
            triggered_by=actor,
            commit_sha=settings.build_sha,
            provenance={
                "kind": "measured",
                "dataset": VERSION,
                "model": "demo-extractor-1.0.0",
                "sample_count": len(results),
                "scope": "Synthetic diagnostic checks, not production accuracy. "
                "Blurred scans test abstention. Agent band tests worker/critic "
                "components; full process coverage is in integration tests.",
                **(prompt_provenance(prompt) if prompt else {}),
            },
        )
        db.add(run)
        await db.flush()
        for result in results:
            db.add(models.QualityCase(run_id=run.id, band=target, **result.row()))
        runs.append(run)
    await db.flush()
    return runs


async def capture_correction(db, task, field, value):
    document = next((d for d in task.case.documents if d.id == field.document_id), None)
    definition = (
        (
            await db.execute(
                select(models.DocumentType).where(models.DocumentType.key == document.doc_type)
            )
        ).scalar_one_or_none()
        if document
        else None
    )
    if not definition or not document:
        raise ValueError("A regression snapshot requires the source document and schema")
    input_text = document.ocr_text
    if not input_text and getattr(document, "storage_path", ""):
        input_text = get_ocr().read(
            get_storage().read(document.storage_path), document.mime_type
        ).text
    await db.execute(
        insert(models.RegressionExample)
        .values(
            source_key=f"{task.id}:{field.id}",
            document_type=str(document.doc_type),
            field_name=field.name,
            expected=value,
            input_text=input_text,
            field_schema=definition.field_schema,
        )
        .on_conflict_do_nothing(index_elements=["source_key"])
    )
