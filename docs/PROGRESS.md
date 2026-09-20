# Wathiq — Progress

Plan: [PLAN.md](PLAN.md)

**Current status:** M3 (AI depth) is **complete and verified**. The graph now runs guardrails, a
supervisor that dispatches one worker per document in parallel, self-correcting extraction, an
actor-critic challenge, a bounded ReAct investigator calling four MCP tool servers, and a
validator using versioned YAML rules with retrieved policy citations and calibrated confidence.
183 backend tests, 24 MCP server tests and 22 Playwright tests pass; ruff, eslint and typecheck
are clean; the whole stack starts from a wiped volume.
**Next step:** M4 — process layer (Conductor), on branch `m4-process-layer`.

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
- [x] Milestone checks: clean `docker compose down -v` + `up --build`, all suites re-run
- [x] Docs updated (ARCHITECTURE section 3 split into "runs today" vs "planned"; DECISIONS 27-33)
- [x] Commit `852bf97`, PR #1 merged into `main`, CI green

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
- [x] Supervisor + parallel workers (Send API), one worker per document
- [x] Self-correction on Pydantic validation errors (max 2 repairs, each one recorded)
- [x] Critic (actor-critic): grounding, shape and wrong-label checks, via the document-store MCP
      server where it is reachable
- [x] ReAct investigator with MCP tools: screening every named party, reconciling names across
      documents, bounded at 6 steps
- [x] 4 MCP servers (official Python SDK 2.2, streamable HTTP), least privilege enforced twice:
      by separate processes, and by an allowlist per graph node
- [x] YAML rule packs, versioned per document type, with a named-check escape hatch and a
      `when:` guard; the pack version that judged a case is recorded on the case
- [x] Confidence from five signals + Platt calibration fitted on reviewer decisions, with a
      guard that refuses a fit worse than doing nothing
- [x] Guardrails: prompt shield, PII tokenisation, output sanitiser, content safety — all four
      run before anything reads a document
- [x] RAG over a synthetic policy pack in pgvector: real policy citations on findings, and
      few-shot example selection for the extraction prompt
- [x] Backend tests: 183 passing (was 86); MCP servers: 24 passing in their own suite
- [x] Playwright: 22 passing (5 new, covering injection, the assurance panel, signals,
      least privilege and calibration honesty)
- [x] Case screen: an Assurance tab reading the agent's own checkpoint; per-field "why this
      confidence" breakdown
- [x] Settings: an Assurance tab generated from the running code (guardrails, signal weights,
      tool servers, rule packs, policy corpus)
- [x] Quality Lab: the calibration curve's state, its ground truth, and a "refit" action
- [x] Milestone checks: clean `docker compose down -v` + `up --build`, every suite re-run
- [x] Docs updated (ARCHITECTURE section 3 rewritten to the live graph, 4b added for RAG;
      DECISIONS 34–45; GLOSSARY "Added in M3")

### Bugs found and fixed while building M3
- **The pipeline read the PII-tokenised copy of each document**, so every date arrived as
  `<DOB_1>` and no date field extracted. The guardrails now produce two clearly named copies:
  `clean_text` for the pipeline, `log_text` for logs. (DECISIONS #34)
- **Every case stopped before its first node, silently.** Read-only API requests left
  connections *idle in transaction*, which blocked the checkpointer's `CREATE INDEX
  CONCURRENTLY` forever on a fresh database. Latent since M1; only visible once the volumes
  were wiped. (DECISIONS #44)
- **Calibration never turned on.** The gradient descent was under-converged, produced a curve
  worse than the raw scores, and the "do no harm" guard correctly discarded it — so the symptom
  was silence. (DECISIONS #35)
- **A date repair could invent a value.** Searching the whole page for a date put the issue date
  into the expiry field. Repairs now look only under the field's own label. (DECISIONS #42)
- **The Assurance panel froze on a half-finished run**, showing "0 steps" for a run that did six,
  because it fetched once on mount. It now follows the case and refetches when it settles.
- **A licence that expired in 2019 also reported "expires within 30 days".** Rules can now carry
  a `when:` guard so they only apply in the state they make sense in.
- **The investigator raised a finding on every clean case** ("screening clear"), which teaches a
  reviewer to ignore the findings panel. Positive results now go to the timeline, which is the
  audit trail, and the panel keeps what needs attention.
- **Name matching missed transliterations.** Token overlap scored "Youssef Karam" against
  "Youssef Karem" at 0.33 and would have missed a real screening match; character similarity is
  now combined with it.

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
- [x] LangGraph: supervisor-worker (Send API, one worker per document)
- [x] LangGraph: self-reflection (repairs on Pydantic errors, capped at 2)
- [x] LangGraph: actor-critic (independent grounding, shape and label checks)
- [x] LangGraph: ReAct (bounded loop, MCP tools, thought/action/observation recorded)
- [x] LangGraph: HITL interrupts
- [x] LangGraph: TypedDict state
- [x] LangGraph: conditional edges
- [ ] Azure AI Foundry extraction with structured outputs
- [x] Per-field confidence from five signals, calibrated with Platt scaling on reviewer outcomes
- [x] Pydantic validation (models built at runtime from the document type's schema; the same
      schema is the structured-output contract in M6)
- [~] Prompt management with semver (registry, diffs, approval done; engine pinning in M2)
- [ ] Prompt sensitivity + correctness testing
- [x] MCP servers: 4 servers, least privilege per node
- [~] MCP servers extended for use case 2 (the same servers serve it; salary-specific tools in M7)
- [~] Five test bands (schema, API and seeded results; real suites in M5)
- [ ] Golden + regression datasets
- [x] HITL at mandatory and dynamic points (mandatory and dynamic review tasks both created)
- [ ] Conductor wait tasks
- [x] Checkpoint persistence and resumption
- [~] Content Safety (local term-list stand-in, clearly labelled; Azure service in M6)
- [x] PII tokenisation (7 recognisers; only the tokenised copy may reach a log)
- [x] Prompt shielding (instruction patterns, invisible characters, bidi overrides, encoded blobs)
- [x] Output sanitisation (markup, scripts, control and bidi characters, length cap)
- [x] Cross-field validation (versioned YAML rule packs, six expression shapes, named checks)
- [ ] Orkes Conductor
- [ ] Document Intelligence
- [~] RAG: chunking and vector indexing in pgvector, citations live; Azure AI Search in M6
- [ ] AKS
- [ ] ADLS Gen2 (storage interface + local implementation done)
- [ ] Azure ML
- [ ] Azure Monitor
- [x] Pydantic, FastAPI, TypeScript, REST APIs, JSON schema
- [x] Git, CI/CD
- [~] Failure-mode analysis (bugs and their causes recorded per milestone; the gallery is M7)

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
