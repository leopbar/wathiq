# Wathiq — Build Plan

Progress: [PROGRESS.md](PROGRESS.md)

**Timeline:** ~28 hours of build time across seven milestones.
**Golden rule:** the whole system runs at the end of every milestone. Thin everywhere first, then deep.
If time runs short, M6 (Azure mode) and M7 depth are cut first — M1–M5 give a complete demo.

## Services (docker compose)

| Service | What it does | Profile |
|---|---|---|
| `db` | PostgreSQL 16 + pgvector (app data, LangGraph checkpoints, vectors) | default |
| `api` | FastAPI backend: REST, SSE, auth, LangGraph engine | default |
| `worker` | Conductor Python workers (call into the engine) | default |
| `mcp-*` | 4 MCP servers: document-store, company-registry, sanctions, core-banking | default |
| `web` | React + Vite frontend (dev: Vite HMR; prod: nginx) | default |
| `conductor` | Conductor OSS server + UI | `process` (on by default, can be switched off) |
| `mlflow` | Experiment tracking for the calibration model | `ml` |
| `e2e` | Playwright tests (official image) | `test` |

Low-RAM fallback: with the `process` profile off, an in-process workflow runner implements the same
`ProcessEngine` interface, so the demo still works end to end.

## M1 — Foundation (≈5 h)
- Monorepo layout: `backend/`, `frontend/`, `mcp_servers/`, `workers/`, `infra/`, `e2e/`, `docs/`.
- `.gitignore`, `.env.example`, `.dockerignore` everywhere; git init; GitHub repo (after approval).
- Multi-stage Dockerfiles (non-root, healthchecks); `compose.yaml` + `compose.dev.yaml` (hot reload,
  polling watchers for Windows) + `compose.prod.yaml`.
- Backend: FastAPI app, settings (`WATHIQ_MODE=demo|azure`), SQLAlchemy models, Alembic, JWT auth,
  5 roles with RBAC, health endpoint, OpenAPI.
- Seed: 5 demo users, document types, ~30 synthetic cases across all statuses, audit entries.
- Frontend: design system (tokens, typography, components), app shell, light/dark, all 10 screens
  wired to the API with skeletons/empty/error states, typed API client from OpenAPI.
- GitHub Actions skeleton: build images, lint, unit tests in containers, gitleaks.

## M2 — Core pipeline, demo mode (≈4 h)
- Upload (drag-and-drop) → storage adapter (local folder) → demo OCR → LangGraph:
  classify → extract → validate → review gate (`interrupt()`) → finalize.
- Postgres checkpointer; reviewer decision resumes the graph.
- SSE live progress + pipeline stepper; case detail (viewer, fields, confidence, timeline).
- Review workspace: queue, SLA timers, approve/correct/reject, reason codes, keyboard shortcuts.
- Synthetic document generator (bilingual PDFs) for demo uploads.

## M3 — AI depth (≈5 h)
- Supervisor + parallel workers (Send API); self-correction on Pydantic errors (max 2).
- Critic node (actor-critic); ReAct investigator with MCP tools via langchain-mcp-adapters.
- 4 MCP servers (official Python SDK), least-privilege tool sets per node.
- Versioned YAML cross-field rules; per-field confidence signals + calibration (scikit-learn).
- Guardrails: prompt shield heuristic, Presidio + UAE recognizers, output sanitiser, content safety.
- RAG over synthetic policy docs (pgvector): policy citations + few-shot example selection.

## M4 — Process layer (≈3.5 h)
- Conductor workflow: intake → guardrails → agent task → HUMAN task + WAIT (SLA) → post → audit.
- Python workers; workflow ID = LangGraph thread ID.
- Idempotent core-banking posting; append-only audit trail; SLA escalation to Supervisor.
- Crash-recovery test: kill the worker mid-case, restart, case resumes from checkpoint.

## M5 — Quality Lab + Prompt Studio (≈4 h)
- Golden dataset generator (quality levels, answer keys); regression cases from reviewer corrections.
- Five test bands (model, prompt, agent, AI security, adversarial) runnable from UI and CI.
- Prompt registry: semver, draft/approved/retired, diffs, linked eval results, Admin approval.
- Calibration chart; MLflow tracking; CI gate that blocks regressions.

## M6 — Azure mode (≈3 h, code only unless you approve resources)
- Adapters behind config: Foundry models, Document Intelligence, Content Safety + Prompt Shields,
  AI Search, ADLS Gen2, Azure ML job, Azure Monitor (OpenTelemetry), Entra ID (MSAL).
- Bicep (ACR, AKS, Postgres Flexible, Storage, Key Vault, Monitor), Helm chart, teardown script.
- Cost estimate shown to you before anything is created.

## M7 — Polish (≈3.5 h)
- UI/UX refinement pass with screenshots; Arabic/RTL toggle.
- Use case 2 (salary certificates) purely via config: schema, prompt, rules, golden set, MCP extension.
- Failure-mode gallery; final README with screenshots; demo script complete.

## Every milestone ends with
Tests in containers → full stack up → Playwright demo flow → screenshots + UI fixes → docs →
commit (approval) → push + PR (approval) → a short written summary of what changed.
