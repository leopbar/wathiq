# Architecture

Five pictures, each with a short explanation. The same diagrams are rendered live inside the app on
the **About the system** screen (they come from `GET /api/v1/system/info`).

---

## 1. System at a glance

```mermaid
flowchart LR
    U["Operations staff"] --> W["Wathiq web console"]
    W --> API["FastAPI backend"]
    API --> C["Orkes Conductor<br/>business process"]
    C --> G["LangGraph agent<br/>AI reasoning"]
    G --> M["Model provider<br/>Foundry or FakeModel"]
    G --> T["MCP tools"]
    T --> REG["Company registry<br/>(simulated)"]
    T --> SAN["Sanctions list<br/>(simulated)"]
    T --> CB["Core banking<br/>(simulated)"]
    API --> DB[("PostgreSQL + pgvector<br/>records, checkpoints, vectors")]
    G --> DB
    R["Reviewer"] --> W
```

People only ever talk to the web console. The backend owns the data and starts the process; the
process layer decides *what happens next*; the reasoning layer decides *what the documents say*.
Tools that reach outside the system are MCP servers, so each one has its own contract and its own
permissions.

---

## 2. The two layers

```mermaid
flowchart TB
    subgraph P["Process layer — Orkes Conductor"]
        A["intake"] --> B["guardrails"] --> D["agent task"]
        D --> E["HUMAN task + WAIT timer (SLA)"]
        E --> F["post to core banking"] --> H["audit"]
    end
    subgraph AI["Reasoning layer — LangGraph (inside the agent task)"]
        S["supervisor: classify"] --> WK["workers: extract (parallel)"]
        WK --> CR["critic"] --> IN["ReAct investigator"]
        IN --> V["validator + calibration"] --> RG["review gate: interrupt()"]
        RG --> FIN["finalize"]
    end
    D -.->|"workflow id == thread id"| S
    RG -.->|"resume from checkpoint"| E
```

**This is the diagram to start from when explaining the system.**

- Conductor is the *manager*: it knows the order of business steps, how long each may take, who must
  act, and what to do when nobody does (escalate).
- LangGraph is the *thinker*: given the documents, it works out what they say and how sure it is.
- They meet at one identifier. `case.thread_id` is both the Conductor workflow ID and the LangGraph
  thread ID, so a single search finds the business history *and* the reasoning history.

---

## 3. The agent graph

```mermaid
stateDiagram-v2
    [*] --> supervisor
    supervisor --> worker_extract: Send() one per document
    worker_extract --> worker_extract: self-correct (max 2)
    worker_extract --> critic
    critic --> investigator: disagreement
    critic --> validator: agreement
    investigator --> validator
    validator --> review_gate
    review_gate --> human_review: interrupt()
    human_review --> validator: corrections applied
    review_gate --> finalize: confident
    finalize --> [*]
```

| Node | Pattern | What it does |
|---|---|---|
| `supervisor` | supervisor-worker | Classifies each document and fans work out with the Send API — documents are processed in parallel, not one after another. |
| `worker_extract` | self-reflection | Extracts fields as structured output. If Pydantic validation fails, it sees the error and tries again, at most twice, then gives up honestly. |
| `critic` | actor-critic | A second opinion that challenges values not supported by the quoted source text. Disagreement is a signal, not a failure. |
| `investigator` | ReAct | Reason → act → observe, using MCP tools, to resolve a mismatch between documents. Has a strict step budget. |
| `validator` | rules | Applies versioned cross-field rules from YAML, then calibrates confidence. |
| `review_gate` | HITL | Calls `interrupt()` at mandatory points (possible sanctions match, expired document, first cases of a new type) and dynamic points (low confidence on a critical field, critic disagreement, suspected injection). |
| `finalize` | — | Writes results and hands control back to Conductor. |

**The rule that matters:** nodes before `interrupt()` must have no side effects, because the node
re-runs when the graph resumes. Anything that writes goes *after* the gate.

---

## 4. What happens to a document

```mermaid
flowchart LR
    UP["Upload"] --> ST["Storage adapter<br/>local folder / ADLS"]
    ST --> OCR["OCR adapter<br/>demo OCR / Document Intelligence"]
    OCR --> SH["Prompt shield + PII tokenisation"]
    SH --> EX["Extraction with structured outputs"]
    EX --> VA["Cross-field rules (YAML, versioned)"]
    VA --> CF["Confidence signals → calibration"]
    CF --> GT{"Confident enough?"}
    GT -->|yes| PO["Post to core banking (idempotent)"]
    GT -->|no| HR["Human review"]
    HR --> PO
    PO --> AU["Append-only audit log"]
```

Confidence is not the model's self-reported number alone. It is built from signals — OCR confidence,
whether the value is grounded in the source text, whether validation rules passed, whether the critic
agreed — and then **calibrated** against the golden set, so a stated 90% matches an observed 90%.

---

## 5. Containers

```mermaid
flowchart TB
    subgraph docker["docker compose"]
        web["web<br/>React + Vite / nginx"]
        api["api<br/>FastAPI + LangGraph"]
        worker["worker<br/>Conductor Python workers"]
        mcp["mcp servers<br/>document-store, registry,<br/>sanctions, core-banking"]
        conductor["conductor<br/>Orkes Conductor OSS"]
        db[("db<br/>PostgreSQL 16 + pgvector")]
    end
    web --> api
    api --> db
    api --> conductor
    conductor --> worker
    worker --> api
    api --> mcp
```

Every service has a multi-stage Dockerfile, runs as a non-root user and has a healthcheck. Heavy
services (`conductor`, `e2e`, `mlflow`) sit behind Compose profiles so the core demo starts on a
laptop. In Azure the same images run on AKS from Azure Container Registry, deployed with Helm.

---

## Data model in one paragraph
A **case** belongs to a customer and has **documents**; each document produces **extracted fields**
(value, confidence, calibrated confidence, page, bounding box, source snippet, critical flag).
Rules produce **findings** (severity, description, policy citation). When a human is needed, a
**review task** is created with a reason code and an SLA. Every action — by a person, an agent or the
system — appends one row to **events**, which is never updated or deleted: the case timeline and the
audit log are two reads of that one table. Configuration lives in **document types** (field schema +
rules) and **prompts** (semantic versions with draft / approved / retired status).
