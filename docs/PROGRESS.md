# Wathiq — Progress

Plan: [PLAN.md](PLAN.md)

**Current status:** M7 (polish) is complete on `codex/m7-polish`, awaiting commit and PR
approval; M6 (Azure mode) is committed at `0683dfc` on the same branch. M7 finished the bilingual
Arabic/RTL interface across every screen, made the second use case configuration-driven through
case-type profiles, and added the failure-mode gallery, the README screenshots and the demo script.

**Verified:** 326 backend tests, 34 MCP, 44 Playwright (plus an opt-in screenshot spec); ruff,
eslint, tsc and the production
build clean. Bicep compiles with zero warnings; the default in-process Helm release renders 16
resources (15 schema-valid, 1 CRD supplied by the AKS add-on); shellcheck clean. A test proves
demo mode loads no Azure SDK, and another runs every staged failure through the real pipeline.

**Protecting the existing system:** this subscription runs a live application in `filingsiq-rg`.
Wathiq never touches it — resource-group scope, an exact-match allow-list in both scripts, its own
copy of every service, and model SKUs chosen against *measured* quota so they draw on pools the
existing system does not use. The teardown guard is tested against `filingsiq-rg` and refuses it.

**Live now:** `rg-wathiq-dev` is deployed on AKS. Public login, a complete real-Azure case
(`WTQ-2026-0031`), checkpoint assurance, and an ADLS SAS document fetch all passed. The resource
group remains intentionally live because development is continuing in Azure.

**Remaining:** commit, push and the M6+M7 pull request, all of which need the user's approval.
Azure teardown is deferred until development in Azure finishes.

**Two things deliberately not claimed.** Azure AI Search is written and tested but **not
deployed** — the free tier belongs to the other system and Basic costs ~USD 74/month to replace a
working pgvector retriever. Entra **browser sign-in** is not built: the API validates Entra tokens
today and that is tested, but the OIDC redirect leg needs an app registration this demo does not
have, and the login screen says so instead of showing a button that cannot finish.

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
- [x] Synthetic bilingual (Arabic) document generator — base-14 PDF fonts cannot encode Arabic;
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

- [x] Golden generator: 50 PDFs, five document types, clean/blurry/cropped/wrong-type/missing-field
      conditions, independent answer keys, authenticated ZIP download
- [x] Bilingual Arabic labels with an embedded shaped font; PDF rendered and visually checked.
      Values are synthetic English strings. Blurry PDFs test abstention, not optical recognition.
- [x] Reviewer corrections copied into permanent input/schema/answer snapshots and replayed in the
      agent band; export to a checked-in JSON fixture lets CI use the same synthetic examples
- [x] Five real diagnostic bands runnable from Quality Lab and CI; measured provenance and sample
      counts, illustrative seed runs excluded from the summary, every band has a negative control
- [x] Prompt-version diagnostics and history with body hash; evaluation does not approve a version
- [~] Prompt sensitivity: harness compares wording variants and detects both unstable answers and
      stable wrong answers. Live model experiments await Foundry in M6; demo mode explicitly says
      unsupported, zero samples, no claimed robustness score
- [x] Calibration Brier corrected to use individual outcomes, rejected cases excluded from positive
      labels, chart marked as training diagnostics, every fit attempt persisted
- [x] Optional MLflow service behind `ml`, non-root, persistent storage, port 5001; real fit tracked,
      unavailable service leaves local fitting usable and reports tracking failure honestly
- [x] CI gate rejects any failed diagnostic; negative-control command must exit 1; a separate test
      breaks the actual extractor and proves the golden set detects it
- [x] Verification: 235-test full backend run plus added Brier regression test; 15 focused M5 tests,
      26 MCP and 33 Playwright tests pass; ruff/eslint/typecheck/production build clean
- [x] Fresh and upgrade migrations verified without wiping the user's development database
- [x] Documentation, clean full browser run (no retries), screenshot review and secret scan
- [x] Milestone commit approved by the user
- [ ] Push/PR approval

Implementation and limits: [QUALITY.md](QUALITY.md). CI reads the committed correction export,
not the developer's live database. No real customer data belongs in that export.

### Bugs found while building M5
- Arabic label normalisation deleted all Arabic letters, collapsing different labels into one key.
  The extractor, repair worker and critic now preserve Unicode letters.
- The results drawer read `status` although the API returns `passed`, displaying successes as failures.
- The evaluation button returned a seeded run instead of running anything.
- The displayed Brier score used squared chart-bin gaps instead of individual binary outcomes.
- A refused refit left the old curve active in PostgreSQL while process memory said raw confidence.
- The worker inherited an HTTP healthcheck although it is a queue-polling process with no HTTP server.

## M6 — Azure mode

Every item is behind an interface that already existed in M1–M5 and is switched on by
`WATHIQ_MODE=azure` **plus that service's own endpoint**. An empty endpoint is a normal state, not
a broken one: the demo implementation keeps running and Settings → Azure names which one answered.
Demo mode is unchanged and still loads no Azure SDK at all — asserted by a test, not assumed.

### A — Model provider (Azure AI Foundry)
- [x] `FoundryExtractor` implementing the same `ExtractorBackend` as `DemoExtractor`
- [x] Structured outputs in **strict mode**, using the very schema `agent/schema.py` already built
      the Pydantic validator from — one definition, two jobs, proven equal by a test
- [x] The model returns values only; each one is then **looked up in the document**. A value that
      cannot be found carries no source line and zero confidence, so the grounding signal collapses
      and the field goes to a person (DECISIONS #66)
- [x] The registry's prompt body and the few-shot examples now reach the model. The supervisor
      loads the pinned prompt version once per case; workers no longer touch the database
- [x] Truncation (`finish_reason=length`) and content-filter refusals raise rather than parsing
      half an object
- [x] `FoundryEmbedder` asking for 256 dimensions, so it drops into the existing `vector(256)`
      column with no migration, renormalised because a shortened vector is no longer unit length
- [x] Azure Prompt Shields and Content Safety **combined with** the local detectors, never
      replacing them; either one flagging wins, and "could not check" is a recorded third state
- [~] Sensitivity harness: the interface now accepts a real prompt, so a Foundry-backed predictor
      can be passed in. **No wording-sensitivity score is published** — that needs a measured run
      against the live model, which has not been done. Demo mode still says "unsupported"

### B — Document Intelligence
- [x] `DocumentIntelligenceOcr` implementing the existing `OcrBackend`, calling `prebuilt-layout`
- [x] **Bounding boxes, end to end at last.** `OcrResult` carries `line_boxes`; `agent/geometry.py`
      joins a value to the line it was printed on by *text*, not line number (the guardrails rewrite
      the text between OCR and extraction); the worker writes the box; the viewer already drew it
- [x] It never guesses: no match means `bbox = None` and the UI goes on saying "no source region"
- [x] A value wrapped across lines is unioned from a distinctive seed plus *adjacent* fragments —
      found by a test that caught the first version dropping "LLC"
- [x] Sixth confidence signal `read`: how sure the engine was of *this value's* characters, as
      distinct from the page. `combine()` re-normalises, so demo scores are bit-identical to M5
- [x] Demo OCR stays the default and reports no geometry rather than inventing any

### C — Azure AI Search (RAG)
- [x] `azure/search.py`: index creation, hybrid keyword + vector query, citation lookup by filter
- [x] The fused rank score is **not** treated as a cosine similarity; the cosine is recomputed
- [~] **Deliberately not deployed.** The free tier in this subscription belongs to another system,
      and Basic is ~USD 74/month to replace a pgvector retriever that already returns real
      citations. `deployAiSearch=false`; pgvector stays live (DECISIONS #71)

### D — ADLS Gen2 (storage)
- [x] `AdlsStorage` implementing the existing `StorageBackend`, hierarchical namespace
- [x] Short-lived read-only SAS signed with a **user delegation key**, so the signature is
      traceable to an identity rather than to an anonymous account key
- [x] `StorageBackend.signed_url()` returns `None` for a local folder — the honest answer — and the
      document endpoint then streams the bytes exactly as it has since M1
- [x] Local folder stays the default

### E — Azure ML (calibration)
- [x] `azure/ml.py` submits the fit as a command job, polls with an enforceable timeout and reads
      `curve.json` back
- [x] `app/quality/fit_job.py` is the job entry point and calls the **same** `calibration.fit()` —
      no second implementation of Platt scaling anywhere
- [x] The "do no harm" guard is applied to the remote result too
- [x] The workspace's own MLflow URI is exposed, so M5's tracking moves to Azure with no code change
- [x] Local fitting stays the default

### F — Azure Monitor (observability)
- [x] OpenTelemetry export, configured at startup, off without a connection string
- [x] `span()` is a no-op context manager when tracing is off, so no call site has to ask
- [x] Spans cover every graph node (wrapped once where nodes are registered, so a node added later
      is traced by construction), every MCP tool call and every guardrail decision
- [x] Ids, verdicts and counts only — never document text or field values
- [x] An exception inside a span is recorded and then re-raised untouched

### G — Entra ID / MSAL (auth)
- [x] Entra token validation behind the existing auth dependency: JWKS by `kid`, RS256 only,
      audience, issuer, `exp`/`nbf` — each check is a real attack if skipped
- [x] App roles map to Wathiq's five roles; the most privileged wins; **an unrecognised role is
      refused, not downgraded**
- [x] Just-in-time provisioning with an unusable password hash, and the role rewritten from the
      token on every sign-in so removing it in Entra takes access away
- [x] `GET /auth/config` (unauthenticated, no secrets) so the login screen can offer what exists
- [~] **The browser sign-in flow is not built.** The API accepts an Entra bearer token today and
      that is tested; the OIDC redirect leg needs an app registration with this origin as a
      redirect URI, which this demo does not have. The login screen says exactly that rather than
      showing a button that cannot finish. PROGRESS previously claimed this page already had a
      conditional Microsoft path — it did not; that claim was wrong and is now corrected

### H — Infrastructure as code
- [x] `infra/bicep/` — 11 modules: ACR, AKS, PostgreSQL Flexible (pgvector allow-listed), ADLS
      Gen2, Key Vault (RBAC), Log Analytics + App Insights, Azure OpenAI, Document Intelligence,
      Content Safety, AI Search (behind a flag), Azure ML. Compiles with **zero warnings**
- [x] **Resource-group scope**, which is the safety property: the template cannot reach outside
      the group it is given (DECISIONS #77)
- [x] `modules/identity.bicep` — the workload identity, its federated credential and every role it
      holds, each with a note on why that role and not a broader one
- [x] `infra/helm/wathiq/` — api, web and four MCP servers in the default in-process mode, plus
      the Conductor worker only when that engine is selected; 16 resources by default. One
      revision-scoped migration Job writes while API/worker init containers wait read-only;
      Key Vault CSI supplies the only two secrets that exist
- [x] `/readyz` added — `/healthz` always returned 200, so it could not serve as a readiness probe.
      A database outage now fails readiness and never liveness
- [x] `infra/teardown/teardown.sh` — four guards; **tested against the live `filingsiq-rg`, which
      it refuses**; purges soft-deleted vaults and Cognitive Services accounts so names and quota
      are released
- [x] `infra/scripts/deploy.sh` — six steps, shellcheck-clean, containerised `helm` fallback
- [x] `.gitattributes` forcing LF on shell scripts and Dockerfiles (CRLF breaks them in a container)
- [x] Costed list verified against the Azure retail price API, in `infra/README.md`

### Protecting the existing system
The subscription holds a working application in `filingsiq-rg`. Nothing Wathiq does touches it:
- [x] Resource-group scope; an exact-match allow-list in both scripts; tags required for teardown
- [x] Wathiq creates its **own** copy of every service — no shared vault, registry or account
- [x] **Quota checked before choosing SKUs.** Azure OpenAI capacity is per subscription, per
      region, per model, per SKU. The existing system uses `gpt-4o` Standard and
      `text-embedding-3-small` GlobalStandard; Wathiq deploys `gpt-4.1-mini` Standard and
      `text-embedding-3-small` Standard — measured as empty first. This coupling is invisible in
      any template or code review, which is why it is written down (DECISIONS #78)
- [x] Free tiers checked: AI Search `free` and Content Safety `F0` were already taken, so Wathiq
      uses no Search and S0 Content Safety. Document Intelligence `F0` was free and is used

### Verification
- [x] Backend: **291 passing**, ruff clean
- [x] `tests/test_azure_geometry_flow.py` runs the **whole pipeline** with an OCR double that
      reports geometry, and asserts the box survives OCR → state → checkpoint → worker →
      `geometry.locate` → database → API. A third test runs the same case on the demo reader and
      asserts there is **no** box and **no** `read` signal — so the first two prove the geometry
      arrives *because the engine supplied it*, not because the pipeline manufactures it
- [x] `pytest -m azure`: 8 opt-in live smoke tests, skipped unless endpoints are configured. The
      deployed workload identity has exercised Foundry structured output, 256-dimensional
      embeddings, Document Intelligence geometry, Prompt Shields, Content Safety, and ADLS
      save/read/exists/user-delegation SAS against the real services
- [x] MCP servers: 26 passing
- [x] Playwright: 33 passing
- [x] Frontend: eslint, tsc and the production build clean
- [x] A test asserts demo mode imports **no** Azure SDK module, in a subprocess so the test file's
      own imports cannot mask it
- [x] Bicep compiles with zero warnings; Helm lints and renders; shellcheck clean on both scripts
- [x] Live deployment to AKS and the demo flow run against real Azure services: public login,
      upload, LangGraph pipeline, 9 extracted fields, finding, assurance checkpoint and SAS fetch
- [ ] Teardown, and confirmation that billing has stopped
- [ ] Commit, push and PR

### Bugs found while building M6

Several of these were only findable by actually deploying. They are the argument for provisioning
rather than stopping at "the template compiles".

- **AKS monitoring needs two similarly named providers.** The script registered
  `Microsoft.OperationalInsights`, but Container Insights also requires
  `Microsoft.OperationsManagement`; the cluster reached a failed provisioning state until the
  latter was added.
- **Key Vault's data plane does not inherit subscription Owner.** The deployer had the read-only
  Secrets User role but needed Secrets Officer to create the two values. The role is now the
  least-privileged writer and secret creation retries boundedly while RBAC propagates.
- **ACR Tasks here is not a BuildKit builder.** Cache mounts in both Python Dockerfiles failed
  remotely although local builds passed. The mounts were optional, so the Dockerfiles now work
  with both builders; ACR log streaming is disabled because Windows Azure CLI crashes on Vite's
  Unicode success mark while the remote build itself succeeds.
- **A pre-install migration hook cannot use ordinary chart resources.** Helm runs hooks before
  the ServiceAccount and SecretProviderClass exist. Migration is now a revision-scoped release
  Job; API/worker init containers wait with read-only `alembic current --check-heads`, and Helm
  waits for Jobs. The idempotent seed also runs after an upgrade, repairing interrupted installs.
- **Default rolling updates overpack a one-node demo.** A surge briefly doubled every pod and
  exhausted CPU. Deployments use `Recreate`, consistent with the explicitly non-HA design, and
  the Conductor worker is absent when the in-process engine is selected instead of crash-looping.
- **The web image knew only Compose DNS.** Nginx resolved `api`, while Helm exposes
  `wathiq-wathiq-api`. Its config is now an environment-expanded startup template, with a writable
  config mount over the otherwise read-only filesystem.
- **Nginx rejected normal document uploads at 1 MB.** The API already permits 25 MB, but the web
  proxy's smaller default returned `413 Request Entity Too Large` before FastAPI saw a passport.
  The same startup template now has a Helm-configurable 25 MB ceiling; a 2 MB request through the
  public load balancer reaches FastAPI in the live revision 5 deployment.
- **ADLS served uploaded images as generic binary.** The database retained `image/jpeg`, but the
  opaque ADLS object returned `application/octet-stream`, leaving the PDF-oriented iframe blank.
  Signed URLs now override the response with the recorded MIME type and an inline disposition;
  the viewer uses an image element with its natural aspect ratio so OCR boxes stay aligned. The
  existing 3.1 MB passport in `WTQ-2026-0033` was verified live without re-uploading it.
- **Azure providers and authentication are separate axes.** Disabling demo login whenever
  `WATHIQ_MODE=azure` made the live environment impossible to enter before an Entra browser app
  registration exists. Demo endpoints now follow `WATHIQ_AUTH_BACKEND`; provider mode still
  controls only the Azure service adapters.

- **`gpt-4o-mini` was refused as deprecated** by the deployment preflight — while
  `az cognitiveservices model list` still advertised it as available with a 2027 deprecation
  date. The list is not the authority; the preflight is. Moved to `gpt-4.1-mini` 2025-04-14, after
  re-checking that its quota pool (`OpenAI.Standard.gpt4.1-mini`, 0 of 200) is one the existing
  system does not use.
- **AKS refused Kubernetes 1.31**: it has moved to Long-Term Support only, and a cluster cannot be
  created on it without enrolling in LTS. Pinned to 1.34, which is on the standard support plan.
  Pinning a version is still right — an automatic minor upgrade under a running demo is worse —
  but the pin has to be checked against `az aks get-versions`, not assumed.
- **Azure ML refuses a storage account with a hierarchical namespace** ("Cannot use storage with
  HNS enabled"), and Wathiq's documents *need* one — the per-case ACL is why ADLS Gen2 was chosen.
  The requirements are genuinely incompatible, so the storage module is now parameterised and
  instantiated twice: an HNS account for documents and a plain one for the workspace. Two
  nearly-empty LRS accounts cost about the same as one.
- **Picking an AKS node size took three attempts, because a size must pass two unrelated
  checks.** `Standard_B2s` is not *offered* to this subscription in eastus2 ("not allowed in your
  subscription"). `Standard_B2ls_v2` is offered but its family's vCPU quota is **zero**
  ("Insufficient vcpu quota requested 2, remaining 0") — a different check with a completely
  different error. `Standard_D2s_v3` passes both. The two are easy to conflate and neither is
  visible in a template: availability comes from `az vm list-skus`, quota from `az vm list-usage`.
  The cost rose from ~USD 30 to ~USD 70/month for the node, which the user approved after seeing
  that a torn-down group makes the real difference about USD 3 over a verification window.
- **Azure ML compute has its own vCPU quota, and this subscription's is zero.** `AmlCompute` does
  not draw on the VM quota AKS uses; a subscription that has never run an ML job starts at 0, and
  the cluster is refused with `ClusterMinNodesExceedCoreQuota` — failing the *whole* deployment
  for a resource the demo does not need standing. Raising it is a support request, not a template
  change, so the compute cluster is now opt-in and off by default. The workspace still deploys, is
  still an MLflow endpoint, and only *submitting* a job needs the quota. Stated in the docs rather
  than quietly dropped.
- **The SAS signer wants the path in two pieces, and said so unhelpfully.**
  `generate_file_sas` takes `directory_name` and `file_name` as separate arguments, and requires
  `directory_name` even at the root; passing the whole `case-id/file.pdf` as the file name raises
  a `TypeError` about a missing argument that names nothing relevant. Worse, `signed_url` caught
  it and returned `None`, so the viewer silently fell back to streaming bytes through the API and
  nothing looked broken. A second live call found that Data Lake also requires a delegation key
  in its `credential` parameter (unlike the similar Blob helper keyword). Both SDK contracts now
  have offline regressions, and the real read-only SAS fetched the uploaded PDF successfully.
- **Azure rate-limited the deployment itself.** After several redeploys in an hour, the
  Cognitive Services preflight started returning `715-123420` — *"unusual activity for your
  account"* — and refused the **whole template**, even though those accounts and both model
  deployments already existed and were correct. It did not clear after a 12-minute wait. The fix
  is a `deployCognitiveServices` switch: with it off, the three AI modules are skipped and their
  endpoints are read from the existing resources with `existing` references, which are lookups
  and cannot trigger the throttle. That turned out to be worth having anyway — iterating on the
  cluster should not re-declare model deployments. `WATHIQ_SKIP_AI=1 ./infra/scripts/deploy.sh`.
- **The first deploy reported success while having failed.** `deploy.sh` is `set -euo pipefail`
  and correct; the wrapper ran it as `deploy.sh | tail -60`, so the exit code reported was
  `tail`'s. The script was never at fault, and the lesson is about how it is invoked.

- **`/healthz` could not be a readiness probe.** It reported the database as "degraded" and still
  returned 200, so a pod that could reach nothing would have stayed in the load balancer. Split
  into `/healthz` (liveness, always 200) and `/readyz` (503 when the database is unreachable).
- **A wrapped value lost its last line.** The first bounding-box union collected any matching line
  above a length floor, which dropped "LLC" — three characters, but plainly the rest of the company
  name on the next line. Rewritten to grow outwards from a distinctive seed through *adjacent*
  lines, which also stops a stray match elsewhere on the page joining the box.
- **The Entra role map invented a role.** It mapped `Wathiq.Analyst` to `Role.analyst`, which does
  not exist — the five roles are ops_officer, reviewer, supervisor, admin, auditor. It failed at
  import, caught by calling the endpoint rather than by reading the code.
- **`azure_services` on the mode endpoint was `not is_demo`** — a claim that Azure was in use
  whenever the mode was set, even with no endpoint configured anywhere. It now counts services that
  are genuinely switched on.
- **Python wrote CRLF into the shell scripts**, which fails inside a container with `bad
  interpreter` and never on Windows. Fixed, and `.gitattributes` now prevents it returning.
- **DECISIONS numbering collided.** The new entries were written as #58–71 while the file already
  ran to #62; they are renumbered #63–78 with the code references updated to match.
- **Quality Lab inherited the live Azure providers.** Its reproducible synthetic suite called the
  deployment factories, turning “run all” into dozens of synchronous Document Intelligence and
  Foundry requests; Document Intelligence eventually returned 429 and the browser saw a failed
  evaluation. Evaluation now injects deterministic OCR/extraction explicitly, while opt-in Azure
  smoke tests remain responsible for provider health. The public all-band run completed five bands
  and 87 checks in 17.8 seconds with no Azure AI calls.

## M7 — Polish
- [x] Arabic / RTL across every screen: interface strings in both locale files, logical CSS
      properties, mirrored layout, direction-aware icons, LTR islands for ids, IBANs, JSON and
      file names. `e2e/tests/rtl.spec.ts` walks each screen in Arabic and fails on a leaked
      translation key
- [x] Use case 2 by configuration: a **case-type profile** per use case (`app/casetypes/*.yaml`)
      naming its expected documents, its posting tool and record, the fields that record needs,
      and its registry checks. The posting step and the investigator read the profile; neither
      names a use case (DECISIONS #80–82)
- [x] Salary cases post an **income verification** to the employee's own file. Before this they
      were posted as a *KYC refresh* against a company — found while making posting config-driven
- [x] Two MCP tools added for use case 2: `company_registry.verify_employer` (read-only,
      investigator only) and `core_banking.post_income_verification` (write, posting step only).
      The simulated system of record refuses a record written to the wrong kind of customer file
      and an income record with no employer or total salary
- [x] Failure-mode gallery: 15 entries, each in English and Arabic. Nine are staged live through
      the ordinary intake (create → upload → start), six name the tests that prove them.
      `test_failure_gallery.py` runs every runnable entry through the real pipeline and asserts
      the promised status and codes, and checks every named test exists (DECISIONS #83)
- [x] Intake shows the documents the chosen case type expects, read from the profile the engine
      reads — so the screen cannot ask for documents the engine does not use
- [x] Final README with 12 screenshots of the running system, captured by an opt-in Playwright
      spec (`e2e/tests/screenshots.spec.ts`), skipped in CI
- [x] Backend tests: 326 passing (19 gallery + 17 use case 2 added); MCP servers: 34 (8 added);
      Playwright: 44 passing (rtl, use case 2 and gallery suites added), plus an opt-in
      screenshot spec that CI skips
- [ ] Milestone checks + commit/PR

### Bugs found while building M7
- **Salary cases were posted as company KYC refreshes.** The posting step named one tool and one
  record for every case type, so use case 2 wrote the wrong record, to a company's file. Profiles
  fixed it, and the system of record now refuses the wrong kind of file as a second lock.
- **Seeded salary cases named the employer as the customer.** A salary certificate belongs to the
  employee; the company is the employer. The seed now uses the person.
- **A tab strip clipped the panel beside it.** With five tabs in a narrow column, the browser
  scrolled a tab into view by scrolling the whole card, silently cutting off the Process and
  Assurance panels. Found in a screenshot, not by a test. The strip now scrolls on its own.
- **Two docs still named `gpt-4o-mini`** although M6 moved to `gpt-4.1-mini` after the older
  model was refused as deprecated. Corrected in DECISIONS #78 and the glossary.
- **Headless browsers do not render PDFs.** The document viewer looked blank in every screenshot
  and in a Chromium test. The product was fine; the capture spec now runs Firefox with its PDF
  viewer enabled, and this is written down so the next person does not chase a phantom bug.

## Capability coverage
- [x] LangGraph: supervisor-worker (Send API, one worker per document)
- [x] LangGraph: self-reflection (repairs on Pydantic errors, capped at 2)
- [x] LangGraph: actor-critic (independent grounding, shape and label checks)
- [x] LangGraph: ReAct (bounded loop, MCP tools, thought/action/observation recorded)
- [x] LangGraph: HITL interrupts
- [x] LangGraph: TypedDict state
- [x] LangGraph: conditional edges
- [x] Azure AI Foundry extraction with structured outputs (strict mode, from the same Pydantic
      schema; the model's answer is then grounded against the document rather than trusted)
- [x] Per-field confidence from five signals, calibrated with Platt scaling on reviewer outcomes
- [x] Pydantic validation (models built at runtime from the document type's schema; the same
      schema is the structured-output contract in M6)
- [~] Prompt management with semver (registry, diffs, approval done; engine pinning in M2)
- [~] Prompt correctness checks and sensitivity harness. The harness now accepts a real
      prompt and a Foundry-backed predictor, but **no wording-sensitivity score is published** —
      that needs a measured run against the live model
- [x] MCP servers: 4 servers, least privilege per node
- [x] MCP servers extended for use case 2 (`verify_employer` and `post_income_verification`,
      each on exactly one node's allowlist)
- [x] Five test bands (real API/CI suites with counts, provenance and negative controls)
- [x] Golden + regression datasets
- [x] HITL at mandatory and dynamic points (mandatory and dynamic review tasks both created)
- [x] Conductor wait tasks (a WAIT task beside the human task, as the SLA timer)
- [x] Checkpoint persistence and resumption (and crash recovery: redelivery under Conductor,
      a startup sweep under the fallback)
- [x] Content Safety and Prompt Shields — the Azure services run **beside** the local detectors,
      not instead of them; either one flagging sends the case to a person
- [x] PII tokenisation (7 recognisers; only the tokenised copy may reach a log)
- [x] Prompt shielding (instruction patterns, invisible characters, bidi overrides, encoded blobs)
- [x] Output sanitisation (markup, scripts, control and bidi characters, length cap)
- [x] Cross-field validation (versioned YAML rule packs, six expression shapes, named checks)
- [x] Orkes Conductor (workflow with HUMAN/WAIT/FORK-JOIN/SWITCH, Python task workers)
- [x] Document Intelligence (`prebuilt-layout`): real OCR, bounding boxes finally rendered on
      the case screen, and a sixth per-value confidence signal
- [~] RAG: chunking, vector indexing and citations live on pgvector. The Azure AI Search
      adapter (hybrid keyword + vector) is written and tested but **deliberately not deployed** —
      the subscription's free tier belongs to another system (DECISIONS #71)
- [x] AKS: Bicep for the cluster with workload identity and the Key Vault CSI driver, and a Helm
      chart covering api, worker, web and the four MCP servers
- [x] ADLS Gen2: hierarchical namespace, and short-lived read-only SAS links signed with a user
      delegation key so the signature is traceable to an identity
- [x] Azure ML: the calibration fit as a command job, calling the same `calibration.fit()` the
      in-process path calls
- [x] Azure Monitor: OpenTelemetry spans for every graph node, MCP tool call and guardrail
      decision — ids and verdicts only, never document text
- [x] Pydantic, FastAPI, TypeScript, REST APIs, JSON schema
- [~] Microsoft Entra ID: token validation, app-role mapping and just-in-time provisioning are
      done and tested; the browser OIDC redirect leg is not built (no app registration)
- [x] Infrastructure as code: 11 Bicep modules at resource-group scope, a Helm chart, and a
      teardown whose guards are tested against the subscription's live resource group
- [x] Git, CI/CD
- [x] Failure-mode analysis (bugs and their causes recorded per milestone, and a gallery that
      stages fifteen of them — nine live, six proven by tests)

Legend: `[x]` done · `[~]` partly done, finished in a later milestone · `[ ]` not started.

## Docs (section 11)
- [x] SYSTEM_OVERVIEW.md
- [x] ARCHITECTURE.md
- [x] ARCHITECTURE_DECISION_RECORD.md — 23 formal ADRs with traceability to all 79 decisions
- [x] DECISIONS.md
- [x] GLOSSARY.md
- [ ] Demo script (M7, drafted after the UI is final; kept privately, not published)
- [ ] Explanation notes (kept privately, not published)
- [x] README.md (screenshots added in M7)
- [x] API.md, DESIGN.md
