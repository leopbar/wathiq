"""M5: measured results, negative controls, provenance and durable corrections."""
import io
import json
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from sqlalchemy import select

from app.agent import worker
from app.agent.extractor import DemoExtractor
from app.agent.ocr import DemoOcr
from app.core.config import settings
from app.db import models
from app.db.enums import QualityBand
from app.quality.dataset import archive, pdf_bytes, samples
from app.quality.service import capture_correction
from app.quality.suites import run_band
from app.quality.tracking import track_fit


@pytest.mark.parametrize("band", list(QualityBand))
async def test_real_suites_and_negative_controls(band):
    results = await run_band(band)
    assert results and all(r.passed for r in results), [r.row() for r in results if not r.passed]
    assert any(not r.passed for r in await run_band(band, broken=True))


async def test_real_extractor_regression_is_detected(monkeypatch):
    # `**kwargs` so the stub keeps matching `ExtractorBackend.extract` as it grows — M6
    # added the keyword-only `prompt` and `examples`.
    broken = DemoExtractor()
    monkeypatch.setattr(broken, "extract", lambda *args, **kwargs: {})
    results = await run_band(QualityBand.model, extractor_backend=broken)
    assert sum(not r.passed for r in results) >= 20


async def test_quality_suite_never_resolves_the_deployment_extractor(monkeypatch):
    def deployment_factory_must_not_run():
        raise AssertionError("Quality Lab must stay deterministic and offline")

    monkeypatch.setattr(worker, "get_extractor", deployment_factory_must_not_run)
    results = await run_band(QualityBand.model)
    assert results and all(result.passed for result in results)


def test_dataset_has_answer_keys_and_real_image_only_blur():
    fixtures = samples()
    assert len(fixtures) == 50
    assert len({s.key for s in fixtures}) == 50
    ocr = DemoOcr()
    for sample in fixtures:
        result = ocr.read(pdf_bytes(sample.key), "application/pdf")
        if sample.quality == "blurry":
            assert result.text == "" and result.confidence == 0
        else:
            assert result.text
    with ZipFile(io.BytesIO(archive())) as bundle:
        assert len(bundle.namelist()) == 51
        manifest = json.loads(bundle.read("answer-key.json"))
        assert manifest["sample_count"] == 50


async def test_run_all_creates_five_new_persisted_runs(client, auth):
    headers = await auth("supervisor")
    response = await client.post("/api/v1/quality/runs", json={"band": "all"}, headers=headers)
    assert response.status_code == 200, response.text
    runs = response.json()["runs"]
    assert len(runs) == 5
    assert len({r["id"] for r in runs}) == 5
    for run in runs:
        detail = (await client.get(f"/api/v1/quality/runs/{run['id']}", headers=headers)).json()
        assert len(detail["cases"]) == run["passed"] + run["failed"]
        assert run["provenance"]["kind"] == "measured"
    repeated = await client.post("/api/v1/quality/runs", json={"band": "agent"}, headers=headers)
    assert repeated.json()["runs"][0]["id"] not in {r["id"] for r in runs}


async def test_eval_rbac_and_invalid_band(client, auth):
    assert (await client.post("/api/v1/quality/runs", json={})).status_code == 401
    assert (await client.post("/api/v1/quality/runs", json={},
                             headers=await auth("auditor"))).status_code == 403
    assert (await client.post("/api/v1/quality/runs", json={"band": "fake"},
                             headers=await auth("admin"))).status_code == 422


async def test_prompt_version_link_and_honest_sensitivity(client, auth):
    headers = await auth("admin")
    path = "/api/v1/prompts/extract_trade_license/versions/2.1.0"
    response = await client.post(path + "/evaluate", headers=headers)
    assert response.status_code == 200, response.text
    run = response.json()["runs"][0]
    assert run["provenance"]["prompt_version"] == "2.1.0"
    assert len(run["provenance"]["prompt_sha256"]) == 64
    assert run["provenance"]["sensitivity"]["status"] == "unsupported"
    history = (await client.get(path + "/evaluations", headers=headers)).json()
    assert history[0]["id"] == run["id"]
    assert (await client.post(path.replace("2.1.0", "99.0.0") + "/evaluate",
                              headers=headers)).status_code == 404


async def test_bad_prompt_contract_fails():
    results = await run_band(QualityBand.prompt, prompt={
        "key": "extract_trade_license", "body": "Guess anything", "document_type": "trade_license",
    })
    assert sum(not r.passed for r in results) == 2


async def test_sensitivity_detects_rewording_changes_and_stable_wrong_answers():
    from app.quality.sensitivity import measure

    async def sensitive(prompt, text):
        return {"name": "wrong" if "Respond with" in prompt else "correct"}

    fixtures = [{"key": "one", "text": "Name: correct", "expected": {"name": "correct"}}]
    results = await measure("Return JSON", fixtures, sensitive)
    assert any(not r.passed and "stability" in r.name for r in results)
    assert any(not r.passed and "correctness" in r.name for r in results)

    async def wrong(prompt, text):
        return {"name": "wrong"}

    results = await measure("Return JSON", fixtures, wrong)
    assert all(r.passed for r in results if "stability" in r.name)
    assert all(not r.passed for r in results if "correctness" in r.name)


async def test_correction_is_snapshotted_deduplicated_and_replayed(db_session):
    from uuid import uuid4
    definition = (await db_session.execute(select(models.DocumentType).where(
        models.DocumentType.key == "trade_license"))).scalar_one()
    document = SimpleNamespace(id=uuid4(), doc_type=definition.key,
                               ocr_text="Licence number\nWRONG")
    field = SimpleNamespace(id=uuid4(), document_id=document.id, name="license_number")
    task = SimpleNamespace(id=uuid4(), case=SimpleNamespace(documents=[document]))
    await capture_correction(db_session, task, field, "CORRECT")
    await capture_correction(db_session, task, field, "CORRECT")
    await db_session.commit()
    document.ocr_text = "changed later"
    rows = (await db_session.execute(select(models.RegressionExample).where(
        models.RegressionExample.source_key == f"{task.id}:{field.id}"))).scalars().all()
    assert len(rows) == 1 and rows[0].input_text == "Licence number\nWRONG"
    results = await run_band(QualityBand.agent, regressions=rows)
    saved = [r for r in results if r.is_regression]
    assert len(saved) == 1 and not saved[0].passed
    # Clean up this deliberately failing canary, not a user correction.
    await db_session.delete(rows[0])
    await db_session.commit()


async def test_tracking_disabled_and_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "mlflow_tracking_uri", "")
    assert (await track_fit({}))["status"] == "disabled"
    monkeypatch.setattr(settings, "mlflow_tracking_uri", "http://127.0.0.1:1")
    assert (await track_fit({}))["status"] == "unavailable"


async def test_brier_uses_individual_outcomes_not_bin_averages(client, auth, monkeypatch):
    from app.agent.calibration import CalibrationCurve
    from app.services import assurance

    async def outcomes(db):
        return [(0.8, True), (0.8, False)]

    async def raw_curve(db):
        return CalibrationCurve()

    monkeypatch.setattr(assurance, "collect_samples", outcomes)
    monkeypatch.setattr(assurance, "load_active", raw_curve)
    response = await client.get("/api/v1/quality/calibration", headers=await auth("admin"))
    assert response.status_code == 200, response.text
    assert response.json()["sample_count"] == 2
    assert response.json()["brier"] == pytest.approx(0.34)
    assert response.json()["ece"] == pytest.approx(0.3)
