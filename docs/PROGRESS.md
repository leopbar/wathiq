# Wathiq — Progress

Plan: [PLAN.md](PLAN.md)

**Current status:** M1 (Foundation) is **complete and verified**. The whole system runs with
`docker compose up --build`; 59 backend tests and 15 Playwright tests pass; lint and gitleaks clean.
**Next step:** M1 commit + PR (awaiting approval), then M2 — the real LangGraph pipeline.

## Section 0 — Setup
- [x] Environment checked (Windows 11, 16 GB RAM, Docker Desktop, Git, GitHub CLI)
- [x] Location decision: Windows drive with polling file watchers (see DECISIONS #17)
- [x] Plan and progress tracker written and agreed
- [ ] GitHub repository created and first push

## M1 — Foundation
- [x] Repo layout, .gitignore, .env.example, .dockerignore per service
- [x] Dockerfiles (multi-stage, non-root, healthchecks) for api, web, e2e
- [x] compose.yaml (dev, hot reload) + compose.prod.yaml (built images, nginx)
- [x] Database: 13 tables, SQLAlchemy 2 async, Alembic initial migration (+ pgvector extension)
- [x] Auth: JWT, bcrypt, 5 roles, RBAC enforced server-side
- [x] Seed: 5 demo users, 5 document types, 6 prompts (9 versions), 30 cases, 96 documents,
      646 fields, 19 findings, 15 review tasks, 332 events, 15 quality runs, calibration curve
- [x] API: 26 endpoints (auth, cases, documents, review, dashboard, quality, prompts, settings,
      audit, system) + SSE stream + OpenAPI
- [x] Backend tests: 59 passing (unit + integration + browser-auth), ruff clean
- [x] GitHub Actions: secret scan, backend, frontend, e2e — all in containers
- [x] Playwright harness + 15 tests (service smoke + full demo flow), all passing
- [x] Design system (tokens, ~25 components), app shell, light/dark, ⌘K palette
- [x] All 10 screens connected to the API, with skeleton / empty / error states
- [x] Typed API client (hand-written from the OpenAPI contract; generator wired via `npm run gen:api`)
- [x] Full-stack run verified screen by screen in a browser
- [x] Docs updated (DECISIONS 21–23 added)
- [ ] Commit + PR (awaiting approval)

### Bugs found and fixed while verifying M1
- Dashboard review queue asked for tasks both *assigned to me* and *unclaimed* — impossible, so it
  always showed "Queue is clear" while 9 tasks waited.
- `/cases/{id}/events` (the SSE stream) had **no authentication at all**.
- Document preview and CSV export could not authenticate at all from the browser.
- `crypto.randomUUID()` in the upload dropzone threw on any non-localhost HTTP origin, silently
  dropping the selected file.
- Vite returned 403 inside Compose because the service hostname was not allowlisted.
- Playwright could not write its report (root-owned folder under a non-root user).

## M2 — Core pipeline (demo mode)
- [ ] Upload + local storage + demo OCR
- [ ] Graph: classify → extract → validate → review gate → finalize
- [ ] Postgres checkpointer + resume on review
- [ ] SSE live progress + stepper
- [ ] Case detail (viewer, highlights, confidence, timeline)
- [ ] Review workspace (queue, SLA timers, actions, reason codes, shortcuts)
- [ ] Milestone checks + docs + commit/PR

## M3 — AI depth
- [ ] Supervisor + parallel workers (Send API)
- [ ] Self-correction (max 2 tries)
- [ ] Critic (actor-critic)
- [ ] ReAct investigator with MCP tools
- [ ] 4 MCP servers, least privilege
- [ ] YAML cross-field rules (versioned)
- [ ] Confidence signals + calibration
- [ ] Guardrails (prompt shield, PII, sanitiser, content safety)
- [ ] RAG policy citations + few-shot selection
- [ ] Milestone checks + docs + commit/PR

## M4 — Process layer
- [ ] Conductor workflow (HUMAN + WAIT tasks)
- [ ] Python workers; workflow ID = thread ID
- [ ] Idempotent core-banking posting
- [ ] Append-only audit trail (table + API done in M1; wire the agent events in M4)
- [ ] SLA escalation
- [ ] Crash-recovery test
- [ ] Milestone checks + docs + commit/PR

## M5 — Quality Lab + Prompt Studio
- [ ] Golden dataset generator
- [ ] Regression cases from reviewer corrections
- [ ] Five test bands (schema + API + UI seeded in M1; real runs in M5)
- [ ] Prompt registry (semver, statuses, diffs, approval) — API done in M1, evals in M5
- [ ] Calibration chart + MLflow
- [ ] CI regression gate
- [ ] Milestone checks + docs + commit/PR

## M6 — Azure mode
- [ ] Foundry / Document Intelligence / Content Safety / AI Search / ADLS / Azure ML / Monitor
- [ ] Entra ID (MSAL) auth
- [ ] Bicep + Helm + teardown script
- [ ] Milestone checks + docs + commit/PR

## M7 — Polish
- [ ] UI/UX refinement pass
- [ ] Arabic / RTL
- [ ] Use case 2 via configuration only (document type + prompt seeded in M1)
- [ ] Failure-mode gallery
- [ ] Final README with screenshots
- [ ] Milestone checks + docs + commit/PR

## Job-description coverage (section 7)
- [ ] LangGraph: supervisor-worker
- [ ] LangGraph: self-reflection
- [ ] LangGraph: actor-critic
- [ ] LangGraph: ReAct
- [ ] LangGraph: HITL interrupts
- [ ] LangGraph: TypedDict state
- [ ] LangGraph: conditional edges
- [ ] Azure AI Foundry extraction with structured outputs
- [~] Per-field confidence (data model, API and calibration curve in place; real signals in M3)
- [~] Pydantic validation (API layer done; model-output validation in M2)
- [~] Prompt management with semver (registry, diffs, approval done; engine pinning in M2)
- [ ] Prompt sensitivity + correctness testing
- [ ] MCP servers, extended for use case 2
- [~] Five test bands (schema, API and seeded results; real suites in M5)
- [ ] Golden + regression datasets
- [~] HITL at mandatory and dynamic points (reason codes and review tasks modelled; interrupts in M2)
- [ ] Conductor wait tasks
- [ ] Checkpoint persistence and resumption
- [ ] Content Safety
- [ ] PII tokenisation
- [ ] Prompt shielding
- [ ] Output sanitisation
- [~] Cross-field validation (rules stored per document type; engine in M3)
- [ ] Orkes Conductor
- [ ] Document Intelligence
- [ ] RAG: chunking, vector indexing, Azure AI Search (pgvector extension enabled in M1)
- [ ] AKS
- [ ] ADLS Gen2 (storage interface + local implementation done)
- [ ] Azure ML
- [ ] Azure Monitor
- [x] Pydantic, FastAPI, TypeScript, REST APIs, JSON schema
- [x] Git, CI/CD
- [ ] Failure-mode analysis

Legend: `[x]` done · `[~]` partly done, finished in a later milestone · `[ ]` not started.

## Docs (section 11)
- [x] SYSTEM_OVERVIEW.md
- [x] ARCHITECTURE.md
- [x] DECISIONS.md
- [x] GLOSSARY.md
- [ ] DEMO_SCRIPT.md (M7, drafted after the UI is final)
- [ ] Explanation notes (kept privately, not published)
- [x] README.md (screenshots added in M7)
- [x] API.md, DESIGN.md
