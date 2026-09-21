# Wathiq Architecture Decision Record

**Document type:** Consolidated Architecture Decision Record (ADR) compendium
**System:** Wathiq · واثق — assurance-first document processing
**Status:** Accepted; reflects the implementation through M6
**Baseline date:** 2026-09-21
**Decision owners:** Wathiq engineering and product architecture
**Audience:** Engineers, security reviewers, operators, auditors, and future maintainers

---

## 1. Purpose and authority

This document is the single, self-contained architectural decision record for Wathiq. It explains
not only what the system contains, but why its boundaries, technologies, controls, and failure
behaviour were selected. It consolidates the 79 chronological notes in `DECISIONS.md` into stable,
domain-oriented ADRs. The chronological file remains useful as a build diary; this compendium is
the architectural reference.

An ADR records a decision, not a marketing claim. “Implemented” means the repository and tests
contain the behaviour. “Deployed” means the behaviour has also been exercised in the live Azure
environment. Deliberate limitations are included because an omitted limitation is itself an
architectural risk.

### Status vocabulary

| Status | Meaning |
|---|---|
| **Accepted** | The decision governs the current implementation. |
| **Accepted with constraints** | The decision is active, but named production gaps remain. |
| **Deferred** | The design or adapter exists, but activation is intentionally postponed. |
| **Superseded** | A later ADR replaces the decision; retained for history. |
| **Proposed** | Not yet an implementation commitment. |

### System quality priorities

When priorities conflict, Wathiq uses this order:

1. Do not turn an unperformed check into a pass.
2. Preserve an auditable link from decision to evidence.
3. Prefer a human review over a confident but unsupported answer.
4. Keep the offline demo and Azure deployment on one codebase.
5. Minimise credentials, mutable infrastructure, and operational components.
6. Optimise latency and cost only after the controls above remain true.

---

## 2. Decision summary

| ID | Decision | Status |
|---|---|---|
| ADR-001 | One codebase, capability interfaces, independently selectable providers | Accepted |
| ADR-002 | Separate durable business orchestration from AI reasoning | Accepted |
| ADR-003 | LangGraph is the explicit, checkpointed reasoning state machine | Accepted |
| ADR-004 | Two process schedulers execute one canonical set of business steps | Accepted |
| ADR-005 | FastAPI, Pydantic v2, async SQLAlchemy, psycopg 3, and SSE | Accepted |
| ADR-006 | PostgreSQL is the transactional, checkpoint, and vector data platform | Accepted |
| ADR-007 | One database-enforced append-only event stream is the audit source | Accepted with constraints |
| ADR-008 | React/Vite internal SPA with an owned accessible design system | Accepted |
| ADR-009 | Documents use abstract storage, ADLS in Azure, and authorised short-lived delivery | Accepted |
| ADR-010 | Schema-first extraction, independent grounding, explainable confidence, and abstention | Accepted |
| ADR-011 | Guardrails run before interpretation; processing text and observability text are separate | Accepted |
| ADR-012 | External capabilities are isolated MCP servers with enforceable least privilege | Accepted |
| ADR-013 | Versioned rules and evidence-bearing policy retrieval govern validation | Accepted |
| ADR-014 | Reviewer outcomes drive quality regression, prompt governance, and calibration | Accepted |
| ADR-015 | Authentication providers vary; one RBAC model governs authorisation | Accepted with constraints |
| ADR-016 | Workload identity and Key Vault replace service credentials in Azure | Accepted |
| ADR-017 | Azure services implement existing contracts; activation is explicit and fail-closed | Accepted |
| ADR-018 | Multi-stage containers, Compose locally, ACR/AKS/Helm in Azure | Accepted |
| ADR-019 | Resource-group-scoped IaC, isolation, cost restraint, and explicit production gaps | Accepted with constraints |
| ADR-020 | At-least-once work is controlled with checkpoints and deterministic idempotency | Accepted |
| ADR-021 | Containerised CI, real PostgreSQL integration tests, and negative controls are release gates | Accepted |
| ADR-022 | Operational tracing supplements—but never replaces—the case audit trail | Accepted |
| ADR-023 | Azure DNS, automatic public TLS, and HTTP-to-HTTPS redirection protect the demo endpoint | Accepted with constraints |

---

## ADR-001 — One codebase with capability interfaces

**Status:** Accepted
**Scope:** Application architecture, environment portability, provider selection
**Decision drivers:** Offline demonstration, Azure fidelity, testability, honest degradation

### Context

Wathiq must run without cloud credentials on a developer laptop and must also exercise real Azure
services. Separate “demo” and “cloud” applications would inevitably diverge in schemas, business
rules, UI behaviour, and failure handling. Direct Azure SDK calls from graph nodes would make the
offline path a web of mocks rather than a real operating mode.

### Decision

Maintain one application and put every external capability behind a narrow interface: OCR,
extraction, embedding, retrieval, storage, safety, calibration execution, tracing, authentication,
and process scheduling. Demo and Azure implementations return the same domain types. Provider
selection is configuration, not a fork in business logic.

`WATHIQ_MODE=azure` enables cloud-aware factories, but each service also requires its own endpoint.
An absent endpoint is an intentional “not configured” state and retains the demo implementation.
A configured provider that fails raises an error; it never silently substitutes a demo result.
The Settings screen reports which implementation actually answered.

### Alternatives rejected

- **Two applications:** fastest initially, but produces two behaviours and an unauditable demo.
- **Azure calls embedded in nodes:** couples domain logic to SDKs and prevents isolated testing.
- **Automatic fallback after Azure failure:** preserves uptime by concealing that the selected
  control did not run; this violates the first quality priority.

### Consequences and controls

The architecture carries more interfaces and factories, and every provider must be tested against
the same contract. In return, mixed configurations such as real OCR plus deterministic extraction
are valid and observable. Demo mode is tested in a fresh subprocess to prove it imports no Azure
SDK. Provider failures remain distinguishable from unconfigured services.

### Revisit when

A provider requires semantics that cannot be represented honestly by the shared domain contract.
Extend the contract first; do not leak provider-specific objects through the graph.

---

## ADR-002 — Separate business orchestration from AI reasoning

**Status:** Accepted
**Scope:** Workflow boundaries, ownership of state, human tasks
**Decision drivers:** Durable waits, inspectability, specialised responsibilities

### Context

A KYC refresh combines two different problems. The business process must schedule intake, retries,
human work, SLA escalation, posting, and sealing. The reasoning process must read documents, fan out
extraction, invoke tools, validate fields, and pause with its complete cognitive state intact.
Forcing both into either a workflow engine or an agent framework weakens one side.

### Decision

Orkes Conductor is the durable business-process layer. LangGraph is the reasoning layer inside the
agent task. Conductor decides what business step happens next; LangGraph decides what the evidence
means. The Conductor workflow ID is also the LangGraph thread ID and is written to the case before
reasoning begins. A single identifier therefore joins business history, reasoning checkpoints,
review work, postings, and audit events.

Conductor receives only the case identifier. Workers load protected data from PostgreSQL after
authorisation; customer fields and document text are never workflow payloads.

### Alternatives rejected

- **Everything in LangGraph:** lacks the intended operations surface and durable business timers.
- **Everything in Conductor:** task graphs cannot express typed reasoning state and checkpointed
  model/tool loops cleanly.
- **Independent identifiers:** creates a reconciliation problem precisely where auditability is
  most important.

### Consequences and controls

There are two state machines to operate and explain. Their contract is narrow: one agent task, one
shared identifier, and explicit outcomes. The workflow definition, UI step list, and About-screen
diagram are generated from the same canonical definition and tested for agreement.

### Revisit when

The organisation standardises on another durable orchestrator. Preserve the `ProcessEngine`
contract and the shared-identifier invariant during any migration.

---

## ADR-003 — LangGraph as an explicit, checkpointed reasoning graph

**Status:** Accepted
**Scope:** AI control flow, parallelism, review interruption, evidence state
**Decision drivers:** Resumability, typed state, bounded autonomy, explainability

### Context

Reasoning can pause for hours while a reviewer acts. It must resume exactly where it stopped,
retain tool observations, and make branching visible. A free-form agent loop or plain Python call
chain makes state persistence and audit reconstruction application-specific.

### Decision

Use LangGraph with PostgreSQL checkpoints. The compiled graph is:

`ocr → guardrails → supervisor → parallel extract workers → critic → investigator → validate →
review gate/finalize`.

The supervisor-worker pattern fans out one extraction worker per document. Append reducers collect
independent findings and tool calls; fields use merge-by-document-and-name so critic revisions
replace earlier values. The investigator uses a bounded ReAct loop of at most six actions.
Self-correction is limited to two local repair attempts. The review gate uses `interrupt()` and is
side-effect-free above the interruption because LangGraph re-executes that node on resume. Review
rows are created by the runner outside the graph.

Evidence displayed in the Assurance tab is read from the checkpoint rather than copied into a
second reporting model. Redelivered agent tasks detect an existing checkpoint and continue it;
they do not apply the initial state twice.

### Alternatives rejected

- **Plain functions plus custom persistence:** recreates checkpoint, branch, and resume semantics.
- **Role-playing multi-agent frameworks:** obscure the actual transition and state ownership.
- **Unbounded agent action:** creates unpredictable cost and an unacceptable tool-use surface.

### Consequences and controls

Developers must understand reducer and interrupt semantics. Every node is traced; the live graph is
generated from the compiled object; geometry and assurance evidence are tested end to end through a
checkpoint. Missing checkpoints on seeded cases are reported honestly rather than fabricated.

### Revisit when

Graph volume or checkpoint retention exceeds PostgreSQL capacity, or a new framework provides
equivalent explicit state, durable interruption, and migration tooling.

---

## ADR-004 — Two schedulers, one canonical business process

**Status:** Accepted
**Scope:** Process execution, local operability, crash recovery, SLA handling
**Decision drivers:** Durable production shape without making the laptop demo fragile

### Context

Conductor provides durable queues, retry/redelivery, HUMAN tasks, WAIT timers, and an operations
view, but requires roughly 2 GB of memory. Making it mandatory would make the core demo unreliable
on the target development machine. Writing two versions of the business steps would be worse.

### Decision

Provide `conductor`, `inprocess`, and `auto` process-engine modes. Both schedulers call the same
functions in `process/tasks.py`, write the same events, and use the same domain transitions. Every
case records the engine that started it. A reviewer decision always returns to that recorded engine,
not whichever engine is configured later.

Under Conductor, the HUMAN task and SLA WAIT task run in parallel. The join waits for the human task
only: a timer may escalate, but can never decide. Completing review also releases the outstanding
WAIT. An overdue unclaimed task moves to a supervisor; a claimed task remains with its reviewer and
is marked late. In-process execution performs the same transitions and runs a startup recovery scan
for cases left in active states.

### Alternatives rejected

- **Conductor only:** operationally heavy for the mandatory offline demo.
- **In-process only:** cannot substantiate durable workflow-engine integration.
- **Airflow:** oriented to scheduled batch work, not long-lived human tasks.
- **Temporal:** technically suitable, but Conductor matches the target operating environment.

### Consequences and controls

The fallback scheduler has weaker crash guarantees, but this is visible per case. `auto` may fall
back only when Conductor is not configured/reachable and reports that choice. The separate worker
uses the same application image as the API so reasoning versions cannot drift.

### Revisit when

Conductor becomes mandatory infrastructure or the deployment requires horizontal worker scaling;
at that point disable `auto` in production while retaining in-process mode for development.

---

## ADR-005 — Async FastAPI service and unidirectional live updates

**Status:** Accepted
**Scope:** API, validation, database access, browser progress
**Decision drivers:** Concurrent I/O, schema reuse, simple proxy-compatible streaming

### Decision

Use FastAPI with Pydantic v2, SQLAlchemy 2 async, and psycopg 3. Pydantic schemas validate API
payloads and structured model output so field contracts do not drift. Psycopg 3 is also the driver
used by the LangGraph checkpointer, avoiding a second PostgreSQL stack.

Use Server-Sent Events for progress because messages travel server-to-browser only. SSE is ordinary
HTTP, reconnects natively, and passes through the current Nginx/load-balancer path without a second
protocol. Browser-owned GETs that cannot set an Authorization header may use a query token only on
the explicitly enumerated preview, export, and event-stream routes. All writes remain header-only.

Request sessions roll back on exit, including read-only requests, so pooled connections cannot
remain idle in transaction. Checkpointer schema setup happens before traffic is accepted.

### Alternatives rejected

Django adds facilities the service does not use; Flask would require more manual async and schema
work. WebSockets add two-way state and operational complexity; polling creates load and stale UX.

### Consequences and revisit triggers

Query tokens can appear in history/logs and are a demo compromise; production document delivery is
handled by short-lived SAS. Revisit SSE if clients need bidirectional collaboration rather than
status updates.

---

## ADR-006 — PostgreSQL as the unified data platform

**Status:** Accepted
**Scope:** Transactional records, checkpoints, vector retrieval, migrations
**Decision drivers:** Consistency, operational simplicity, sufficient scale

### Decision

Use PostgreSQL 16 with pgvector for domain records, review work, postings, configuration, events,
LangGraph checkpoints, policy chunks, and example embeddings. Use `VARCHAR` plus CHECK constraints
for application enums rather than native PostgreSQL enum types, keeping migrations reversible.
Use one database transaction for related business/audit writes.

At the current thousands-of-chunks scale, pgvector is sufficient and avoids a separate vector
service, backup, connection, and consistency boundary. Embeddings are 256-dimensional to match the
existing column; shortened Azure embeddings are renormalised before cosine operations. Changing
embedding models requires a re-index and the model/version is recorded.

### Alternatives rejected

A dedicated vector database adds cost without current scale benefit. Mock databases cannot exercise
PostgreSQL-only functions, constraints, triggers, or checkpoint behaviour. Native enums are harder
to reverse safely.

### Consequences and controls

Database capacity affects several subsystems at once, making backup and monitoring important. Tests
use a real disposable database and refuse names not ending in `_test`. Azure AI Search is the
designed scale-out path for heavier hybrid search, but is currently deferred for cost reasons.

### Revisit when

Vectors reach millions, hybrid query latency violates the SLO, checkpoint retention dominates the
primary database, or independent scaling/recovery objectives justify separation.

---

## ADR-007 — One append-only event stream as audit truth

**Status:** Accepted with constraints
**Scope:** Audit, timeline, integrity, evidence retention

### Decision

Use one `events` table for the detailed audit log and the case timeline. Each action by a human,
agent, process engine, or system appends a monotonically sequenced row. Application code never
updates or deletes an event, and a database trigger rejects row-level UPDATE and DELETE operations.
An integrity endpoint reports whether the trigger exists and states what it does not prove.

Tracing is not audit. Checkpoint state is not audit. The event stream answers who did what to a
specific case; checkpoints preserve resumable reasoning evidence; traces diagnose distributed
performance. Each remains authoritative for its own question.

### Alternatives rejected

Separate timeline and audit tables can disagree. Application convention alone is not a control.
Copying all graph evidence into reporting tables creates a second truth that can drift.

### Consequences and limitations

The application cannot rewrite individual events, but a database owner can drop the trigger and
`TRUNCATE` bypasses row triggers. This is application-level immutability, not cryptographic tamper
evidence. Seed resets deliberately require owner-level complete truncation rather than selective
history editing.

### Revisit when

Compliance requires tamper evidence or external non-repudiation. Add a hash chain, signed ledger,
immutable storage export, and independent verification without replacing the operational event API.

---

## ADR-008 — React/Vite internal console and owned design system

**Status:** Accepted
**Scope:** Web architecture, accessibility, explanatory UI

### Decision

Build a React + TypeScript + Vite single-page application. Serve static production assets with
unprivileged Nginx. Use Tailwind CSS v4 and small hand-written components on Radix primitives rather
than a general-purpose enterprise component suite. The product is an authenticated internal console;
server-side rendering, SEO, and a production Node server add no value.

The UI must expose provenance rather than only outcomes: provider names, process engine, confidence
signals, source regions, tool results, policy citations, rule versions, reviewer state, and audit
events. Diagrams and step lists come from running definitions where practical to prevent drift.

### Alternatives rejected

Next.js adds server runtime and routing complexity. Material UI/Ant Design would impose a generic
visual language. Generated component code introduces install-time tooling and weakens ownership.

### Consequences and controls

The team owns accessibility and component maintenance. Radix supplies difficult keyboard/focus
primitives. Reduced-motion CSS excludes Mermaid measurement nodes after a universal selector broke
diagram geometry. The large Mermaid/Recharts bundle is accepted for the internal network and is a
future lazy-loading target. TypeScript remains on the version supported by the OpenAPI generator.

### Revisit when

Public delivery creates SEO/first-render requirements, or bundle telemetry shows material user
impact. Prefer route-level lazy loading before changing framework.

---

## ADR-009 — Authorised document storage and faithful browser rendering

**Status:** Accepted
**Scope:** Upload, storage, preview, content delivery, document geometry

### Context and decision

`StorageBackend` provides save/read/exists/signed-URL operations. Demo mode uses a guarded local
folder. Azure mode uses ADLS Gen2 with hierarchical namespace for per-case directories, ACL-ready
boundaries, and atomic rename capability. Documents are opaque bytes to storage; the database keeps
the authoritative filename, MIME type, size, page count, and storage path.

Uploads accept PDF, PNG, JPEG, and TIFF up to 25 MB. Nginx and FastAPI enforce the same ceiling so
the proxy cannot reject a valid API upload first. In Azure, an authorised API request returns a
15-minute read-only SAS signed with an Entra user-delegation key. The SAS includes response overrides
for the recorded MIME type and inline filename, allowing already-stored opaque objects to render
correctly. PDFs use the browser frame; images use an `<img>` with natural aspect ratio so normalised
OCR bounding boxes align with pixels. The raw-file action remains available.

### Alternatives rejected

Public blobs violate access control. Account-key SAS lacks identity provenance and long-lived keys
expand blast radius. Proxying every Azure byte through FastAPI wastes compute. Treating every file
as a PDF iframe fails for image content and distorts geometry.

### Consequences and controls

SAS URLs may be copied while valid, so lifetime and permissions are deliberately narrow. The API
authorises before issuing one. The live 3.1 MB JPEG case verified upload, correct `image/jpeg`
delivery, inline disposition, image rendering, and field-highlight alignment.

### Revisit when

Production requires malware scanning, content-disarm/reconstruction, legal retention, watermarking,
or browsers must preview TIFF consistently. Add those stages without weakening the storage contract.

---

## ADR-010 — Schema-first extraction and explainable confidence

**Status:** Accepted
**Scope:** OCR, extraction, validation, grounding, review thresholds

### Decision

Document-type configuration owns the field schema. Pydantic models are built from that schema and
the same schema constrains Foundry structured output. Document Intelligence uses `prebuilt-layout`
for words, lines, polygons, and confidence; Wathiq performs field mapping rather than accepting an
external, unversioned key-value schema.

The model returns values only. Wathiq independently locates each value in OCR lines; the model is
not trusted to self-report its evidence. A missing match removes grounding and geometry rather than
inventing a citation. Repairs search only near the field's own label, never the entire page.

Raw confidence combines observable signals: page read quality, exact grounding, label proximity,
shape validation, critic agreement, and—when available—per-value read confidence. Weights are
renormalised over signals present. Case confidence averages fields with values; completeness is
handled by rules. Calibration maps raw confidence to empirical correctness only after reviewed
labels exist. Until then the UI labels scores as raw. Low/critical uncertainty, disagreement,
missing checks, or guardrail hits route to a human.

### Alternatives rejected

Model self-confidence is not calibrated evidence. Model-generated citations can hallucinate with
the value. Whole-page repair can select a valid but wrong field. Random demo confidence is visually
plausible and semantically empty.

### Consequences and revisit triggers

The pipeline prefers empty/needs-review over a syntactically valid guess. More fields therefore
reach humans, by design. Revisit signal weights only through measured reviewer outcomes and preserve
per-signal explanations during any model change.

---

## ADR-011 — Guardrails before interpretation and privacy-separated text

**Status:** Accepted
**Scope:** Prompt injection, content safety, PII, logs and traces

### Decision

Run guardrails immediately after OCR and before classification or extraction. Combine local Prompt
Shield patterns with Azure Prompt Shields, and local content rules with Azure Content Safety. A hit
from either detector is sufficient; unavailable remote checks are recorded as unavailable, never
passed. Azure calls use explicit, pinned REST API versions through `httpx` where the preview SDK
surface is less stable.

Guardrails produce two text forms. `clean_text` retains values and is the only form processed by
the pipeline. `log_text` replaces identifiers with stable tokens and is the only text allowed near
logs, traces, or diagnostic fixtures. Document data remains access-controlled in the case store;
observability data is intentionally less sensitive.

### Alternatives rejected

Replacing local detectors with cloud-only checks removes protection during outages. Averaging
security verdicts can vote away a real attack. Feeding tokenised text to extraction protects logs by
destroying the business result. Logging raw text creates unnecessary secondary copies.

### Consequences and revisit triggers

Logical OR increases human-review volume, which is preferable to an undetected instruction attack.
Detector versions and outcomes must remain visible. Revisit thresholds with a labelled red-team set,
not by suppressing alerts operationally.

---

## ADR-012 — MCP isolation and enforceable least privilege

**Status:** Accepted
**Scope:** Tool integration, external checks, write separation

### Decision

Expose document store, company registry, sanctions, and core banking as four MCP servers in separate
processes/containers. Each exposes only its own tool contract. The document volume is read-only;
registry and sanctions are read-only; core banking alone can write. The investigator receives no
core-banking address, and the API broker rejects that tool name independently. DNS-rebinding
protection remains enabled with explicit allowed hosts.

Simulated integrations are labelled `Simulated` in the API, UI, and documentation. The protocol and
contracts are real; the data sources are synthetic. If a tool call fails, the result is “not
checked,” is recorded, and can raise a finding. There is no local imitation that converts failure
into success.

### Alternatives rejected

Four functions in the API provide organisation but not security separation. One all-powerful tool
server increases blast radius. Silent local fallback manufactures assurance.

### Consequences and revisit triggers

More containers require health checks, routing, and version management. In return, permissions are
concrete and independently deployable. When replacing simulated sources, preserve tool contracts,
authentication boundaries, and explicit provenance labels.

---

## ADR-013 — Versioned rules and evidence-bearing policy retrieval

**Status:** Accepted; Azure AI Search activation deferred
**Scope:** Rules, policy citations, embeddings, retrieval

### Decision

Store common validation logic in semantic-versioned YAML rule packs per document type. Record the
pack/version used on each case. Rules that need whole-case collection semantics use named Python
checks referenced by configuration. A rule that lacks inputs or cannot execute returns
`evaluated: false` with a reason; it never passes by default. Findings cite retrieved policy.

Chunk policy Markdown by section because a section is the citation unit. An explicit section ID is
looked up exactly; uncited findings use similarity search with a minimum quality bar; weak matches
produce no quote rather than a misleading one. Demo retrieval uses normalised 256-dimensional
hashed lexical embeddings in pgvector. The Azure Search adapter performs hybrid keyword/vector
retrieval and recomputes cosine because a fused rank is not a similarity score.

### Alternatives rejected

Hard-coded business rules require deployments for policy changes. Arbitrary character chunks make
unreadable citations. Pure vectors lose exact rule codes; pure keyword search loses semantic
equivalence. Treating “not evaluated” as pass conceals missing evidence.

### Consequences and constraints

Azure AI Search is implemented and tested but not deployed: the subscription’s free service belongs
to another system and Basic would cost roughly USD 74/month to replace working pgvector. Activation
remains a configuration decision when scale justifies it.

### Revisit when

Policy volume/query rate exceeds pgvector targets, or operational need justifies the Azure Search
cost. Re-run retrieval evaluations before switching.

---

## ADR-014 — Reviewer-derived quality, prompt governance, and safe calibration

**Status:** Accepted
**Scope:** Evaluation, regression, prompt versions, confidence calibration, ML provenance

### Decision

Use completed human review outcomes as ground truth: accepted fields are positive; corrected fields
are negative; rejected cases are excluded from positive labels; straight-through fields are not
pretended to have been checked. Preserve correction input, schema, source, and expected output during
the review transaction. Deduplicate repeated capture. Local replay reads the database; CI consumes
only an explicitly exported synthetic regression set.

Evaluation bands share one runner between API and CI and contain assertions capable of failing.
Negative controls prove the gate rejects broken results. One document is one diagnostic observation,
not one sample per field. Prompt correctness and wording sensitivity are separate metrics; demo
extraction does not claim prompt sensitivity because it does not consume prompts.

Calibrate with an explainable two-parameter Platt curve. Reject any fit whose Brier score is worse
than raw scores. Record every attempt, including refused fits. MLflow logging is optional. Azure ML
runs the same fitting function as an auditable command job for provenance, not speed.

### Alternatives rejected

Manual labelling duplicates operational work. Counting unchecked cases as correct creates feedback
bias. Scikit-learn adds a large numeric stack for a tiny fit. Separate local/cloud fitting logic
would produce two meanings of confidence.

### Revisit when

Enough labelled data supports isotonic or segmented calibration, provided out-of-sample evaluation
proves improvement and the “do no harm” guard remains.

---

## ADR-015 — Provider-independent authentication, single RBAC model

**Status:** Accepted with constraints
**Scope:** Identity, browser login, roles, token transport

### Decision

Keep authentication provider selection separate from Azure service mode. Local/demo authentication
uses bcrypt-hashed accounts and Wathiq-signed JWTs, including audited one-click role login. Entra
mode validates tenant, audience, issuer, signature, and app roles. Both resolve to the same five
application roles: operations officer, reviewer, supervisor, administrator, and auditor.

In Entra mode the token role is authoritative. The local user row is a just-in-time cache, rewritten
from the claim on sign-in and created with an unusable password hash. Missing/unrecognised roles are
rejected, not silently downgraded. Authorisation remains server-side on every endpoint.

### Alternatives rejected

Requiring Entra for the offline demo makes it unusable. Azure mode automatically implying Entra
made the live environment inaccessible before browser registration. Maintaining different role
models doubles policy and test surface.

### Consequences and known gap

The deployed M6 demo uses real Azure providers with local authentication. Entra token validation and
role mapping are built and tested, but the browser OIDC/MSAL redirect leg needs an app registration
and is not yet implemented. This deployment must not be described as production SSO.

### Revisit when

An Entra app registration is approved. Add PKCE browser sign-in, logout, token renewal, and tenant
deployment documentation without changing application roles.

---

## ADR-016 — Workload identity and Key Vault for Azure credentials

**Status:** Accepted
**Scope:** Service authentication, secret delivery, RBAC

### Decision

Use AKS workload identity via the cluster OIDC issuer and a federated Entra credential. Azure SDK
factories use `DefaultAzureCredential` unless an explicit developer key is configured. Assign only
the data-plane roles required by Foundry, Document Intelligence, Content Safety, ADLS, and Azure ML.
Mount the database password and JWT signing key from Key Vault through the CSI driver. These are the
only two application secrets in the deployed system.

The deployment identity uses Key Vault Secrets Officer only to create/update those values; runtime
identity permissions are narrower. Deployment retries boundedly while RBAC propagates.

### Alternatives rejected

Service keys in Kubernetes secrets are long-lived, broadly copyable, and rotate operationally.
Account keys for ADLS make access anonymous at the identity layer. Subscription Owner does not
grant Key Vault data-plane access and is not treated as runtime permission.

### Consequences and revisit triggers

The identity chain adds OIDC/federation/RBAC dependencies but removes service credentials from code,
images, manifests, and repository. Retain key support only for intentional developer access. Review
role assignments whenever an adapter gains a new operation.

---

## ADR-017 — Explicit Azure service adapters and fail-closed activation

**Status:** Accepted
**Scope:** Azure AI and platform selection

### Decision

Azure implementations preserve existing application contracts:

- Azure OpenAI/Foundry `gpt-4.1-mini` for strict structured extraction.
- `text-embedding-3-small` at 256 dimensions for semantic embeddings.
- Document Intelligence `prebuilt-layout` for OCR and geometry.
- Content Safety and Prompt Shields combined with local detectors.
- ADLS Gen2 for documents.
- Azure Monitor/OpenTelemetry for operational traces.
- Azure ML command jobs for calibration provenance.
- Azure AI Search adapter available but deployment disabled.

Endpoints activate services independently. A configured service failure is an error, except safety
services may return the explicit third state `unavailable`, which routes conservatively. Model
deployment preflight is authoritative over catalogue listings. Model/SKU capacity is chosen from
quota pools not used by the existing subscription workload.

### Alternatives rejected

Provider-native inferred document fields would displace the versioned Wathiq schema. A single global
“Azure works” switch cannot describe partial deployments. Quiet fallback creates false provenance.

### Consequences and constraints

Service API versions, deployments, and dimensions become controlled configuration. Azure ML compute
is opt-in because this subscription has zero AML compute quota; the workspace still supplies job
provenance capability. AI Search remains off for cost. Model choices must be revalidated against
current region availability and shared quota before redeployment.

### Revisit when

Models are deprecated, measured quality changes, quota ownership changes, or a provider contract
cannot satisfy the grounding and structured-output requirements.

---

## ADR-018 — Containers, Compose, ACR, AKS, and Helm

**Status:** Accepted
**Scope:** Packaging, local runtime, Kubernetes release topology

### Decision

Use multi-stage Dockerfiles with `dev` and `prod` targets. Run containers as non-root users with
health checks and read-only root filesystems where practical. Use Docker Compose for local
development and optional profiles for Conductor, workers, tests, and MLflow. Use the same production
images in ACR and AKS, deployed through Helm.

AKS runs separate Deployments for API, web, and four MCP servers; render the Conductor worker only
when that engine is selected. On the one-node non-HA demo cluster, use `Recreate` strategy to avoid
surge pods exhausting capacity. Database migrations are revision-scoped Jobs; API/worker init
containers wait for schema head; idempotent seed runs after install/upgrade. Nginx configuration is
expanded at startup for release-specific API DNS and writable generated config is mounted over the
read-only image.

### Alternatives rejected

Local host installs create environment drift. Separate dev/prod Dockerfiles drift. Default rolling
surge exceeds the intentionally small cluster. Pre-install migration hooks cannot depend on chart
resources that do not yet exist.

### Consequences and revisit triggers

`Recreate` causes brief deployment downtime and is acceptable only for this demo. Before production,
add multiple nodes/replicas, PodDisruptionBudgets, rolling capacity, autoscaling, and availability
objectives, then restore RollingUpdate.

---

## ADR-019 — Scoped infrastructure, isolation, cost restraint, and named gaps

**Status:** Accepted with constraints
**Scope:** IaC, subscription safety, network posture, cost

### Decision

Provision Azure resources with Bicep at resource-group scope. Wathiq owns a separate resource group
and its own copies of every service; it does not reuse the live `filingsiq-rg` resources. Deploy and
teardown scripts exact-match allowed group names. Teardown additionally validates ownership tags and
requires the operator to type the group name. Guard behaviour is tested.

Deploy the least costly shape that exercises the architecture: one AKS node, PostgreSQL Flexible
Server, ACR, ADLS, Key Vault, monitoring, Azure AI services, and an Azure ML workspace. Keep Azure AI
Search and AML compute disabled until justified. Verify model quota by model, SKU, and region rather
than assuming a separate account means separate capacity.

### Explicit non-production boundaries

PostgreSQL currently permits Azure-service access over TLS rather than using a private endpoint and
VNet-only path. NetworkPolicy is not installed. Key Vault purge protection is disabled to permit
demo teardown. The AKS node and workloads are not highly available. These are documented gaps, not
implicit claims of production readiness.

### Revisit when

Moving beyond a controlled demo. Required work includes private networking/DNS, egress policy,
NetworkPolicy, WAF/TLS ingress, purge protection, backup/restore tests, HA, autoscaling, SIEM export,
and formal cost/SLO ownership.

---

## ADR-020 — Checkpointed, idempotent, auditable side effects

**Status:** Accepted
**Scope:** Redelivery, posting, retries, completion semantics

### Decision

Assume task delivery is at least once. Reasoning resumes existing checkpoints. Posting uses a
deterministic key `<workflow-id>:kyc_refresh:<contract-version>`, enforced both by a UNIQUE database
column and the receiving core-banking service. A retry produces the same key; a deliberate new
workflow or contract version can produce a new one.

Only approved cases post. Approval records whether it came from a named human or a named
straight-through policy—never a fabricated human approver. Every posting attempt creates a row,
including deliberate non-posts such as rejection, missing customer, or unavailable target.
`completed` means posting/auditable non-posting has finished and the process is sealed; the graph
ending at `approved` is not completion.

### Alternatives rejected

Random idempotency keys do not deduplicate retries. Application-only deduplication cannot protect
against a worker dying after the external call. Silence for non-posts is indistinguishable from a
lost task. Marking reasoning completion as case completion skips the business side effect.

### Consequences and revisit triggers

External systems must honour the idempotency contract. New payload semantics require a deliberate
contract-version change and compatibility review. Add an outbox/inbox protocol if future systems
cannot provide receiver-side idempotency.

---

## ADR-021 — Verification is containerised, realistic, and capable of failing

**Status:** Accepted
**Scope:** CI, test databases, security scanning, deployment verification

### Decision

Run CI in containers built from project Dockerfiles. Gates include Ruff and pytest, frontend lint,
TypeScript, production build, MCP tests through the official client, Playwright end-to-end flows,
Bicep compilation with zero warnings, Helm lint/render plus schema validation, ShellCheck, and
gitleaks. A planted-secret canary proves the scanner is not over-allowlisted. Negative quality
controls prove evaluation gates reject broken outputs.

Integration tests use real PostgreSQL in a disposable `_test` database. Milestone verification
includes clean-volume startup because persistent local state previously concealed transaction and
migration defects. Azure adapters have offline contract tests and opt-in live smoke tests. M6 was
validated through public login, upload, real OCR/model/safety/storage calls, full pipeline, review
checkpoint, posting flow, SAS retrieval, and browser rendering.

### Alternatives rejected

Mocking the database misses PostgreSQL functions, triggers, locks, pgvector, and checkpoints.
Template compilation alone misses cloud-provider registration, RBAC propagation, quota, builder,
and runtime DNS failures. A metric with no failing assertion is a dashboard, not a gate.

### Consequences and revisit triggers

CI is heavier but produces evidence proportional to system risk. Add performance, accessibility,
resilience, migration rollback, and restore tests before production SLOs are declared.

---

## ADR-022 — Tracing supplements the audit trail

**Status:** Accepted
**Scope:** Observability, privacy, operational diagnosis

### Decision

Instrument graph nodes, MCP calls, guardrail decisions, and service operations with OpenTelemetry
and export to Azure Monitor when configured. `span()` is a no-op when tracing is disabled so domain
code does not branch on observability. Spans carry identifiers, durations, counts, provider names,
and verdicts—never document text or extracted values.

The append-only event log remains the authoritative case history. Traces answer cross-case latency,
dependency, and reliability questions and may follow different retention/access policies. Logs use
tokenised `log_text` only.

### Alternatives rejected

Using traces as audit makes customer history dependent on sampling and external retention. Logging
raw content expands sensitive-data copies. No-op-free instrumentation causes every call site to
couple to deployment configuration.

### Revisit when

Operational volume requires sampling, a SIEM integration, or formal telemetry retention. Sampling
must never apply to domain audit events.

---

## ADR-023 — Azure DNS and automatic TLS protect the public endpoint

**Status:** Accepted with constraints
**Scope:** Public networking, transport security, certificate lifecycle, AKS deployment

### Context

The original M6 demo exposed nginx directly through an AKS `LoadBalancer` Service at a raw IPv4
address on port 80. Browsers correctly labelled that endpoint unsafe: HTTP provides neither server
identity nor transport encryption, and a public certificate cannot usefully establish application
identity for the mutable raw-IP URL. The fix must preserve the existing public IP and one-node,
cost-constrained cluster while avoiding manually copied certificate secrets.

### Decision

Publish an Azure-managed regional hostname for the existing Service public IP through the AKS
`service.beta.kubernetes.io/azure-dns-label-name` annotation. Run Caddy as a sidecar in the web pod
in front of nginx. The public Service maps ports 80 and 443 to Caddy's unprivileged internal ports;
Caddy redirects every HTTP request—including requests to the legacy IP—to the canonical HTTPS
hostname and proxies accepted HTTPS traffic to nginx over pod-local loopback.

Caddy obtains and renews a publicly trusted ACME certificate. Its certificate and ACME account
state live on a 1 GiB `ReadWriteOnce` persistent volume so pod replacement does not cause needless
reissuance or rate-limit pressure. HSTS is returned for HTTPS responses. HTTP/3 is disabled because
the current Azure Service exposes TCP rather than QUIC/UDP; HTTP/1.1 and HTTP/2 remain enabled.
Nginx preserves the incoming `X-Forwarded-Proto` value when proxying API requests.

The TLS container retains a read-only root filesystem, fixed non-root identity, runtime-default
seccomp, and only the `NET_BIND_SERVICE` capability required by the official Caddy binary. The
application container receives no additional capability.

### Alternatives rejected

Continuing with raw HTTP fails basic confidentiality and identity requirements. A self-signed
certificate still produces browser warnings and creates a manual trust-distribution problem.
Azure Front Door or Application Gateway adds useful production controls but disproportionate cost
and operational surface for this single-node demo. A separate ingress controller plus cert-manager
adds multiple cluster components where a single sidecar is sufficient. Third-party wildcard DNS
would work but adds an avoidable external naming dependency when Azure can own the record.

### Consequences and revisit triggers

The canonical demo URL is
`https://wathiq-dev-fjzpbfjqt27r6.eastus2.cloudapp.azure.com/`; the former IP URL is redirect-only.
Certificate lifecycle is automatic, but the hostname is still an Azure regional demo name and the
web Deployment uses `Recreate`, so rollout availability remains demo-grade. Before production,
move to an organisation-owned domain, at least two replicas across zones, a managed edge or ingress
with WAF and rate limiting, an explicit certificate incident runbook, and tested DNS/certificate
monitoring. Revisit the sidecar when ingress consolidation, multi-service routing, or private-origin
requirements justify a shared gateway.

---

## 3. Cross-cutting invariants

These rules span several ADRs and should be treated as architectural acceptance criteria:

1. A check that did not execute is never represented as passed.
2. A value without independent document grounding cannot receive full confidence.
3. A graph node that may interrupt performs no pre-interrupt side effects.
4. The workflow ID and graph thread ID are identical for a case.
5. The engine that started a case receives its reviewer decision.
6. Conductor payloads contain identifiers, not customer content.
7. Only the posting step can reach a write-capable external tool.
8. Audit events are appended in the same transaction as the domain change they describe where
   atomicity is required.
9. Raw document text and values never enter logs or traces.
10. A configured cloud provider never silently degrades to a demo implementation.
11. Every externally visible score states whether it is raw or calibrated.
12. Every automated approval names a policy; it never impersonates a person.
13. Upload limits are aligned at proxy and API boundaries.
14. Document rendering uses the stored MIME contract and preserves geometry.
15. Infrastructure actions are scoped so a naming mistake cannot reach another resource group.
16. Public HTTP is redirect-only; authenticated or document-bearing traffic uses a trusted HTTPS
    hostname.

---

## 4. Deployment-specific decision state

The current M6 Azure environment implements the accepted architecture with these deliberate choices:

| Area | Current state |
|---|---|
| Hosting | AKS, one non-HA node, Helm release, Azure DNS hostname, public HTTPS load balancer |
| Process engine | In-process implementation of the canonical process; Conductor worker omitted |
| Authentication | Local audited demo authentication; Entra token validation exists, browser OIDC pending |
| Model | Azure OpenAI `gpt-4.1-mini`, strict structured output |
| Embeddings | `text-embedding-3-small`, 256 dimensions |
| OCR | Azure Document Intelligence `prebuilt-layout` |
| Safety | Local detectors plus Azure Prompt Shields and Content Safety |
| Storage | ADLS Gen2, workload identity, user-delegation SAS |
| Retrieval | pgvector active; Azure AI Search adapter deferred |
| Calibration | Local fitting active; Azure ML workspace present, compute opt-in due quota |
| Observability | Azure Monitor/OpenTelemetry configured; PostgreSQL event audit remains authoritative |
| Secrets | Database password and JWT signing key in Key Vault via CSI |
| Availability | Demo-grade; `Recreate` deployments and no multi-node HA |

---

## 5. Legacy decision traceability

Every numbered decision in `DECISIONS.md` is represented here. Some map to more than one ADR because
the chronological note crossed architectural boundaries.

| Consolidated ADR | Legacy decision numbers |
|---|---|
| ADR-001 | 15, 27, 64 |
| ADR-002 | 2, 3, 57 |
| ADR-003 | 1, 29, 30, 33, 39, 42, 45, 56 |
| ADR-004 | 14, 31, 46–50 |
| ADR-005 | 4, 6, 7, 21, 44 |
| ADR-006 | 5, 9, 20, 72 |
| ADR-007 | 8, 55, 75 |
| ADR-008 | 10, 11, 18, 22–25 |
| ADR-009 | 19, 69 |
| ADR-010 | 28, 34–36, 42, 43, 65, 66 |
| ADR-011 | 34, 67, 68, 75 |
| ADR-012 | 16, 37–39 |
| ADR-013 | 32, 40, 41, 70–72 |
| ADR-014 | 35, 36, 58–62, 74, 79 |
| ADR-015 | 12, 21, 26, 73 |
| ADR-016 | 63 |
| ADR-017 | 64–68, 70–74, 78 |
| ADR-018 | 13, 14, 17, 22, 31 |
| ADR-019 | 71, 76–78 |
| ADR-020 | 29, 30, 47, 49–54, 56 |
| ADR-021 | 19, 20, 24, 25, 35, 58–62 |
| ADR-022 | 34, 45, 55, 75 |

---

## 6. How to change an architectural decision

1. Add a new ADR section; do not silently rewrite the rationale of an accepted decision.
2. Mark the old ADR **Superseded by ADR-NNN** and link both directions.
3. State the observed trigger that caused reconsideration—measurement, incident, compliance change,
   cost, scale, or provider deprecation.
4. Describe data, API, workflow, and infrastructure migration, including rollback.
5. Add or update executable evidence: contract tests, migration tests, negative controls, rendered
   infrastructure validation, and live smoke tests where external behaviour is involved.
6. Update `ARCHITECTURE.md`, `SYSTEM_OVERVIEW.md`, operational runbooks, and the in-product About
   screen if the user-visible system shape changed.

The standard for accepting a new decision is not that the alternative is unfashionable. It is that
the chosen option better preserves Wathiq’s core promise: every automated decision is attached to
evidence, uncertainty is visible, and missing assurance cannot masquerade as assurance.
