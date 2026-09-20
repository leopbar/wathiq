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
