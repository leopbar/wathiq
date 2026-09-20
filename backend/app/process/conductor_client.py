"""A small HTTP client for Conductor's REST API.

Only the handful of calls Wathiq needs: register the definitions, start a workflow, poll for
tasks, report a task's result, complete the human task, and read a workflow back. Written
against Conductor OSS 3.15's `/api` endpoints.

Why not the official `conductor-python` SDK: it brings its own threaded worker runtime, and
this application is asyncio from top to bottom. Six endpoints over `httpx` keep one concurrency
model, make the calls easy to read, and mean the fallback engine and the Conductor engine share
the same code for everything except scheduling. The trade-off is recorded in DECISIONS.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

WORKER_ID = "wathiq-worker"


class ConductorError(RuntimeError):
    """Conductor answered, but not with what we asked for."""


class ConductorClient:
    """One client per process. Holds an httpx connection pool."""

    def __init__(self, base_url: str = "", timeout: float | None = None) -> None:
        self.base_url = (base_url or settings.conductor_url).rstrip("/")
        self.timeout = timeout or settings.conductor_timeout_seconds
        self._client: httpx.AsyncClient | None = None

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        client = await self._http()
        response = await client.request(method, path, **kwargs)
        return response

    # -- health ---------------------------------------------------------------

    async def health(self) -> tuple[bool, str]:
        """Whether the server is up, in words that can go straight into the UI."""
        if not self.configured:
            return False, "No Conductor URL is configured."
        probe = settings.conductor_probe_timeout_seconds
        try:
            response = await self._request("GET", "/health", timeout=probe)
            if response.status_code == 200:
                return True, "Conductor is responding."
            # Some builds do not expose /health; asking for the metadata proves as much.
            response = await self._request("GET", "/api/metadata/workflow", timeout=probe)
            if response.status_code == 200:
                return True, "Conductor is responding (metadata API)."
            return False, f"Conductor answered {response.status_code} on /health."
        except Exception as exc:
            return False, f"Conductor is not reachable: {type(exc).__name__}"

    # -- metadata -------------------------------------------------------------

    async def register(
        self, workflow: dict[str, Any], task_defs: list[dict[str, Any]]
    ) -> None:
        """Upsert the task definitions and the workflow definition.

        Idempotent: called every time a worker starts. Conductor keeps definitions itself, and
        registering the same ones again simply overwrites them with the current code's version —
        which is what we want, so the server can never run an older process than the repository
        describes.
        """
        for task_def in task_defs:
            name = task_def["name"]
            existing = await self._request("GET", f"/api/metadata/taskdefs/{name}")
            if existing.status_code == 200:
                response = await self._request("PUT", "/api/metadata/taskdefs", json=task_def)
            else:
                response = await self._request("POST", "/api/metadata/taskdefs", json=[task_def])
            if response.status_code >= 400:
                raise ConductorError(
                    f"Could not register task '{name}': {response.status_code} {response.text}"
                )

        # PUT takes a list and updates or creates, so one call covers both cases.
        response = await self._request("PUT", "/api/metadata/workflow", json=[workflow])
        if response.status_code >= 400:
            raise ConductorError(
                f"Could not register the workflow: {response.status_code} {response.text}"
            )

    async def workflow_registered(self, name: str, version: int) -> bool:
        try:
            response = await self._request(
                "GET", f"/api/metadata/workflow/{name}", params={"version": version}
            )
            return response.status_code == 200
        except Exception:
            return False

    # -- running workflows ----------------------------------------------------

    async def start_workflow(
        self,
        name: str,
        version: int,
        *,
        workflow_input: dict[str, Any],
        correlation_id: str = "",
        idempotency_key: str = "",
    ) -> str:
        """Start a workflow and return its instance id.

        The idempotency key stops a double click, or a retry of the HTTP call itself, from
        creating two workflows for one case. Not every Conductor build accepts those two
        fields, so a rejection is retried without them rather than failing the case — and the
        `postings` table's unique key still makes the money-side step safe either way.
        """
        body: dict[str, Any] = {
            "name": name,
            "version": version,
            "input": workflow_input,
        }
        if correlation_id:
            body["correlationId"] = correlation_id
        if idempotency_key:
            body["idempotencyKey"] = idempotency_key
            body["idempotencyStrategy"] = "RETURN_EXISTING"

        response = await self._request("POST", "/api/workflow", json=body)
        if response.status_code >= 400 and idempotency_key:
            logger.warning(
                "Conductor rejected the idempotency fields (%s); retrying without them",
                response.status_code,
            )
            body.pop("idempotencyKey", None)
            body.pop("idempotencyStrategy", None)
            response = await self._request("POST", "/api/workflow", json=body)
        if response.status_code >= 400:
            raise ConductorError(
                f"Could not start {name}: {response.status_code} {response.text}"
            )
        return response.text.strip().strip('"')

    async def get_workflow(self, workflow_id: str, *, include_tasks: bool = True) -> dict[str, Any]:
        response = await self._request(
            "GET",
            f"/api/workflow/{workflow_id}",
            params={"includeTasks": str(include_tasks).lower()},
        )
        if response.status_code >= 400:
            raise ConductorError(
                f"Could not read workflow {workflow_id}: {response.status_code}"
            )
        return dict(response.json())

    async def terminate(self, workflow_id: str, reason: str) -> None:
        await self._request(
            "DELETE", f"/api/workflow/{workflow_id}", params={"reason": reason}
        )

    # -- tasks ----------------------------------------------------------------

    async def poll(
        self, task_type: str, *, count: int = 1, timeout_ms: int = 1000
    ) -> list[dict[str, Any]]:
        """Long-poll for work. An empty list means there was nothing to do."""
        response = await self._request(
            "GET",
            f"/api/tasks/poll/batch/{task_type}",
            params={
                "workerid": WORKER_ID,
                "count": count,
                "timeout": timeout_ms,
            },
        )
        if response.status_code == 204 or not response.content:
            return []
        if response.status_code >= 400:
            raise ConductorError(f"Poll for {task_type} failed: {response.status_code}")
        payload = response.json()
        return list(payload) if isinstance(payload, list) else []

    async def complete(
        self,
        *,
        workflow_id: str,
        task_id: str,
        output: dict[str, Any] | None = None,
        logs: list[str] | None = None,
    ) -> None:
        await self._update(workflow_id, task_id, "COMPLETED", output or {}, logs)

    async def fail(
        self,
        *,
        workflow_id: str,
        task_id: str,
        reason: str,
        terminal: bool = False,
    ) -> None:
        """Report a failed task.

        `terminal` marks it FAILED_WITH_TERMINAL_ERROR, which tells Conductor not to retry —
        used when retrying cannot possibly help, such as a case that does not exist.
        """
        await self._update(
            workflow_id,
            task_id,
            "FAILED_WITH_TERMINAL_ERROR" if terminal else "FAILED",
            {"reason": reason},
            [reason],
        )

    async def _update(
        self,
        workflow_id: str,
        task_id: str,
        status: str,
        output: dict[str, Any],
        logs: list[str] | None,
    ) -> None:
        body: dict[str, Any] = {
            "workflowInstanceId": workflow_id,
            "taskId": task_id,
            "status": status,
            "outputData": output,
            "workerId": WORKER_ID,
        }
        if logs:
            body["logs"] = [{"log": line} for line in logs]
        response = await self._request("POST", "/api/tasks", json=body)
        if response.status_code >= 400:
            raise ConductorError(
                f"Could not update task {task_id}: {response.status_code} {response.text}"
            )

    async def find_open_task(
        self, workflow_id: str, *, task_type: str
    ) -> dict[str, Any] | None:
        """The waiting task of a given type in a workflow, or None.

        Used to hand a reviewer's decision to the HUMAN task. A HUMAN task sits in SCHEDULED or
        IN_PROGRESS until someone completes it, which is exactly what "the process is waiting
        for a person" means.
        """
        workflow = await self.get_workflow(workflow_id)
        for task in reversed(workflow.get("tasks") or []):
            if task.get("taskType") != task_type:
                continue
            if task.get("status") in ("SCHEDULED", "IN_PROGRESS"):
                return dict(task)
        return None
