"""Optional MLflow REST tracking. No document text or identifiers leave the API.

Local fit attempts are persisted even if tracking is disabled or unavailable.
"""

import time

import httpx

from app.core.config import settings


async def track_fit(result: dict) -> dict:
    if not settings.mlflow_tracking_uri:
        return {"status": "disabled", "reason": "Enable the ml profile to track experiments."}
    try:
        async with httpx.AsyncClient(base_url=settings.mlflow_tracking_uri, timeout=3) as client:
            base = "/api/2.0/mlflow/"
            response = await client.get(
                base + "experiments/get-by-name", params={"experiment_name": "wathiq-calibration"}
            )
            if response.status_code == 404:
                response = await client.post(
                    base + "experiments/create", json={"name": "wathiq-calibration"}
                )
                response.raise_for_status()
                experiment_id = response.json()["experiment_id"]
            else:
                response.raise_for_status()
                experiment_id = response.json()["experiment"]["experiment_id"]
            response = await client.post(
                base + "runs/create",
                json={
                    "experiment_id": experiment_id,
                    "start_time": int(time.time() * 1000),
                    "tags": [
                        {"key": "scope", "value": "training diagnostics, not held-out accuracy"}
                    ],
                },
            )
            response.raise_for_status()
            run_id = response.json()["run"]["info"]["run_id"]
            response = await client.post(
                base + "runs/log-batch",
                json={
                    "run_id": run_id,
                    "metrics": [
                        {
                            "key": key,
                            "value": float(value),
                            "step": 0,
                            "timestamp": int(time.time() * 1000),
                        }
                        for key, value in result.items()
                        if isinstance(value, (int, float))
                    ],
                    "params": [
                        {"key": "model_version", "value": result["model_version"]},
                        {"key": "commit", "value": settings.build_sha},
                    ],
                },
            )
            response.raise_for_status()
            response = await client.post(
                base + "runs/update",
                json={
                    "run_id": run_id,
                    "status": "FINISHED",
                    "end_time": int(time.time() * 1000),
                },
            )
            response.raise_for_status()
            return {"status": "tracked", "run_id": run_id, "experiment_id": experiment_id}
    except (httpx.HTTPError, KeyError, ValueError):
        return {
            "status": "unavailable",
            "reason": "Local fit saved; MLflow did not acknowledge it.",
        }
