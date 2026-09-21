"""Azure ML: running the calibration fit as a managed job.

The fit itself is ninety lines of gradient descent in `agent/calibration.py` and it takes
milliseconds. Submitting it to a cluster is *slower*. So this module is not here to make the
fit faster — it is here because of what a managed job gives you that an in-process function
does not, and those are the reasons a bank cares about:

* **it is reproducible.** The job records the exact code, the exact environment and the exact
  inputs. "Which curve is in production and what was it fitted on" stops being a question
  answered from memory.
* **it is auditable.** Every run has an id, an owner, a start and end time, and outputs that
  survive the process that asked for it. A model that decides whether a human looks at a KYC
  case needs that.
* **it scales past this one model.** The day calibration becomes something heavier than Platt
  scaling, nothing about the submission changes.

**The local fit remains the default and is never removed.** With no `AZURE_ML_*` settings the
calibration works exactly as it has since M3. This adapter is the same computation, run
somewhere that keeps a record of it. See DECISIONS #74.

**Honesty about what this does and does not prove.** Wathiq submits the job, waits for it and
reads back the fitted parameters; it does not pretend the curve was produced locally. If the
job fails or the workspace is unreachable, the caller is told, and the local fit is used — with
the event log saying which one ran, because a curve of unknown provenance is worse than a
known-local one.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.agent.calibration import CalibrationCurve
from app.azure.credentials import require_sdk, token_credential
from app.core.config import settings

logger = logging.getLogger(__name__)

# The job is tiny; anything longer than this means something is wrong with the cluster rather
# than with the fit, and a reviewer is waiting.
_DEFAULT_TIMEOUT_SECONDS = 600


class AzureMlUnavailable(RuntimeError):
    """The workspace is configured but the job could not be run. Never swallowed."""


@dataclass(slots=True)
class JobResult:
    """What came back, and enough provenance to explain it later."""

    curve: CalibrationCurve
    job_name: str
    studio_url: str
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_name": self.job_name,
            "studio_url": self.studio_url,
            "status": self.status,
            "where": "azure-ml",
            **self.curve.as_dict(),
        }


def _client() -> Any:
    module = require_sdk("azure.ai.ml", "Azure ML")
    return module.MLClient(
        credential=token_credential(),
        subscription_id=settings.azure_ml_subscription_id.strip(),
        resource_group_name=settings.azure_ml_resource_group.strip(),
        workspace_name=settings.azure_ml_workspace.strip(),
    )


def tracking_uri() -> str | None:
    """The workspace's own MLflow endpoint, when there is one.

    M5 already tracks every fit to MLflow. An Azure ML workspace *is* an MLflow server, so
    pointing `WATHIQ_MLFLOW_TRACKING_URI` at this URI moves that tracking into Azure without
    changing a line of the tracking code. Returns `None` when Azure ML is not configured, and
    the local MLflow service keeps serving.
    """
    if not settings.azure_ml_enabled:
        return None
    try:
        workspace = _client().workspaces.get(settings.azure_ml_workspace.strip())
        return str(getattr(workspace, "mlflow_tracking_uri", "") or "") or None
    except Exception as exc:  # pragma: no cover - depends on the workspace
        logger.warning("azure ml: could not read the workspace tracking URI: %s", exc)
        return None


def submit_fit(
    samples: list[tuple[float, bool]],
    *,
    model_version: str = "",
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
) -> JobResult:
    """Run the calibration fit as an Azure ML command job and read the curve back.

    The job runs `python -m app.quality.fit_job`, which is the *same* `calibration.fit()` the
    local path calls — there is deliberately no second implementation of the maths, because two
    implementations of a calibration curve is two curves.
    """
    if not settings.azure_ml_enabled:
        raise AzureMlUnavailable("Azure ML workspace is not configured")

    entities = require_sdk("azure.ai.ml.entities", "Azure ML")

    payload = json.dumps([[float(raw), bool(correct)] for raw, correct in samples])
    job = entities.CommandJob(
        display_name="wathiq-calibration-fit",
        description=(
            "Platt scaling of Wathiq's per-field confidence on reviewer outcomes. "
            "Input is (raw score, was the reviewer's decision that it was correct)."
        ),
        command=(
            "python -m app.quality.fit_job "
            "--samples ${{inputs.samples}} --model-version ${{inputs.model_version}}"
        ),
        inputs={
            "samples": payload,
            "model_version": model_version or "unversioned",
        },
        environment=f"azureml:{settings.azure_ml_workspace.strip()}-env@latest",
        compute=settings.azure_ml_compute.strip(),
    )

    try:
        client = _client()
        submitted = client.jobs.create_or_update(job)
        logger.info("azure ml: submitted %s", submitted.name)
        _wait_for(client, submitted.name, timeout_seconds)
        finished = client.jobs.get(submitted.name)
    except Exception as exc:
        raise AzureMlUnavailable(f"Azure ML job failed: {exc}") from exc

    status = str(getattr(finished, "status", "") or "Unknown")
    if status.lower() != "completed":
        raise AzureMlUnavailable(f"Azure ML job finished as {status}")

    curve = _read_curve(client, submitted.name, model_version=model_version)
    return JobResult(
        curve=curve,
        job_name=str(submitted.name),
        studio_url=str(getattr(finished, "studio_url", "") or ""),
        status=status,
    )


def _wait_for(client: Any, job_name: str, timeout_seconds: int) -> None:
    """Poll until the job leaves a running state, or give up.

    Polling rather than `jobs.stream()`: streaming blocks for as long as the job wants to run,
    and a reviewer is waiting on the other end of this. A timeout has to be enforceable.
    """
    import time

    deadline = time.monotonic() + timeout_seconds
    terminal = {"completed", "failed", "canceled", "cancelled"}
    while time.monotonic() < deadline:
        status = str(getattr(client.jobs.get(job_name), "status", "") or "").lower()
        if status in terminal:
            return
        time.sleep(5)
    raise AzureMlUnavailable(
        f"Azure ML job {job_name} did not finish within {timeout_seconds}s"
    )


def _read_curve(client: Any, job_name: str, *, model_version: str) -> CalibrationCurve:
    """Download the job's `curve.json` output and rebuild the curve from it.

    The parameters are validated on the way in. A job that returned something that is not two
    finite numbers must not become the curve that decides whether a person looks at a case.
    """
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as workdir:
        client.jobs.download(name=job_name, download_path=workdir, output_name="curve")
        matches = list(Path(workdir).rglob("curve.json"))
        if not matches:
            raise AzureMlUnavailable("Azure ML job produced no curve.json")
        body = json.loads(matches[0].read_text(encoding="utf-8"))

    try:
        a = float(body["a"])
        b = float(body["b"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AzureMlUnavailable("Azure ML job returned an unreadable curve") from exc

    curve = CalibrationCurve(
        a=a,
        b=b,
        fitted=bool(body.get("fitted", True)),
        sample_count=int(body.get("sample_count", 0) or 0),
        model_version=model_version or str(body.get("model_version", "")),
    )
    curve.brier_before = float(body.get("brier_before", 0.0) or 0.0)
    curve.brier_after = float(body.get("brier_after", 0.0) or 0.0)

    # The same "do no harm" guard the local fit applies. A remote fit gets no exemption from
    # it: a curve that scores worse than the raw numbers is discarded either way.
    if curve.fitted and curve.brier_after > curve.brier_before > 0:
        logger.warning("azure ml: discarding a fit that scored worse than the raw confidence")
        return CalibrationCurve(model_version=model_version, sample_count=curve.sample_count)
    return curve


__all__ = ["AzureMlUnavailable", "JobResult", "submit_fit", "tracking_uri"]
