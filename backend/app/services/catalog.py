"""Static catalogues: labels, reason codes, integration honesty, stack rationale, diagrams.

Kept in one place so the UI, the docs and the About screen can never disagree.
"""

from __future__ import annotations

from app.core.config import settings
from app.db.enums import DocTypeKey, IntegrationStatus, QualityBand, ReviewDecision
from app.schemas.review import ReasonCode
from app.schemas.settings import Integration
from app.schemas.system import Diagram, StackItem, StackLayer

DOC_TYPE_LABELS: dict[DocTypeKey, str] = {
    DocTypeKey.trade_license: "Trade licence",
    DocTypeKey.emirates_id: "Emirates ID",
    DocTypeKey.passport: "Passport",
    DocTypeKey.moa: "Memorandum of association",
    DocTypeKey.salary_certificate: "Salary certificate",
    DocTypeKey.unknown: "Unclassified",
}

DOC_TYPE_LABELS_AR: dict[DocTypeKey, str] = {
    DocTypeKey.trade_license: "الرخصة التجارية",
    DocTypeKey.emirates_id: "الهوية الإماراتية",
    DocTypeKey.passport: "جواز السفر",
    DocTypeKey.moa: "عقد التأسيس",
    DocTypeKey.salary_certificate: "شهادة راتب",
    DocTypeKey.unknown: "غير مصنف",
}

BAND_LABELS: dict[QualityBand, tuple[str, str]] = {
    QualityBand.model: (
        "Model",
        "Does the underlying model answer document questions correctly and consistently?",
    ),
    QualityBand.prompt: (
        "Prompt",
        "Correctness against the golden set, plus sensitivity: small rewordings must not change "
        "the answer.",
    ),
    QualityBand.agent: (
        "Agent",
        "Routing, interrupts, tool calls and loop limits behave as designed.",
    ),
    QualityBand.ai_security: (
        "AI security",
        "Prompt shielding, PII tokenisation, output sanitisation and content safety hold.",
    ),
    QualityBand.adversarial: (
        "Adversarial",
        "Hidden instructions, altered values, poor scans and Arabic/English edge cases.",
    ),
}

REVIEW_REASON_LABELS: dict[str, str] = {
    "SANCTIONS_POSSIBLE_MATCH": "Possible sanctions match — mandatory review",
    "DOCUMENT_EXPIRED": "Document expired — mandatory review",
    "NEW_DOCUMENT_TYPE": "First cases of a new document type — mandatory review",
    "LOW_CONFIDENCE_CRITICAL_FIELD": "Low confidence on a critical field",
    "CRITIC_DISAGREEMENT": "The critic disagreed with the extractor",
    "SUSPECTED_INJECTION": "Suspected prompt injection in the document",
    "CROSS_DOC_MISMATCH": "Values disagree across documents",
}

DECISION_REASON_CODES: list[ReasonCode] = [
    ReasonCode(
        code="VALUES_CONFIRMED",
        label="Values confirmed against the document",
        applies_to=[ReviewDecision.approve],
    ),
    ReasonCode(
        code="FINDING_WAIVED",
        label="Finding reviewed and waived",
        applies_to=[ReviewDecision.approve],
    ),
    ReasonCode(
        code="OCR_ERROR",
        label="OCR misread the value",
        applies_to=[ReviewDecision.correct],
    ),
    ReasonCode(
        code="WRONG_FIELD_MAPPED",
        label="Value taken from the wrong place",
        applies_to=[ReviewDecision.correct],
    ),
    ReasonCode(
        code="TRANSLITERATION",
        label="Arabic/English transliteration corrected",
        applies_to=[ReviewDecision.correct],
    ),
    ReasonCode(
        code="ILLEGIBLE_DOCUMENT",
        label="Document is illegible — new copy needed",
        applies_to=[ReviewDecision.reject],
    ),
    ReasonCode(
        code="EXPIRED_DOCUMENT",
        label="Document is expired",
        applies_to=[ReviewDecision.reject],
    ),
    ReasonCode(
        code="WRONG_DOCUMENT",
        label="Wrong document supplied",
        applies_to=[ReviewDecision.reject],
    ),
    ReasonCode(
        code="POSSIBLE_SANCTIONS_HIT",
        label="Possible sanctions match — needs compliance",
        applies_to=[ReviewDecision.escalate],
    ),
    ReasonCode(
        code="SUSPECTED_TAMPERING",
        label="Document may be altered",
        applies_to=[ReviewDecision.escalate, ReviewDecision.reject],
    ),
    ReasonCode(
        code="POLICY_EXCEPTION",
        label="Needs a policy exception",
        applies_to=[ReviewDecision.escalate],
    ),
]


def integrations() -> list[Integration]:
    """Honest status of every external dependency. `simulated` means we built a stand-in."""
    demo = settings.is_demo
    azure_or_demo = IntegrationStatus.demo if demo else IntegrationStatus.connected
    return [
        Integration(
            key="model_provider",
            name="Azure AI Foundry (chat + structured outputs)",
            category="AI",
            status=azure_or_demo,
            detail=(
                "Demo mode uses a deterministic FakeModel so the demo never depends on a network "
                "call. Azure mode calls the configured Foundry deployment."
                if demo
                else f"Connected to deployment '{settings.azure_openai_deployment}'."
            ),
        ),
        Integration(
            key="document_intelligence",
            name="Azure AI Document Intelligence (OCR)",
            category="Documents",
            status=azure_or_demo,
            detail=(
                "Demo mode reads text layers and uses a built-in demo OCR with synthetic "
                "confidence values."
                if demo
                else "Connected to the configured Document Intelligence resource."
            ),
        ),
        Integration(
            key="content_safety",
            name="Azure AI Content Safety + Prompt Shields",
            category="Safety",
            status=azure_or_demo,
            detail=(
                "Demo mode uses a local heuristic shield (pattern and instruction detection)."
                if demo
                else "Connected to Content Safety with Prompt Shields enabled."
            ),
        ),
        Integration(
            key="presidio",
            name="Microsoft Presidio (PII) + UAE recognisers",
            category="Safety",
            status=IntegrationStatus.connected,
            detail="Runs in-process in every mode. Custom recognisers: Emirates ID, UAE IBAN.",
        ),
        Integration(
            key="search",
            name="Azure AI Search (policy RAG)",
            category="Retrieval",
            status=IntegrationStatus.demo if demo else IntegrationStatus.connected,
            detail=(
                "Demo mode indexes the synthetic policy pack in PostgreSQL with pgvector."
                if demo
                else f"Connected to index '{settings.azure_search_index}'."
            ),
        ),
        Integration(
            key="storage",
            name="ADLS Gen2 (document storage)",
            category="Storage",
            status=IntegrationStatus.demo if demo else IntegrationStatus.connected,
            detail=(
                "Demo mode stores uploads in a local folder inside the container volume."
                if demo
                else "Connected to the configured storage account."
            ),
        ),
        Integration(
            key="conductor",
            name="Orkes Conductor (process orchestration)",
            category="Process",
            status=IntegrationStatus.connected,
            detail="Conductor OSS runs in Docker Compose with Python workers.",
        ),
        Integration(
            key="core_banking",
            name="Core banking posting API",
            category="Banking",
            status=IntegrationStatus.simulated,
            detail=(
                "SIMULATED. We built a stand-in MCP server that accepts idempotent posts and "
                "returns reference numbers. No real banking system is contacted."
            ),
        ),
        Integration(
            key="company_registry",
            name="Company registry lookup",
            category="Banking",
            status=IntegrationStatus.simulated,
            detail=(
                "SIMULATED. Synthetic registry of fake companies used to verify trade licence "
                "details."
            ),
        ),
        Integration(
            key="sanctions",
            name="Sanctions screening",
            category="Compliance",
            status=IntegrationStatus.simulated,
            detail=(
                "SIMULATED. A small sample list of invented names — not a real sanctions source."
            ),
        ),
        Integration(
            key="entra",
            name="Microsoft Entra ID (sign-in)",
            category="Identity",
            status=IntegrationStatus.demo if demo else IntegrationStatus.connected,
            detail=(
                "Demo mode uses local accounts with hashed passwords and JWT. The role model is "
                "identical to the Entra app roles used in Azure mode."
                if demo
                else "OIDC sign-in against the configured tenant."
            ),
        ),
        Integration(
            key="monitor",
            name="Azure Monitor (OpenTelemetry)",
            category="Observability",
            status=IntegrationStatus.demo if demo else IntegrationStatus.connected,
            detail=(
                "Demo mode exports traces to the local console and the per-case timeline."
                if demo
                else "Traces and metrics exported to Azure Monitor."
            ),
        ),
    ]


def stack() -> list[StackLayer]:
    """The 'why this, not that' table shown on the About screen."""
    return [
        StackLayer(
            layer="AI reasoning",
            items=[
                StackItem(
                    name="LangGraph",
                    version="0.6",
                    why=(
                        "We need an explicit graph with state we can inspect, pause and resume. "
                        "Human review is an interrupt inside the graph, and checkpoints let a "
                        "case wait hours for a person and continue exactly where it stopped."
                    ),
                    alternative=(
                        "CrewAI (less control over state and interrupts) or plain Python "
                        "(no checkpointing, no resumable human-in-the-loop)."
                    ),
                ),
                StackItem(
                    name="Azure AI Foundry",
                    version="2024-10-21 API",
                    why=(
                        "Bank-grade hosting of models inside the tenant, with structured outputs "
                        "that we validate with Pydantic."
                    ),
                    alternative="Public model APIs — rejected for data residency reasons.",
                ),
                StackItem(
                    name="Model Context Protocol (MCP)",
                    version="Python SDK 1.x",
                    why=(
                        "Tools are separate servers with their own permissions, so each node gets "
                        "only the tools it needs and a new document type reuses them."
                    ),
                    alternative="Hard-coded Python functions — harder to sandbox and reuse.",
                ),
            ],
        ),
        StackLayer(
            layer="Process orchestration",
            items=[
                StackItem(
                    name="Orkes Conductor",
                    version="OSS 3.x",
                    why=(
                        "The business process needs durable HUMAN and WAIT tasks, retries and an "
                        "operations view. Conductor gives that without us writing a scheduler."
                    ),
                    alternative=(
                        "Airflow (batch-oriented, weak human tasks) or Temporal (powerful, but "
                        "the team's target stack is Conductor)."
                    ),
                ),
            ],
        ),
        StackLayer(
            layer="Backend",
            items=[
                StackItem(
                    name="FastAPI + Pydantic v2",
                    version="0.118 / 2.11",
                    why=(
                        "Async for streaming progress, and the same Pydantic models validate API "
                        "input and model output, so schemas cannot drift."
                    ),
                    alternative="Django — heavier, and we do not need its ORM/admin here.",
                ),
                StackItem(
                    name="PostgreSQL + pgvector",
                    version="16",
                    why=(
                        "One database for records, LangGraph checkpoints and embeddings. Fewer "
                        "moving parts to run and to explain."
                    ),
                    alternative=(
                        "A dedicated vector database — extra service, extra cost, no benefit at "
                        "this scale."
                    ),
                ),
                StackItem(
                    name="Server-Sent Events",
                    version="—",
                    why=(
                        "Progress only flows server to client. SSE is one HTTP response, "
                        "reconnects on its own and passes through proxies."
                    ),
                    alternative="WebSockets — two-way, more moving parts than this needs.",
                ),
            ],
        ),
        StackLayer(
            layer="Frontend",
            items=[
                StackItem(
                    name="React + TypeScript + Vite",
                    version="19 / 5.9 / 8",
                    why=(
                        "A single-page operations console behind a login; instant hot reload and "
                        "types generated from the API schema."
                    ),
                    alternative=(
                        "Next.js — server rendering and SEO add nothing behind a bank login."
                    ),
                ),
                StackItem(
                    name="Tailwind CSS + shadcn-style components",
                    version="4",
                    why=(
                        "A small design system we own, with accessible Radix primitives instead "
                        "of a heavy component library."
                    ),
                    alternative="Material UI — harder to make look like a bespoke bank product.",
                ),
                StackItem(
                    name="TanStack Query",
                    version="5",
                    why="Caching, retries and background refresh for a data-heavy console.",
                    alternative="Hand-rolled fetch state — more code, more bugs.",
                ),
            ],
        ),
        StackLayer(
            layer="Platform",
            items=[
                StackItem(
                    name="Docker Compose",
                    version="v2",
                    why="One command starts everything locally; reviewers need no toolchain.",
                    alternative="Local installs — slow to set up and different on every machine.",
                ),
                StackItem(
                    name="AKS + Helm",
                    version="1.30",
                    why=(
                        "The target production platform: several always-on services, private "
                        "networking and scale control."
                    ),
                    alternative=(
                        "Container Apps — simpler, but less control over networking and the "
                        "team already runs AKS."
                    ),
                ),
                StackItem(
                    name="Bicep",
                    version="latest",
                    why="First-party Azure IaC, no extra state file to manage.",
                    alternative="Terraform — great, but adds state management we do not need.",
                ),
            ],
        ),
    ]


_DIAGRAM_SYSTEM = """flowchart LR
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
"""

_DIAGRAM_LAYERS = """flowchart TB
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
"""

_DIAGRAM_GRAPH_PLANNED = """stateDiagram-v2
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
"""

_DIAGRAM_DATAFLOW = """flowchart LR
    UP["Upload"] --> ST["Storage adapter<br/>local folder / ADLS"]
    ST --> OCR["OCR adapter<br/>demo OCR / Document Intelligence"]
    OCR --> SH["Prompt shield + PII tokenisation"]
    SH --> EX["Extraction with structured outputs"]
    EX --> VA["Cross-field rules (YAML, versioned)"]
    VA --> CF["Confidence signals -> calibration"]
    CF --> GT{"Confident enough?"}
    GT -->|yes| PO["Post to core banking (idempotent)"]
    GT -->|no| HR["Human review"]
    HR --> PO
    PO --> AU["Append-only audit log"]
"""

_DIAGRAM_CONTAINERS = """flowchart TB
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
"""


def diagrams(graph_mermaid: str | None = None) -> list[Diagram]:
    return [
        Diagram(
            key="system",
            title="System at a glance",
            description=(
                "Who uses Wathiq and which parts talk to each other. Simulated services are "
                "labelled: no real external system is contacted."
            ),
            mermaid=_DIAGRAM_SYSTEM,
        ),
        Diagram(
            key="layers",
            title="Two layers: process and reasoning",
            description=(
                "Conductor runs the business process and can wait days for a human. LangGraph "
                "runs the AI thinking inside one Conductor task. The Conductor workflow id is "
                "the LangGraph thread id, so one identifier ties the whole audit trail together."
            ),
            mermaid=_DIAGRAM_LAYERS,
        ),
        Diagram(
            key="graph",
            title="The agent graph",
            description=(
                "Supervisor-worker with parallel extraction, self-correction, an actor-critic "
                "challenge, a ReAct investigator for mismatches, and a review gate that pauses "
                "the graph for a human."
            ),
            mermaid=graph_mermaid or _DIAGRAM_GRAPH_PLANNED,
        ),
        Diagram(
            key="dataflow",
            title="What happens to a document",
            description="From upload to posting, with the assurance steps in between.",
            mermaid=_DIAGRAM_DATAFLOW,
        ),
        Diagram(
            key="containers",
            title="Containers",
            description="Every part runs in its own container; one command starts them all.",
            mermaid=_DIAGRAM_CONTAINERS,
        ),
    ]
