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
    subgraph P["Process layer — Orkes Conductor (workflow wathiq_kyc_refresh v1)"]
        A["intake"] --> D["agent task"]
        D --> SW{"does a human<br/>have to look?"}
        SW -->|no| F
        SW -->|yes| FK["fork"]
        FK --> HU["HUMAN task"]
        FK --> TI["WAIT — SLA timer"]
        TI --> ES["escalate to a supervisor"]
        HU --> JN["join on the review only"]
        JN --> AP["apply the decision"] --> F
        F["post to core banking<br/>idempotent, approved only"] --> H["seal the audit trail"]
    end
    subgraph AI["Reasoning layer — LangGraph (inside the agent task)"]
        G["guardrails"] --> S["supervisor: classify"] --> WK["workers: extract (parallel)"]
        WK --> CR["critic"] --> IN["ReAct investigator"]
        IN --> V["validator + calibration"] --> RG["review gate: interrupt()"]
        RG --> FIN["finalize"]
    end
    D -.->|"workflow id == thread id"| G
    RG -.->|"interrupt: the graph parks"| HU
    AP -.->|"resume from the checkpoint"| RG
```

**This is the diagram to start from when explaining the system.**

- Conductor is the *manager*: it knows the order of business steps, how long each may take, who must
  act, and what to do when nobody does (escalate).
- LangGraph is the *thinker*: given the documents, it works out what they say and how sure it is.
- They meet at one identifier. `case.thread_id` is both the Conductor workflow ID and the LangGraph
  thread ID, so a single search finds the business history *and* the reasoning history. The intake
  step is where that invariant is applied: it receives Conductor's own workflow id and writes it onto
  the case before any step needs it.

The workflow is declared once, in `backend/app/process/definition.py`, as plain data. The Conductor
JSON, the step list the UI shows and the diagram on the About screen are all generated from it, and a
test asserts that they describe the same steps — so the picture cannot drift from the process.

---

## 2b. The process layer in detail

### Two engines, one set of steps

| | Orkes Conductor | In-process engine |
|---|---|---|
| Who schedules the steps | Conductor, from its own queues | Python, in the API container |
| Retries and redelivery | at-least-once, per the task definition | retried in-process; a crash is picked up at the next startup |
| The SLA timer | a `WAIT` task per case | one sweep over the review queue every minute |
| Needs | ~2 GB of RAM | nothing extra |

Both call the **same functions** in `backend/app/process/tasks.py` and write the same entries to the
same event log. The fallback is not a second implementation of the business process — it is the same
steps with a different scheduler, which is why it can be trusted for a demo.

`WATHIQ_PROCESS_ENGINE` chooses: `conductor` (fail if it is not there), `inprocess`, or `auto` (the
default: Conductor when it answers, the fallback when it does not). **Every case records which engine
ran it**, so a case processed by the fallback can never be mistaken for one that went through
Conductor — and a decision is always handed back to the engine that started that case, never to
whichever one is configured today.

### The human step, and the timer beside it

The review and its SLA timer run as two branches of a fork, and the join waits for **the review
alone**. That one line is the whole design: a timer that fired must never finish a case on a person's
behalf. When it fires, it escalates — the review moves to the supervisor queue and the case priority
is raised — and the case still needs a human answer.

A review somebody has already claimed stays with them. Taking a half-made decision away from a person
produces a worse outcome than a late case.

### Posting: the only step that writes outside Wathiq

Three rules, each enforced rather than promised:

1. **Only after an approval.** Either a named reviewer approved it, or the straight-through policy
   did — and the posting records *which*, so a record never says a human approved something no human
   saw. The simulated core banking server refuses a post that names no approver or an approval kind
   it does not recognise.
2. **Exactly once.** The idempotency key is derived from the workflow instance
   (`<workflow id>:kyc_refresh:1`), so the same case always produces the same key. It is honoured in
   two independent places: a `UNIQUE` column in our database and the system of record's own key
   table. A redelivered task, a worker that died between the call and the commit, and two workers
   racing all end with one posting.
3. **Never silently skipped.** A case that is not posted gets a row saying why — rejected, no
   matching customer, or the server not configured. "Nothing was posted" is an audit answer.

### Crash recovery

Under Conductor there is nothing to write: a task whose worker stops answering is redelivered after
its response timeout. The agent step is safe to redeliver because it *continues* the graph from its
checkpoint rather than starting it again — restarting would feed the initial state in a second time,
and the keys the parallel workers write use appending reducers, so every list would gain a duplicate.

The fallback has to answer for this itself, so at startup it looks for cases left in `processing`,
`approved` or `posting`, records that it found them, and carries them on.

### The audit trail is append-only, and the database enforces it

Until M4 the `events` table was append-only by convention: nothing in the code updated or deleted a
row. Convention is not a control. A trigger now raises on every `UPDATE` and `DELETE` against it, so
the application cannot rewrite history even by accident, and `GET /process/audit-integrity` reports
whether the trigger is in place — along with what the check does *not* prove.

---

## 3. The agent graph

This is the graph that runs. The About screen in the running app draws it from the compiled
graph object, so the picture cannot drift from the code.

```mermaid
stateDiagram-v2
    [*] --> ocr
    ocr --> guardrails: text read
    guardrails --> supervisor: prompt shield, content safety, PII tokenised
    supervisor --> extract_worker: Send() — one worker per document, in parallel
    extract_worker --> extract_worker: self-correct on validation errors (max 2)
    extract_worker --> critic: all workers finished
    supervisor --> critic: nothing to extract
    critic --> investigator: verdict on every field
    investigator --> investigator: ReAct loop with MCP tools (max 6 steps)
    investigator --> validate
    validate --> review_gate: something needs a human
    validate --> finalize: confident enough
    review_gate --> review_gate: interrupt() — waits for a reviewer
    review_gate --> finalize: decision applied
    finalize --> [*]
```

| Node | Pattern | What it does |
|---|---|---|
| `ocr` | — | Reads the text out of each stored document. Demo mode reads the PDF text layer; an image gets an honest "cannot read this" rather than invented text. |
| `guardrails` | AI security | Prompt shield, content safety and PII tokenisation, **before** anything reads the text as meaningful. Produces two copies: the cleaned text the pipeline reads, and a tokenised copy that is the only form allowed into a log. |
| `supervisor` | supervisor-worker | Classifies each document, records the evidence for the choice, and fans work out with the Send API — one worker per document, running in the same superstep. |
| `extract_worker` | self-reflection | Extracts the schema's fields, validates against a Pydantic model built from that schema, and repairs what fails: at most two passes, each recorded with what it tried and why. |
| `critic` | actor-critic | An independent second read of every value: is it on the page, is it the right shape, is it under its own label. Where the document-store MCP server is reachable it asks the file, not the state. |
| `investigator` | ReAct | Thought → action → observation, with MCP tools, for what the documents cannot answer: screening every named party, and settling a name that differs between two documents. At most six steps. |
| `validate` | rules | Versioned YAML rule packs, policy quotes retrieved from the index, then calibration turns each raw score into a probability. |
| `review_gate` | HITL | Calls `interrupt()`. The graph stops here and the state is checkpointed; it can wait hours. |
| `finalize` | — | Closes the case out. Posting to core banking is wired in M4. |

Two branches, and they are the two decisions the system makes: `fan_out` after the supervisor
(how many workers), and `needs_human` after validate (person or not). If nothing needs a person
the case goes straight to `finalize` — that is the "straight-through" number on the dashboard.

**The rule that matters:** a node that can interrupt must have no side effects above the
`interrupt()` call, because the node re-runs from its first line when the graph resumes. The
review-task rows are therefore created by the runner, outside the graph, which runs once per
pause. See DECISIONS #29.

### Why the state uses the reducers it does

Parallel workers write to the state in the same superstep. A key whose reducer keeps the last
write would lose all but one of them, so `findings`, `tool_calls`, `guardrails`, `critic_notes`
and `investigation` all append. `fields` uses a merge-by-(document, name) reducer instead: the
workers write disjoint fields, and the critic later writes revised copies of fields it has
challenged, which must **replace** rather than duplicate.

### When a human is asked

| Point | Kind | Raised by |
|---|---|---|
| Possible sanctions match | mandatory | investigator |
| Required document expired | mandatory | rule pack (critical severity) |
| First cases of a new document type | mandatory | supervisor (unclassified document) |
| Content safety flagged the upload | mandatory | guardrails |
| Registry says the company is not trading | mandatory | investigator |
| Low calibrated confidence on a critical field | dynamic | validate |
| The critic disagreed about a critical field | dynamic | critic |
| Suspected instructions hidden in a document | dynamic | guardrails |
| Values disagree across documents | dynamic | rule pack / investigator |
| Not every external check could be completed | dynamic | investigator |

---

### Tools and least privilege

Four MCP servers, each its own process and its own container:

| Server | Can write? | Tools | Which node may call it |
|---|---|---|---|
| document-store | no (volume mounted read-only) | `read_document`, `find_in_document`, `list_case_documents` | critic, investigator |
| company-registry (simulated) | no | `lookup_by_license`, `search_by_name`, `reconcile_names` | investigator |
| sanctions (simulated sample list) | no | `screen_name`, `describe_list` | investigator |
| core-banking (simulated) | **yes** | `get_customer`, `post_kyc_refresh`, `get_posting` | post (M4) only |

Two independent locks on the only server that can write: the investigator is never given its
address, and the broker in the API refuses the call by name even if it were. The Settings screen
shows this table from the running code.

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

Confidence is not the model's self-reported number alone. Each field's score is a weighted average
of five signals, and every one of them is a fact about how the value was obtained:

| Signal | Question it answers | Weight |
|---|---|---|
| `ocr` | How well was the page read at all? | 0.20 |
| `grounded` | Does this exact value appear in the document text? | 0.25 |
| `label` | Was it found next to its own label, or guessed from nearby text? | 0.15 |
| `shape` | Does it look like what the schema asks for (date, number, list)? | 0.20 |
| `critic` | Did the independent second read agree? | 0.20 |

That weighted average is the **raw** score. It is then mapped through a **calibration** curve —
Platt scaling, two parameters — fitted on what reviewers actually decided: a field they accepted
was read correctly, a field they corrected was not. The result is the **calibrated** score, and it
is the one the thresholds read, because it is the one that means "right about this often".

Until enough reviewers have decided enough cases, the curve is not fitted and the product shows
raw scores **labelled as raw**. An uncalibrated number dressed up as a calibrated one is the kind
of dishonesty this whole system exists to avoid.

---

## 4b. Policy retrieval (RAG)

Findings cite policy, and the citation is retrieved rather than written into the rule:

1. Six synthetic policy documents live in `backend/app/rag/corpus/` as Markdown.
2. They are chunked **one section per chunk**, because a section is the unit a rule cites.
   Splitting by character count would produce citations like "characters 1200-1800", which is
   useless to a reviewer, and would cut rules in half.
3. Each chunk is embedded and stored in `policy_chunks` with pgvector — same database, no
   separate vector service to run or explain.
4. A rule that names its section (`KYC-POL-004 §3.2`) gets that exact section: a look-up, not a
   search, so it cannot retrieve the wrong one. A finding with no citation gets the nearest
   section by cosine distance, and anything with no good match gets **no quote at all** rather
   than a misleading one.

The demo embedder is a hashed lexical embedding: every word and word pair is hashed into one of
256 buckets and the vector is normalised. It is honest about being lexical — it matches "expired
trade licence" to a section about expired licences because the words overlap, and it does not
know that "lapsed" means the same thing. Azure mode swaps in an Azure OpenAI embedding
deployment behind the same interface; the chunking, the index and the citation stay identical.

The same machinery picks **few-shot examples** for the extraction prompt: worked examples live
in `backend/app/rag/examples/`, and the ones nearest the document being read are selected and
recorded on the case. In demo mode the extractor makes no model call, so the selection is shown
as "selected for the prompt" and nothing more is claimed for it.

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
    api -->|"start workflow,<br/>complete the human task"| conductor
    worker -->|"poll for tasks"| conductor
    worker --> db
    worker --> mcp
    api --> mcp
```

The `worker` service runs **the same image as the API**, started as a task worker instead of a web
server. That is deliberate: the worker runs the LangGraph graph, so two images would mean two
versions of the reasoning — the last thing an auditable system should have.

Every service has a multi-stage Dockerfile, runs as a non-root user and has a healthcheck. Heavy
services (`conductor`, `worker`, `e2e`, `mlflow`) sit behind Compose profiles so the core demo starts
on a laptop: with the `process` profile off, the API's in-process engine runs the same workflow. In Azure the same images run on AKS from Azure Container Registry, deployed with Helm.

---

## Data model in one paragraph
A **case** belongs to a customer and has **documents**; each document produces **extracted fields**
(value, confidence, calibrated confidence, page, bounding box, source snippet, critical flag).
Rules produce **findings** (severity, description, policy citation). When a human is needed, a
**review task** is created with a reason code, an SLA and, if the timer found it late, an
escalation timestamp. Handing the case to the system of record writes a **posting** — one row per
attempt, whatever the outcome, with a unique idempotency key. Every action — by a person, an agent or the
system — appends one row to **events**, which is never updated or deleted: the case timeline and the
audit log are two reads of that one table. Configuration lives in **document types** (field schema +
rules) and **prompts** (semantic versions with draft / approved / retired status).
