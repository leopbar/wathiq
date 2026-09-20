# Wathiq — Progress

Plan: [PLAN.md](PLAN.md)

**Current status:** M2 (Core pipeline) is **complete and verified**. A document uploaded through
the UI is read, classified, extracted, validated and either completes on its own or stops at the
review gate for a person; a reviewer's decision resumes the graph from its PostgreSQL checkpoint.
86 backend tests and 17 Playwright tests pass; ruff and typecheck clean.
**Next step:** M2 commit + PR (awaiting approval), then M3 — AI depth.

## Section 0 — Setup
- [x] Environment checked (Windows 11, 16 GB RAM, Docker Desktop, Git, GitHub CLI)
- [x] Location decision: Windows drive with polling file watchers (see DECISIONS #17)
- [x] Plan and progress tracker written and agreed
- [x] GitHub repository created and first push (`leopbar/wathiq`)

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
- [x] Commit pushed to `m1-foundation` and `main`; all four CI jobs green
- [x] No pull request for M1: `main` was created from this same commit, so a PR would be empty.
      Milestones from M2 onwards branch off `main` and are merged through a PR.

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
- [x] Upload + local storage + demo OCR (reads the PDF text layer; says so honestly for images)
- [x] Graph: ocr → classify → extract → validate → review gate → finalize, with one conditional
      edge and `interrupt()` at the gate
- [x] PostgreSQL checkpointer (`langgraph-checkpoint-postgres`); a reviewer's decision resumes
      the graph from the checkpoint
- [x] Deterministic demo extractor and classifier — no model call, no network, reproducible
- [x] Cross-field rule engine reading the rules stored on the document type (configuration,
      not engine code)
- [x] SSE live progress: event-log rows mapped to stepper frames, with a `waiting` state for a
      case parked at the review gate
- [x] Review workspace wired to the real pipeline: claim, approve, correct, reject, escalate
- [x] Backend tests: 86 passing (20 agent unit + 7 pipeline integration added), ruff clean
- [x] Playwright: 17 passing (two new tests run a real PDF through the whole pipeline)
- [~] Case detail: viewer, confidence, findings and timeline are live. **Field highlighting is
      not done** — the demo extractor has no bounding boxes, so the UI honestly says "no source
      region". Real coordinates arrive with Document Intelligence in M3/M6.
- [ ] Synthetic bilingual (Arabic) document generator — base-14 PDF fonts cannot encode Arabic;
      moved to M5 with the golden dataset
- [ ] Milestone checks + docs + commit/PR

### Bugs found and fixed while building M2
- Re-running the rules on resume recreated findings as `open`, silently undoing a reviewer's
  resolution. Findings now carry their previous status over by rule code.
- The cross-document name rule scored "Al Noor Trading LLC" against "Al Noor Trading L.L.C." at
  0.5 similarity, because punctuation was turned into spaces and split `L.L.C.` into three
  tokens. Punctuation is now deleted rather than replaced.
- The SSE stream tested a case status it had read once before the loop, so it never noticed the
  pipeline finishing and always ran to its poll limit.
- Case detail never refreshed, so a case opened mid-run sat on a stale "Processing" until the
  user reloaded. It now polls only while the case is actually moving.
- The "What happens next" panel on New case listed guardrails, a supervisor and self-correcting
  workers — all M3 work that does not exist yet. It is now driven by the same step list the
  stepper uses, so it cannot describe a pipeline we do not run.

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
- [x] LangGraph: HITL interrupts
- [x] LangGraph: TypedDict state
- [x] LangGraph: conditional edges
- [ ] Azure AI Foundry extraction with structured outputs
- [~] Per-field confidence (real per-field scores from the extractor; calibration in M3)
- [~] Pydantic validation (API layer done; model-output validation lands with the real model in M6)
- [~] Prompt management with semver (registry, diffs, approval done; engine pinning in M2)
- [ ] Prompt sensitivity + correctness testing
- [ ] MCP servers, extended for use case 2
- [~] Five test bands (schema, API and seeded results; real suites in M5)
- [ ] Golden + regression datasets
- [x] HITL at mandatory and dynamic points (mandatory and dynamic review tasks both created)
- [ ] Conductor wait tasks
- [x] Checkpoint persistence and resumption
- [ ] Content Safety
- [ ] PII tokenisation
- [ ] Prompt shielding
- [ ] Output sanitisation
- [x] Cross-field validation (rules stored per document type; engine runs in M2)
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
