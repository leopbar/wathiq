# Decisions — why this, not that

Every significant choice, in plain English, with the alternative we rejected and why.
Newest decisions are added at the bottom of each section as the project grows.

---

## 1. AI reasoning: LangGraph
**Chosen:** LangGraph with a PostgreSQL checkpointer.
**Instead of:** CrewAI, AutoGen, or plain Python functions.
**Why:** A KYC case can pause for hours waiting for a human. LangGraph makes the agent an explicit
graph with typed state that can be saved (checkpointed), interrupted at a review gate, and resumed
exactly where it stopped. Plain Python would mean writing that persistence ourselves; CrewAI hides
the state machine behind role-play abstractions, which makes auditing "why did it do that?" harder.
**Cost:** One more framework to learn, and its interrupt/resume semantics must be respected (nodes
before `interrupt()` re-run on resume, so they must have no side effects).

## 2. Process orchestration: Orkes Conductor
**Chosen:** Conductor OSS in Docker, with Python workers.
**Instead of:** Apache Airflow, Temporal, or a plain database queue.
**Why:** The *business* process — intake, guardrails, agent work, human task with an SLA timer,
posting, audit — needs durable waiting, retries and an operations view. Conductor has first-class
HUMAN and WAIT tasks. Airflow is built for scheduled batch pipelines, not long-lived human
workflows. Temporal is excellent but the target team runs Conductor, and matching their stack is
part of the point.
**Cost:** Conductor is a heavy Java service (~1–2 GB RAM), so it sits behind a Compose profile.

## 3. Two layers, one identifier
**Chosen:** Conductor runs the process; LangGraph runs the reasoning inside one Conductor task. The
Conductor workflow ID is used as the LangGraph thread ID.
**Instead of:** Doing everything inside LangGraph, or everything inside Conductor.
**Why:** They are good at different things. Conductor cannot reason; LangGraph is not an operations
platform. Sharing one identifier means an auditor can take a single ID and see the business steps,
the AI's thinking and every audit line for the same case.
**Cost:** Two systems to explain — which is why `docs/ARCHITECTURE.md` leads with this picture.

## 4. Backend: FastAPI + Pydantic v2
**Chosen:** FastAPI, async, Pydantic v2 models shared between the API and model output validation.
**Instead of:** Django or Flask.
**Why:** We stream live progress (SSE) and call models concurrently, so async matters. The same
Pydantic model validates the API request and the model's structured output, so the schema cannot
drift between layers. Django's ORM and admin add weight we do not use.

## 5. Database: one PostgreSQL with pgvector
**Chosen:** PostgreSQL 16 + pgvector for records, LangGraph checkpoints and policy embeddings.
**Instead of:** PostgreSQL plus a dedicated vector database (Pinecone, Qdrant, Milvus).
**Why:** At this scale (thousands of policy chunks) pgvector is fast enough, and one database means
one backup, one connection string, one thing to explain. A separate vector store would add a
service, a cost line and a consistency problem for no benefit yet.
**Revisit when:** millions of vectors or heavy hybrid-search requirements appear — then Azure AI
Search (already behind an interface) takes over.

## 6. Async SQLAlchemy with psycopg 3
**Chosen:** SQLAlchemy 2 async + psycopg 3.
**Instead of:** Sync SQLAlchemy in a threadpool, or asyncpg.
**Why:** SSE endpoints and LangGraph both want async. psycopg 3 is the driver LangGraph's Postgres
checkpointer uses, so we keep one driver in the image instead of two.

## 7. Live progress: Server-Sent Events
**Chosen:** SSE (`text/event-stream`).
**Instead of:** WebSockets, or polling.
**Why:** Progress only travels server → client. SSE is a plain HTTP response, reconnects on its own,
survives proxies and load balancers, and needs no extra protocol handling. WebSockets would give us
two-way messaging we do not need. Polling wastes requests and looks laggy.

## 8. One append-only `events` table for both timeline and audit
**Chosen:** A single `events` table; the case timeline is a filtered view of it.
**Instead of:** Separate `timeline_events` and `audit_log` tables.
**Why:** Two tables drift. If the timeline shows something the audit log does not, the audit log is
worthless. One append-only table (never updated, never deleted) with a monotonic `seq` column keeps
them identical by construction.

## 9. Enums stored as strings with a CHECK constraint
**Chosen:** `VARCHAR` + CHECK, not native PostgreSQL enum types.
**Instead of:** `CREATE TYPE ... AS ENUM`.
**Why:** Adding a value to a native enum in PostgreSQL is awkward to reverse and can block. A string
column with a constraint is a simple, reversible migration.

## 10. Frontend: React + TypeScript + Vite
**Chosen:** Vite single-page app.
**Instead of:** Next.js.
**Why:** This is an internal console behind a login. Server rendering, SEO and edge routing bring no
value, and Next.js would add a Node server to run and secure in production. Vite gives instant hot
reload in development and static files served by nginx in production.

## 11. UI: Tailwind v4 + hand-written shadcn-style components
**Chosen:** Tailwind CSS v4 (CSS-first `@theme`) with our own components built on Radix primitives.
**Instead of:** Material UI, Ant Design, or the shadcn CLI.
**Why:** A bank product should not look like a default component library. Owning ~25 small
components gives complete control over the design system and accessibility, with Radix handling the
hard parts (focus traps, keyboard menus). We write the components by hand rather than using the
shadcn CLI so the build never depends on a code generator at install time.

## 12. Auth: local JWT in demo mode, Entra ID in Azure mode
**Chosen:** Two providers behind one role model.
**Instead of:** Building our own user management for production, or requiring Entra ID always.
**Why:** The demo must work offline on a laptop with no tenant. Production must never store
passwords. The five roles are identical in both, so authorisation code is written once.

## 13. Everything containerised, dev and prod from the same Dockerfiles
**Chosen:** Multi-stage Dockerfiles with `dev` and `prod` targets; Compose for local, Helm/AKS for
Azure.
**Instead of:** Local installs, or separate Dockerfiles per environment.
**Why:** `docker compose up --build` is the whole setup. One Dockerfile per service means the image
that passes CI is the image that ships. Non-root users and healthchecks are set once.

## 14. Compose profiles for heavy services
**Chosen:** Conductor (`process`), Playwright (`test`) and MLflow (`ml`) sit behind profiles.
**Why:** The development machine has 16 GB RAM. The core demo (db + api + web) must always start,
even if the heavy services are switched off. The process layer has a documented in-process fallback
behind the same interface so the demo never breaks.

## 15. Storage, OCR, models, search and safety behind interfaces
**Chosen:** An abstract class per external capability, with a demo implementation and an Azure one.
**Instead of:** Calling Azure SDKs directly from the business code.
**Why:** It is the only way to have a genuinely offline demo *and* a real Azure mode without two
codebases. It also makes the failure story honest: if Azure is down, we degrade to the local
implementation and say so in the UI.

## 16. Simulated services are labelled, never disguised
**Chosen:** Core banking, company registry and sanctions screening are clearly marked `Simulated` in
the UI, the API and the docs.
**Why:** Claiming a fake integration is real is the fastest way to lose trust in a review or an
audit. The stand-ins are real MCP servers with real contracts — they just talk to synthetic data.

---

## Milestone-1 working decisions

### 17. Project stays on `C:\projects\Wathiq` instead of moving into WSL2
**Why:** The development tooling runs on Windows. Polling-based file watching (`usePolling` in Vite,
`--reload-dir` with WatchFiles in uvicorn) costs 1–2 seconds of reload latency, which is cheaper
than the setup risk of relocating the project mid-build.
**Revisit when:** the reload delay becomes annoying — moving to WSL2 is a copy plus a restart.

### 18. TypeScript 5.9 instead of TypeScript 7
**Why:** TypeScript 7 is stable, but `openapi-typescript` (which generates our API types from the
FastAPI schema) still requires a TypeScript 5 peer. Rather than force a broken dependency tree, we
pin 5.9 and will move when the tooling catches up. Nothing in our code uses 6/7-only syntax.

### 19. A tiny hand-written PDF writer for seeded documents
**Why:** The 30 demo cases need viewable documents, but binary files must not be committed. A ~70
line PDF writer generates them at seed time. It cannot render Arabic (the base PDF fonts do not
contain Arabic glyphs), which is stated on the document itself; the real bilingual generator arrives
with the golden dataset in M5.

### 20. Tests run against a throwaway `wathiq_test` database
**Why:** Integration tests hit the real schema and real SQL (including PostgreSQL-only features like
`percentile_cont`), so mocking the database would test the wrong thing. The fixture refuses to run
against any database whose name does not end in `_test`.

### 21. Browser-initiated GETs accept `?token=`, write endpoints never do
**The problem:** three things the browser fetches by itself cannot send an `Authorization` header —
an `<iframe src>` (the document preview), an `EventSource` (the live progress stream) and a download
link (the audit CSV export).
**Chosen:** a separate dependency (`get_current_user_browser`) that accepts the JWT either in the
header or in a `token` query parameter, wired to exactly those three GET endpoints. Every write
endpoint keeps header-only auth, and a test asserts that a token in the URL cannot create a case.
**Instead of:** cookies (CSRF surface, and the SPA already holds a JWT) or making the endpoints
public (they expose customer documents).
**Cost:** tokens in URLs can land in server logs and browser history. Accepted for the demo; the
production answer is short-lived signed URLs for documents and exports.
**This also closed a hole:** the event stream had no authentication at all before this change.

### 22. Vite's dev server allowlists the Compose service name
Vite 8 answers `403` when the `Host` header is not in `server.allowedHosts`. Inside Compose the app
is reached as `http://web:5173`, so Playwright saw 403 on every page. `allowedHosts` now lists
`web`, `localhost` and `127.0.0.1`. The default is a real protection (DNS-rebinding), so the list
stays explicit rather than being switched off.

### 23. `@types/node` instead of hand-written type shims
`tsconfig.json` type-checks `vite.config.ts`, which uses `node:url` and `process`. A temporary
ambient-declaration file was written while the dependency list was frozen; it has been deleted and
`@types/node` added properly. Hand-written shims drift silently from the real API — a dependency is
the honest version of the same thing.

### 24. A blanket reduced-motion rule broke Mermaid rendering
`@media (prefers-reduced-motion: reduce) { * { animation-duration: … } }` also matches the SVG
elements Mermaid measures while laying a diagram out. Chrome then reports the wrong geometry and the
diagram renders as scattered dots in a viewBox roughly seven times too wide.
**Fix:** the rule now excludes Mermaid's measurement container (`#dwq-mermaid-*`) and `.mermaid-host`;
everything else still honours reduced motion. Comments in `theme.css` and `MermaidDiagram.tsx` keep
the id prefix in sync.
**Worth remembering:** a universal selector in a media query is not free — it can change how a
library measures the page, not just how it animates.

### 25. Known: the frontend bundle is 1.4 MB (418 KB gzipped)
Mermaid and Recharts dominate it. Acceptable for an internal console on a corporate network, and not
worth fixing while screens are still changing. **M7 polish:** load the About screen (Mermaid) and the
chart components with `React.lazy`, which should cut the initial bundle by roughly half.

### 26. `demo-login` is an endpoint, not a hard-coded frontend shortcut
**Why:** One-click role switching must go through the same authentication and audit path as a real
login, so the audit trail is complete. The endpoint returns 404 when `WATHIQ_MODE=azure`, so the
shortcut cannot exist in a real deployment.

### 27. The demo extractor reads labels, it does not call a model
**Why:** Demo mode has to work with no network and no keys, and the Quality Lab in M5 needs a
baseline that gives the same answer every time. A deterministic label-and-value reader does both.
It also cannot hallucinate: if a value is not in the document, the field comes back empty with
confidence 0 rather than invented.
**Not that:** a small local model — more to install, slower, and a demo that sometimes disagrees
with itself is worse than one that is obviously simple.
**Honesty:** the UI and `integrations()` both label this as a demo extractor. Azure mode swaps in a
Foundry call with structured outputs behind the same interface in M6; the Pydantic validation of
the result does not change.

### 28. Confidence is a formula we can explain, not a random number
**Why:** A reviewer will ask "why is this 62%?". The demo extractor scores a value from things you
can point at — replacement characters from a bad read, a suspiciously short value, a mixed
letters-and-digits reference number that is typically the most reliable field on the page. Seeding
a random number generator would look the same on screen and mean nothing.
**Consequence:** `calibrated_confidence` currently equals the raw score. Calibration needs a labelled
outcome set, which is M3/M5 work, and showing a "calibrated" number that has not been calibrated
would be a lie.

### 29. The review task is created by the runner, not inside the review-gate node
**Why:** LangGraph re-runs an interrupted node from its first line when the graph resumes. Anything
the node wrote before `interrupt()` would therefore be written a second time — here, a duplicate
review task for every reviewer decision. The node computes and interrupts; the runner, which is
outside the graph and runs exactly once per pause, creates the task rows.
**Rule to keep:** a node that can interrupt must be side-effect-free above the `interrupt()` call.

### 30. Findings carry their status across a resume
**Why:** The rules re-run when the graph resumes, and `_persist` replaces the findings for a case.
A finding a reviewer had just resolved came back as `open`, silently undoing their decision. The
previous status is now carried over by rule code.
**Worth remembering:** "replace everything the graph produced" is a clean rule for data the graph
owns, but findings are shared — the graph proposes them and a human dispositions them.

### 31. The pipeline runs as a background task, for now
**Why:** An upload request should not block until the pipeline finishes, and the browser already
follows progress over SSE. `asyncio.create_task` with a strong reference and a done-callback that
logs failures is enough for a single API process.
**Its limit, stated plainly:** if the container dies mid-run, that run is lost — the LangGraph
checkpoint survives, but nothing restarts it. M4 replaces this with a Conductor worker, which is
what makes the run durable. The interface (`pipeline.start` / `pipeline.resume`) stays the same.

### 32. Punctuation is deleted, not spaced, when comparing names
**Why:** The cross-document rule scored "Al Noor Trading LLC" against "Al Noor Trading L.L.C." at
0.5 similarity and raised a mismatch on two identical names. Replacing punctuation with a space
split `L.L.C.` into three tokens. Deleting it instead keeps it as one.
**Worth remembering:** UAE company names use both spellings constantly; a normaliser that looks
obviously correct in English can be wrong for the data it will actually see.

### 33. The About screen draws the graph that actually runs
**Why:** A diagram that describes a design rather than the code drifts within a week, and the whole
point of the screen is to explain the system truthfully. `/system/graph` now returns the diagram
from the graph module and reports `source: "live"`.
**Same rule elsewhere:** the New case "what happens next" panel and the pipeline stepper both read
one step list, mirrored on the backend in `services/progress.py`. Guardrails are deliberately absent
from it until M3 builds them — a step that never lights up reads as a bug, not as honesty.

### 34. The pipeline reads the cleaned text, never the PII-tokenised copy
**Why:** The guardrails node produces two copies of a document's text, and mixing them up is a real
bug, not a style point. The first build tokenised identifiers and then handed *that* to the
extractor, so every date became `<DOB_1>` and every extraction failed. The rule now is explicit:
`clean_text` (invisible characters and markup removed, values intact) is what the pipeline reads;
`log_text` (identifiers replaced with stable tokens) is the only form allowed into a log, a trace
or an evaluation fixture.
**Worth remembering:** tokenisation protects the *observability* path, not the processing path. The
case record is access-controlled and audited; the log is read by engineers and copied into tests.

### 35. Platt scaling, written by hand, instead of scikit-learn
**Why:** Calibration here is one logistic curve with two parameters. Forty lines of gradient descent
keeps a 300 MB numeric stack out of the API image, stays deterministic, and — the part that matters
in a bank — can be explained to an auditor in one sentence: "we learned how much to trust the
extractor's own score, and applied that correction."
**The trap it fell into first:** the initial settings (400 steps, rate 0.5) stopped well short of
the minimum. The curve it produced scored *worse* than doing nothing, the guard below caught it, and
calibration silently never turned on. Two thousand steps at rate 1.0 converges in milliseconds.
**The guard that saved it:** if the fitted curve's Brier score is worse than the raw scores', the
fit is discarded and the product keeps showing raw numbers, labelled as raw.
**Later:** isotonic regression and MLflow tracking arrive in M5 with the golden set, where the extra
flexibility has enough data to earn its place.

### 36. Ground truth comes from reviewers, not from a labelling exercise
**Why:** Every field a reviewer looked at is a labelled example, for free, growing every day: a field
they accepted was read correctly, a field they corrected was not. Only cases a human actually
completed are counted. Fields from straight-through cases are excluded deliberately — nobody checked
them, and counting them as "right" would teach the curve to be over-confident about exactly the
cases nobody verified.

### 37. Four MCP servers as four processes, not four functions
**Why:** "Least privilege" is only true if the privileges are actually separate. Each server is its
own container with its own tool set; the document store's volume is mounted read-only; core banking
is the only one that can write anything. The investigator is never given core banking's address,
and the broker in the API refuses that call by name as a second, independent lock.
**Also:** the servers are the real MCP Python SDK over streamable HTTP, with DNS-rebinding
protection left on and each service's hostname allowlisted in `compose.yaml` — rather than switched
off with a wildcard.

### 38. A failed tool call is a failed check, never a silent pass
**Why:** If the sanctions server cannot be reached, the honest outcome is "this party was not
screened", which sends the case to a person. The alternative — falling back to a local imitation of
the tool — would make an unperformed check look like a passed one, which is the single most
dangerous thing an assurance system can do.
**Consequence:** there is no local fallback for any MCP tool. Failures are recorded in the case's
tool-call list and raise a finding.

### 39. The ReAct controller is deterministic in demo mode, and says so
**Why:** Demo mode has no model. The investigator still runs a real reason → act → observe loop with
real tools and a real step limit; what chooses the next action is a small rule-based controller
rather than a model. Azure mode swaps the controller and changes nothing else.
**Honesty:** the UI names the controller, because "an agent decided" and "a rule decided" are not the
same claim.

### 40. Rules moved to versioned YAML packs, with a named-check escape hatch
**Why:** A bank rule changing should be a diff in a pull request with a version number, not a
deployment of new logic. Each document type has one pack file carrying a semantic version, and the
version that judged a case is recorded on the case, so an audit two years later can be read against
the rules in force at the time.
**The escape hatch:** some rules ("every shareholder has an identity document in this case") compare
a list against the *set of documents*, which no two-value expression can say. Those are Python
functions in a registry, and a pack refers to one by name. Adding a rule is configuration; adding a
new *kind* of check is code, and the difference is visible in the YAML.
**Fallback:** a document type with no pack falls back to the editable rows on the document type, and
the case records which source judged it.

### 41. A rule that did not run is not a rule that passed
**Why:** The engine returns `evaluated: False` with a reason whenever the values a rule needs are
missing or the expression is not supported. Callers must not read `passed` as a verdict when that
flag is false. The alternative — treating "could not check" as "checked and fine" — is how
assurance systems quietly stop assuring anything.
**Related:** a rule may carry a `when:` guard so it only applies in the state it makes sense in.
"Expires within 30 days" is a useful warning about a valid licence and a nonsense sentence about one
that lapsed in 2019, where a different rule already fired.

### 42. Self-correction repairs near the label, never anywhere on the page
**Why:** The first version of the date repair searched the whole document as a last resort. On a
trade licence that cheerfully put the *issue* date into the *expiry* field and called it a repair.
A wrong value that validates is far more dangerous than an empty one, because nothing downstream can
tell it is wrong. Repairs now look only at the lines under the field's own label, and a field that
cannot be filled is left empty with every attempt recorded.

### 43. The case's confidence averages the fields that have a value
**Why:** A schema has optional fields. Including a field the document simply does not contain — which
scores low because it is not grounded anywhere — made a perfectly read document look doubtful.
Completeness is a separate question, and the `is present` rules answer it.

### 44. Read-only requests must end their transaction
**Why:** A read-only request still opens a transaction, and a connection returned to the pool without
a commit or a rollback sits **idle in transaction**. A handful of those, from ordinary GET requests,
blocked the LangGraph checkpointer's `CREATE INDEX CONCURRENTLY` on a fresh database — that
statement waits for every open transaction to finish — and every case stopped before its first node
with no error anywhere in the logs.
**The fix, in two parts:** the request session now rolls back on the way out, and the checkpointer is
set up during application startup, before the server accepts traffic.
**Worth remembering:** this had been latent since M1 and only appeared when the database was wiped,
because the checkpoint tables already existed on every previous run. A clean `docker compose down -v`
before a milestone check is not ceremony.

### 45. Evidence is read from the checkpoint, not copied into new tables
**Why:** The case screen's Assurance tab shows guardrail reports, worker results, the critic's notes,
the investigator's trail and every tool call. All of it is already in the LangGraph checkpoint, which
is the state the graph resumes from. Reading it there means the panel and the pipeline cannot
disagree; copying it into tables would create a second version of the truth to keep in step.
**Its limit:** a seeded demo case has no checkpoint, and the panel says exactly that rather than
showing an empty page that looks like a failure.
**The bug it caused:** the panel fetched once on mount and froze whatever half-finished snapshot it
caught — "0 steps" for a run that did six. It now follows the case while it is moving and refetches
once when the status settles.

### 46. Two process engines, one set of steps
**Why:** Conductor needs about 2 GB of RAM. A demo that cannot run without it is a fragile demo, and
the laptop this is built on has 16 GB to share with everything else. So the process layer has a
second engine that walks the same steps in Python.
**What makes it honest:** both engines call the same functions in `process/tasks.py` and write the
same entries to the same append-only log. The fallback is not a second implementation of the business
process — it is the same steps with a different scheduler. Every case records which engine ran it, so
a case processed by the fallback can never be mistaken for one that went through Conductor, and the
Settings screen says plainly when `auto` had to fall back.
**Not chosen:** making Conductor mandatory (the demo stops working on a tired laptop), or dropping
Conductor and only ever claiming to use it (dishonest, and it is named in the job description).

### 47. A decision goes back to the engine that started the case
**Why:** A case can sit at the human step for hours. In that time the API may have restarted, or
Conductor may have gone down and `auto` fallen back. Handing the reviewer's answer to *today's*
engine would leave a Conductor workflow waiting for ever for an answer that went somewhere else. The
engine is therefore looked up from the case's own `process.started` event, not from the current
configuration.

### 48. A hand-written Conductor client, not the official SDK
**Why:** `conductor-python` brings its own threaded worker runtime. This application is asyncio from
top to bottom, and mixing the two would mean two concurrency models in one container for the sake of
six HTTP endpoints. The client is about 200 lines of `httpx` and keeps the fallback engine and the
Conductor engine sharing everything except scheduling.
**Its cost, stated:** we own the compatibility. If Conductor changes those endpoints, this breaks and
the SDK would not have. The endpoints used are the stable REST ones (`/api/metadata`,
`/api/workflow`, `/api/tasks`), and there is a test suite against a fake transport.

### 49. The SLA timer runs beside the review, and the join waits for the review alone
**Why:** The obvious design — review, then a timeout — cannot escalate a review that is late, because
nothing is watching while it waits. The fork runs the timer next to the human task instead, and the
join lists only the human task. A fired timer escalates; it never finishes a case on a person's
behalf.
**The consequence we had to handle:** the timer branch is still sitting in its `WAIT` once the review
is answered, so the workflow instance would stay RUNNING for the rest of the SLA window. Completing
the human task now also releases that `WAIT`, in that order — so the escalation step, which runs
straight afterwards, sees a review that is already closed and records that there was nothing to do.

### 50. Escalation moves the queue, it does not take work away from a person
**Why:** An overdue review that somebody has already claimed is usually a reviewer in the middle of a
hard case. Yanking it into the supervisor queue would throw away their half-made decision and start
the reading again. So an *unclaimed* overdue review changes hands, a *claimed* one stays with its
reviewer, and both are recorded. Either way the case priority is raised and the supervisor is told.
**The fix it forced:** the review queue now filters on `assigned_role`, so an escalated task really
does leave the reviewer's list. Before that, escalation changed a label and nothing else.

### 51. The idempotency key is derived from the workflow, never random
**Why:** The point of the key is that a retry produces the *same* key. `<workflow id>:kyc_refresh:1`
does: the same case always produces it, and a restarted workflow — which is a deliberate decision to
run the business process again — produces a different one.
**Enforced twice:** a `UNIQUE` column in our `postings` table and the simulated core banking server's
own key table. A redelivered task, a worker that died between the call and the commit, and two
workers racing all end with one posting. The contract version at the end of the key means a genuine
change to the payload can post again while a retry of the old payload cannot.

### 52. A posting that did not happen is written down
**Why:** "We did not post this" is exactly what an auditor asks about. A rejected case, a customer
with no file in the system of record, a tool server that is not configured — each writes a `postings`
row with its reason instead of leaving silence that looks like success.

### 53. Straight-through cases are posted under a named policy, not a person
**Why:** The whole value of straight-through processing is that nobody looks at the case. But the
system of record only accepts a posting with a named approver, and writing a person's name there
would be a lie. So an approval carries a *kind*: `human`, or `straight_through_policy` with the
policy's identifier. The server rejects any kind it does not recognise, and the case screen shows
"a policy, not a person" in as many words.

### 54. `completed` means posted and sealed, not "the model stopped thinking"
**Why:** Before M4 the graph set a case to `completed` when it finished reasoning. With a process
layer that is wrong: the case still has to be posted and its audit entry written. The graph now ends
at `approved` and only the audit step writes `completed`.
**What it broke, and how we found it:** the case screen polled only while a case was `intake` or
`processing`, so it stopped one step early and sat on "Approved" until the page was reloaded. The
end-to-end tests caught it because they wait for the process to finish, not for the graph to.

### 55. The audit trail's append-only rule is enforced by the database
**Why:** "Append-only" was true because nothing in the code wrote an `UPDATE`. Convention is not a
control — a bug, or anyone with the application's own credentials, could quietly rewrite history. A
trigger on `events` now raises on every `UPDATE` and `DELETE`.
**Its limits, said out loud:** a database superuser can drop a trigger, and `TRUNCATE` does not fire
row triggers. This proves the *application* cannot alter the log; it is not cryptographic proof. A
hash chain per row is the next step if an auditor needs tamper evidence, and the integrity endpoint
says so rather than implying more than it has.
**What it forced:** reseeding the demo database used to `DELETE` from every table. It now uses
`TRUNCATE`, which is the right boundary rather than a loophole — it needs table-owner rights and
empties the table completely, so it cannot be used to alter one record.

### 56. A redelivered agent task continues the graph, it does not restart it
**Why:** At-least-once delivery means the agent step can arrive twice. Calling the graph with the
initial state again would apply that state on top of an existing checkpoint, and the keys the
parallel workers write use appending reducers — so every list would quietly gain a duplicate. The
step checks for a checkpoint first and resumes from it instead.

### 57. Conductor gets an identifier, never a customer's data
**Why:** Conductor is a separate system with its own storage and retention, and its UI is visible to
anyone who can reach it. Every task payload is the case id and nothing else; the worker reads what it
needs from the database itself. A test asserts that no customer field and no document text appears
anywhere in the workflow definition.

### 58. Evaluation results must come from assertions that can fail
M5 shares one runner between the API and CI. A document is one diagnostic observation; field
counts are not presented as independent samples. Old seeded runs remain labelled illustrative and
are excluded from the summary. Negative controls and a broken-extractor test prove rejection.

### 59. Blurry demo PDFs test abstention, not imaginary OCR
The generator rasterises and blurs real PDFs, without leaving hidden answers in a text layer.
The offline reader returns no text. Arabic labels use an embedded, shaped font; English synthetic
values remain the extraction contract. This is explicitly not an Arabic OCR accuracy claim.

### 60. Prompt correctness and wording sensitivity are different claims
The demo reader does not consume prompts, so identical outputs after rewording prove nothing.
Prompt Studio records exact-version template/backend diagnostics; live sensitivity says unsupported.
The sensitivity harness can catch unstable answers and stable-but-wrong answers in tests. A real
Foundry predictor is required in M6 before publishing a wording-sensitivity score.

### 61. Corrections preserve their input, and CI needs an explicit export
Copy the schema, source text and expected answer during the review transaction, independently of
later processing. Repeated task/field capture is deduplicated. Local replay reads the database;
CI reads the reviewed synthetic export committed as quality/regressions.json. Raw customer data
must never be promoted through this demo-only export path.

### 62. Calibration metrics describe individual outcomes and their training scope
Averaging chart-bin errors is not the Brier score. Compute it per reviewed field, exclude rejected
cases from positive ground truth, and say these are training diagnostics. Record every refit
attempt, even refusals, and keep database/memory activation consistent. MLflow receives aggregate
metrics via REST; its absence never prevents fitting. It runs on loopback port 5001 under the ml
profile so it does not compete with Conductor's UI port.

## M6 — Azure mode

### 63. Managed identity first; an API key is the exception, not the default
**Why:** Every adapter calls `credential_for(key, service)`, which returns a key only when one is
configured and otherwise the shared `DefaultAzureCredential`. On AKS that resolves to a workload
identity: the pod trades its Kubernetes service-account token for an Entra token. The payoff is
countable — the whole deployed system holds exactly **two** secrets, the database password and the
JWT signing key, and both come from Key Vault through the CSI driver. There is no key for Foundry,
Document Intelligence, Content Safety, Storage, Search or Azure ML anywhere: not in the image, not
in a manifest, not in the repository. A key is still supported because a developer testing against
a real service from their laptop has no managed identity to use.

### 64. A configured service that fails is an error, never a quiet fallback to demo
**Why:** The tempting behaviour is to catch the exception and fall back to the demo reader, so the
case keeps moving. That would be the worst outcome available: the case would look normal, carry
confident-looking numbers, and have been read by something nobody chose. "Not configured" and
"configured and broken" are different states and are treated differently — the first is a normal
deployment shape that the Settings screen names, the second raises. Content Safety is the one
deliberate exception, and even there the result is a recorded third state ("unavailable"), not a
silent pass.

### 65. `prebuilt-layout`, not `prebuilt-document` — our schema stays the contract
**Why:** `prebuilt-document` returns key-value pairs the service inferred. Taking them would put a
second, unversioned schema in the middle of a system whose field names are configuration, whose
rule packs are written against those names, and whose prompt versions are pinned per document type.
We ask for words, lines, polygons and confidences, and do the field mapping ourselves against the
schema we version.

### 66. The model's answer is grounded against the document, not self-reported
**Why:** It is easy to ask a model to return the source line beside each value. It is also
worthless: a model that invents a value will invent a citation for it. So `FoundryExtractor` asks
only for values and then looks each one up in the document's own lines. A value that is found
carries the line it came from, which feeds the label signal; a value that is not found carries
nothing, the grounding signal collapses to zero, and the field goes to a person. The difference is
between a system that reports a hallucination and one that launders it.

### 67. Both detectors run, and either one flagging is enough
**Why:** Azure Prompt Shields does not replace the local pattern set, it joins it. Two detectors
with different failure modes catch more than the better one alone, and the local one keeps working
when the service is unreachable. The combination is a logical OR, not an average and not a vote,
because these detect a deliberate attack: a miss costs far more than a false alarm, and a false
alarm costs one extra pair of human eyes on a KYC file.

### 68. `httpx` for Content Safety rather than the Content Safety SDK
**Why:** Prompt Shields moves between preview API versions faster than the SDK follows, and `httpx`
is already a dependency with the async client the rest of the app uses. Two small, explicit POST
bodies are easier to read — and to fake in a test — than a wrapper whose model classes change shape
between releases. The API version is pinned in code, so a guardrail's behaviour cannot change
without a code review.

### 69. Document links are short-lived, user-delegation SAS URLs
**Why:** The viewer is an `<iframe>`, and an iframe cannot send an `Authorization` header — which is
why M1 added a `?token=` query parameter to the local file endpoint. In Azure mode the browser
fetches from storage directly with a SAS generated per request, after the API has already
authorised the user. Fifteen minutes: long enough to read a document, short enough that a URL in a
browser history is useless by the time anyone finds it. The signature uses a **user delegation
key**, which Entra issues and expires, so it is traceable to the identity that asked for it —
unlike an account-key signature, which is anonymous and valid until the key is rotated.

### 70. Hybrid search, not pure vector
**Why:** A policy lookup often contains an exact token — a citation, a licence type, a rule code —
and pure vector search is precisely the thing that loses exact tokens. Keyword search alone misses
"lapsed" against "expired". Azure AI Search fuses both, so they cover each other's failure. The
score it returns from a hybrid query is a fused rank, **not** a cosine similarity, so the adapter
recomputes the cosine against the stored vector rather than comparing a rank score against a
similarity threshold and getting nonsense.

### 71. The AI Search adapter is written and tested, and deliberately not deployed
**Why:** A free AI Search service is one per subscription, and this subscription's belongs to
another system. Deploying Wathiq's own would mean paying about USD 74/month for a Basic service to
replace a pgvector retriever that already returns real policy citations. `deployAiSearch` is
`false`, the pgvector retriever stays the default, and `app/azure/search.py` exists behind the flag.
The honest claim is "the adapter is written and tested; I chose not to pay for a second search
service", which is a better engineering answer than either pretending or deleting the code.

### 72. Azure embeddings ask for 256 dimensions to fit the column that already exists
**Why:** `policy_chunks.embedding` is `vector(256)` and a 1536-number vector does not fit in it.
The obvious response is a migration; the better one is that `text-embedding-3-*` can return a
shortened vector on request, so we ask for exactly 256 and the Azure embedder drops into the
existing schema with no migration and no second column. A truncated vector is no longer unit
length, so it is renormalised — without that, every similarity in the system would read low, and
`cosine()` is a plain dot product precisely because it assumes unit vectors. Switching embedders is
still a re-index: vectors from two different models are not comparable, which is why the embedder
version is recorded per chunk.

### 73. Entra is the authority on roles; the local row is a cache
**Why:** The app role in the token wins over whatever the database says, and it is rewritten on
every sign-in. That keeps "remove the app role in Entra" working as a way to take access away,
which is the reason a bank wants Entra in front of this at all. A user who has been granted a role
and never signed in is created on the spot, with an unusable password hash so the account cannot
also be reached by the local password path. A token carrying no recognised Wathiq role is
**refused**, not given the lowest role: silently downgrading would turn a misconfigured app
registration into a person quietly holding permissions nobody granted.

### 74. The calibration fit runs as an Azure ML job for provenance, not for speed
**Why:** The fit is ninety lines of gradient descent that takes milliseconds; submitting it to a
cluster is slower, and that is fine, because speed was never the point. A managed job records the
code, the environment, the inputs, an owner and a run id — so "which curve is in production and
what was it fitted on" stops being answered from memory. The job runs `app/quality/fit_job.py`,
which calls the *same* `calibration.fit()` the in-process path calls: two implementations of a
calibration curve is two curves. The "do no harm" guard is applied to the remote result as well,
so a fit that scores worse than the raw confidence is discarded wherever it was computed.

### 75. Tracing is additional to the audit trail, not a replacement for it
**Why:** They answer different questions. The append-only event log in PostgreSQL answers "what
happened to *this case*, and who did it" — that is what an auditor reads, and it is inside the
bank. Traces answer "why was this slow, which tool call hung, how often does the critic disagree
*across all cases*". Both exist. What crosses the boundary is constrained: spans carry ids, verdicts
and counts, never document text or field values, because a trace leaves the building and the
guardrails layer produces a tokenised `log_text` that is the only text allowed near a log.
`span()` is a no-op context manager when tracing is off, so no call site has to ask.

### 76. PostgreSQL is reachable from Azure, and that is stated rather than hidden
**Why:** The demo's database is protected by a password and TLS, with a firewall rule allowing
Azure services. A bank deployment puts it behind a private endpoint in a VNet the cluster joins,
with no public path at all. That is a network design rather than a line of Bicep, and it is out of
scope here — so it is named in `infra/README.md` under "What this is not", beside the two other
gaps (no NetworkPolicy, Key Vault purge protection off so the demo can be torn down). A demo that
claims to be production-ready is worse than one that does not.

### 77. The deployment's safety rule is enforced by scope, not by care
**Why:** This subscription holds a working system in `filingsiq-rg`. "Be careful not to touch it"
is not a control. Three things make it one: `main.bicep` deploys at **resource-group scope**, so it
cannot reach outside the group it is given; `deploy.sh` and `teardown.sh` check the group name
against an exact-match allow-list; and `teardown.sh` additionally requires the tags Bicep stamps on
the group and makes the operator type the name back. Wathiq also creates its own copy of every
service rather than reusing one, so nothing is shared and nothing can be broken by sharing. The
guards are tested: pointing teardown at `filingsiq-rg` is refused at the first check.

### 78. Wathiq's model deployments sit on quota pools the existing system does not use
**Why:** Azure OpenAI capacity is granted per subscription, per region, per model, per SKU — not per
account. So a *second account* is harmless, but a deployment drawing on a pool something else
depends on can throttle it. The existing system uses `gpt-4o` Standard and `text-embedding-3-small`
GlobalStandard. Wathiq therefore deploys `gpt-4o-mini` Standard and `text-embedding-3-small`
**Standard** — different pools, measured as empty before deploying. This is invisible coupling: it
does not appear in any template, in any resource graph, or in a code review. It is recorded in
`modules/openai.bicep` next to the parameters that would break it.

### 79. Quality Lab diagnostics never inherit deployment providers
**Why:** The Quality Lab and CI share a reproducible synthetic suite. Resolving `get_ocr()` and
`get_extractor()` inside that suite worked in demo mode but, in Azure, issued dozens of synchronous
Document Intelligence and Foundry calls from one browser request. The results stopped being
reproducible, the run consumed real quota, and Document Intelligence eventually throttled it with
HTTP 429. The suite now injects `DemoOcr` and `DemoExtractor` explicitly. Live-provider health and
contract checks remain separate, opt-in Azure smoke tests; a diagnostic regression run and a cloud
availability test are different claims and must not be conflated.
