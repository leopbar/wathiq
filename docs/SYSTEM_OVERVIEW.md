# Wathiq — system overview (one page)

## The problem
A bank must refresh the "know your customer" file of every corporate client. Today an operations
officer opens a folder of documents — a trade licence, Emirates IDs, passports, a memorandum of
association, in Arabic and English — reads them, types the values into the core system, and checks
that everything agrees. It is slow, repetitive, and mistakes are expensive: a wrong expiry date or a
missed sanctions match is a regulatory problem, not a typo.

Pure automation is not the answer either. A model that is confidently wrong on a licence number is
worse than a slow human, and "the AI decided" is not an acceptable audit answer.

## The solution
**Wathiq** (Arabic for *confident*) is an assurance-first document processing platform. AI agents do
the reading, but the system is built around the question **"how sure are we, and can we prove it?"**

1. **Upload** — an officer creates a case and drops in the documents.
2. **Classify** — a supervisor agent decides what each document is.
3. **Extract** — worker agents pull out the fields in parallel, each value carrying the exact snippet
   it came from and a confidence score.
4. **Challenge** — a critic agent argues with the extractor; an investigator agent uses tools to
   resolve disagreements between documents.
5. **Validate** — versioned cross-field rules check the values against each other and against policy.
6. **Decide** — confident cases go straight through. Doubtful ones stop at a review gate and wait for
   a human, for a named reason.
7. **Post and audit** — approved records go to the core banking system once (idempotently), and every
   step is written to an append-only log: who, what, when, which prompt version, which model version.

## Who uses it
| Role | What they do |
|---|---|
| **Operations Officer** | Creates cases, uploads documents, watches progress. |
| **Reviewer** | Works the review queue: approve, correct or reject, with a reason code. |
| **Supervisor** | Handles escalations and SLA breaches, watches team dashboards. |
| **Admin** | Manages document types, prompts, rules, users and integrations. |
| **Auditor** | Read-only access to every case and the full audit trail. |

## The shape of the system
Two layers, joined by one identifier:

- **Process layer — Orkes Conductor.** Runs the business process and can wait hours or days for a
  human, with SLA timers, retries and escalation.
- **Reasoning layer — LangGraph.** Runs the AI's thinking inside a single Conductor task: a graph of
  nodes with typed state, parallel workers, self-correction, and a review gate that pauses the graph
  and resumes it from a saved checkpoint when the reviewer decides.

The Conductor workflow ID **is** the LangGraph thread ID, so one number links the business steps, the
AI reasoning and the audit trail.

## Where the value is
- **Straight-through processing** for the clear cases: minutes instead of a queue.
- **Human attention spent only where it is needed**, with the reason stated ("low confidence on a
  critical field", "possible sanctions match", "values disagree across documents").
- **Every claim is evidenced**: each value links to the region of the document it came from, and each
  finding cites the policy behind it.
- **Calibrated confidence**: the number shown to a reviewer is checked against how often the system
  was actually right, so "92%" means something.
- **New use cases are configuration, not code**: salary certificates were added with a schema, a
  prompt, rules, a golden set and a case-type profile that says where the result is posted (an
  income verification on the employee's file) and that the employer must be a trading company.
- **Failures are shown, not hidden**: a failure-mode gallery stages each way a case can go wrong —
  a poisoned document, an expired licence, a sanctions near-match, a suspended employer — and a
  test proves each one ends the way the gallery says.

## Two modes, one codebase
- **DEMO mode** runs fully offline: a deterministic fake model, demo OCR, local file storage, local
  accounts. The demo cannot break because of a network or a quota.
- **AZURE mode** swaps in Azure AI Foundry, Document Intelligence, Content Safety, ADLS Gen2,
  Azure ML, Azure Monitor and Entra ID by configuration only — the same interfaces, the same
  screens. Each service is switched on by **its own endpoint**, so "real OCR, demo extractor" is a
  legitimate state and the Settings → Azure tab names which one answered. A service that is
  configured and then fails raises rather than falling back, because a case read by something
  nobody chose is worse than a case that stops.
- Demo mode loads **no Azure SDK at all** — a test asserts it, so the offline promise cannot rot.
- It runs on AKS from Bicep and a Helm chart (`infra/`), on one small node: M4's in-process
  workflow engine means no separate orchestrator is needed. Every Azure service authenticates with
  a **workload identity**, so the deployment holds exactly two secrets — the database password and
  the JWT signing key.

Simulated parts (core banking, company registry, sanctions screening) are labelled `Simulated`
everywhere they appear. They are real services with real contracts talking to synthetic data.

## Quality feedback loop (M5)
Quality Lab runs five real diagnostic bands against synthetic answer keys. Reviewer corrections
become saved regression inputs; exported synthetic snapshots can run in CI. Prompt Studio links
checks to exact prompt versions. Calibration reports its sample count and training scope, and can
log fits in optional MLflow. Model wording sensitivity is deliberately unmeasured: the harness is
tested and now accepts a live model, but **no sensitivity score is published** until one has
actually been measured. See [QUALITY.md](QUALITY.md).
