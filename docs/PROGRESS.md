# Wathiq — Progress

Plan: [PLAN.md](PLAN.md)

**Current status:** M4 (process layer) is **complete and verified** on branch `m4-process-layer`.
Orkes Conductor now runs the business process — intake, the agent task, a HUMAN task with an SLA
timer beside it, idempotent posting and an audit seal — and an in-process engine walks the same
steps when Conductor is switched off. The Conductor workflow id is the LangGraph thread id. 221
backend tests, 26 MCP server tests and 30 Playwright tests pass; ruff, eslint and typecheck are
clean; the whole stack starts from a wiped volume with the `process` profile on.
**Next step:** M5 — Quality Lab + Prompt Studio.

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
      still not done** — neither the demo extractor nor M3's workers produce bounding boxes, so
      the UI honestly says "no source region". Real coordinates arrive with Document
      Intelligence in M6. M3 did add the next best thing: each field now shows the signals its
      confidence was built from, including whether the value was found in the document at all.
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
  workers, none of which existed at the time. It was rewritten to read the same step list the
  stepper uses, so it cannot describe a pipeline we do not run. (M3 has since built all three,
  and they appeared in the panel the moment the step list grew — which is the point.)

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
      DECISIONS 34–45; GLOSSARY "Added in M3"; API and README)
- [x] CI: a new `mcp` job, and the backend and e2e jobs now start the tool servers — without
      them the agent records "could not check", which is a different outcome from the one
      under test
- [x] Commits `576e358` and `70e25a1`, PR #2 merged into `main` (`4c48548`), all five CI jobs
      green on both the push and the pull-request trigger

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
- **A dashboard test failed in CI and passed locally.** Diagnosed first as a timing flake and
  given a longer timeout, which was wrong: "Straight-through" appears three times on the
  dashboard, so the assertion hit a Playwright strict-mode violation the moment the charts
  rendered. The KPI block is now a `<section>` with an accessible name — a landmark for screen
  readers as well as a stable anchor for the test.

## M4 — Process layer
- [x] Conductor workflow `wathiq_kyc_refresh` v1: intake → agent → SWITCH → (FORK: HUMAN task +
      WAIT timer → escalate | JOIN on the review alone → apply decision) → post → audit
- [x] The workflow is declared once as data (`process/definition.py`); the Conductor JSON, the UI
      step list and the About diagram are all generated from it, and a test proves they agree
- [x] Python task workers polling six queues, in the same image as the API (so the reasoning code
      is identical), with hot reload in dev and a clean SIGTERM shutdown
- [x] Second engine: an in-process runner calling the *same* step functions, for a machine without
      2 GB to spare. `WATHIQ_PROCESS_ENGINE=auto|conductor|inprocess`
- [x] Every case records which engine ran it; a decision always goes back to that engine
- [x] Workflow ID == LangGraph thread ID, applied by the intake step before anything needs it
- [x] Idempotent core-banking posting: key derived from the workflow, enforced by a UNIQUE column
      *and* by the simulated system of record; a skip is always recorded with its reason
- [x] Straight-through cases post under a named policy, never under a person's name
- [x] SLA escalation: unclaimed work moves to the supervisor queue, claimed work stays with its
      reviewer, `escalated_at` makes it happen once. The reviewer queue now filters on
      `assigned_role`, so an escalated task really does leave their list
- [x] Append-only audit trail enforced by a PostgreSQL trigger, with an integrity endpoint that
      also states what the check does not prove
- [x] Crash recovery: Conductor redelivers (the agent step *continues* the graph rather than
      restarting it); the fallback sweeps for stuck cases at startup. Verified on live containers
      in both shapes — with the posting row surviving, and with it lost
- [x] Case screen: a Process tab reading the case's own event log, with the posting, the
      idempotency key and Conductor's own view of the instance beside it
- [x] Settings: a Process tab with both engines' health, the generated workflow diagram, the step
      list, the SLA rule and a supervisor-only "run the SLA check now"
- [x] Backend tests: 221 passing (38 new); MCP servers: 26 (2 new); Playwright: 30 (8 new)
- [x] Milestone checks: clean `docker compose --profile process down -v` + `up --build`, every
      suite re-run, the UI walked screen by screen
- [x] Docs updated (ARCHITECTURE 2 rewritten and 2b added; DECISIONS 46–57; GLOSSARY "Added in
      M4"; API.md process endpoints; README)
- [ ] Commit, push and PR

### Bugs found and fixed while building M4
- **The case screen stopped polling one step early.** `completed` now means "posted and sealed",
  so a case passes through `approved` and `posting` on its way there — statuses the detail screen
  did not treat as "still moving". It sat on "Approved" until the page was reloaded. The same
  omission was in the SSE stream's list of moving statuses.
- **Escalation changed a label and nothing else.** The review queue filtered on `assigned_to_id`
  but never on `assigned_role`, so a task escalated to a supervisor stayed in the reviewer's list.
- **The append-only trigger broke reseeding.** `clear_all` deleted from every table, which the
  trigger correctly refused. It now uses `TRUNCATE` — which needs table-owner rights and empties
  the table completely, so it cannot be used to alter one record. (DECISIONS #55)
- **SQLAlchemy could not compile the trigger's SQL.** `RAISE EXCEPTION '... % ...'` uses a
  per-cent sign, which the `DDL` construct treats as its own substitution. The message is now
  built by concatenation.
- **Conductor refused the HUMAN task definition**: `responseTimeoutSeconds: 0` is rejected even
  for a task no worker polls. It is 30 days now, with `ALERT_ONLY` so reaching it only logs.
- **The Conductor workflow never reached COMPLETED after a review.** The SLA branch was still
  sitting in its `WAIT`, so the instance stayed RUNNING for the rest of the window. Completing the
  human task now also releases that timer — in that order, so the escalation step that follows
  sees a review that is already closed.
- **The human step stayed "waiting" for ever** in the process view: nothing recorded that it had
  finished. The decision step now closes it, the timer and the join explicitly.
- **The worker ran stale code for half an hour.** It had no hot reload, unlike the API, so a change
  to a step was silently not running. It now starts under `watchfiles` in dev.
- **Conductor's healthcheck could never pass**: the standalone image has no `curl`. The worker
  waits for that healthcheck, so it would have waited for ever.

## M5 — Quality Lab + Prompt Studio
Scope agreed before starting, so a fresh session does not have to re-derive it.

- [ ] **Golden dataset generator** — synthetic documents at known quality levels (clean, blurry,
      cropped, wrong type, missing field) each with an answer key, so "is extraction still good?"
      has a definite answer rather than an impression
- [ ] **Bilingual (Arabic) document generator** — carried over from M2. Base-14 PDF fonts cannot
      encode Arabic, so this needs an embedded font; it belongs with the golden set
- [ ] **Regression cases from reviewer corrections** — every field a reviewer corrected becomes a
      permanent test case. This is the loop that makes the system improve rather than just age
- [ ] **Five test bands made real** (model, prompt, agent, AI security, adversarial) — the schema,
      API and seeded results exist from M1; M5 makes them suites that run from the Quality Lab
      screen *and* in CI
- [ ] **Prompt Studio finished** — eval results linked to a prompt version, prompt *sensitivity*
      testing (does rewording change the answer?) and correctness testing. The registry, semver
      and approval flow are already done
- [ ] **Calibration chart + MLflow** — MLflow as a new compose service behind the `ml` profile,
      tracking each calibration fit as an experiment
- [ ] **CI regression gate** — the piece that makes the rest matter: a pull request that makes
      extraction worse fails
- [ ] Milestone checks + docs + commit/PR

**The risk to watch in this milestone.** M5 is where it is easiest to build something that *looks*
like assurance and is not: an eval that cannot fail, a gate that never fires, a score computed over
eight samples and presented as if it meant something. Every number this milestone produces needs to
say how many samples it rests on, and every suite needs a case that is known to fail so we can see
the gate work. The value here is in judgment, not in lines of code.

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
- [x] Conductor wait tasks (a WAIT task beside the human task, as the SLA timer)
- [x] Checkpoint persistence and resumption (and crash recovery: redelivery under Conductor,
      a startup sweep under the fallback)
- [~] Content Safety (local term-list stand-in, clearly labelled; Azure service in M6)
- [x] PII tokenisation (7 recognisers; only the tokenised copy may reach a log)
- [x] Prompt shielding (instruction patterns, invisible characters, bidi overrides, encoded blobs)
- [x] Output sanitisation (markup, scripts, control and bidi characters, length cap)
- [x] Cross-field validation (versioned YAML rule packs, six expression shapes, named checks)
- [x] Orkes Conductor (workflow with HUMAN/WAIT/FORK-JOIN/SWITCH, Python task workers)
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
