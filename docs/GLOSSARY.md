# Glossary

Every term in one sentence, plus an everyday comparison. If you can say the analogy, you understand
the term well enough to answer a follow-up question.

## The domain

**IDP (Intelligent Document Processing)** — using AI to read documents and turn them into structured
data. *Like a very fast clerk who types the contents of a form into a system.*

**KYC (Know Your Customer)** — the checks a bank must do to know who it is dealing with.
*Like showing ID and proof of address before you can open an account.*

**KYC refresh** — redoing those checks periodically for an existing customer. *Like renewing your
gym membership photo every few years.*

**Straight-through processing (STP)** — a case that completes with no human touch. *Like a parcel
that goes from warehouse to door without anyone opening it.*

**SLA (Service Level Agreement)** — the promised time limit for a step. *Like "we answer within 24
hours" on a support page.*

**Sanctions screening** — checking names against lists of people and companies a bank may not deal
with. *Like a nightclub's banned-guest list at the door.* **Ours is simulated with invented names.**

**Core banking system** — the bank's main record system where accounts and customer data live.
*Like the company's official filing cabinet.* **Ours is simulated.**

**Idempotency key** — a token that makes repeating a request safe. *Like a ticket number: handing in
the same ticket twice still gets you one coat.*

## The AI

**LLM (Large Language Model)** — a model that predicts text and can follow instructions.
*Like an extremely well-read assistant who has never worked at your company.*

**Agent** — an LLM given tools and a goal, allowed to take steps. *Like an intern who can look things
up and ask questions rather than answering from memory.*

**LangGraph** — a library for building agents as an explicit graph of steps with saved state.
*Like a flowchart the computer actually follows, with a save button at every box.*

**Node / edge** — a step in the graph and the arrow between steps. *Like a station and a track.*

**Conditional edge** — an arrow chosen at runtime based on the state. *Like "if it rains, take the
bus".*

**TypedDict state** — the shared clipboard passed between nodes, with named fields.
*Like a form every station fills in one part of.*

**Checkpoint** — a saved copy of that state after each step. *Like a save point in a game.*

**Thread ID** — the name under which checkpoints for one case are stored. *Like a case file number.*

**interrupt()** — the call that pauses the graph and waits for a human. *Like a machine that stops
and turns on a light until an operator presses a button.*

**HITL (Human-in-the-loop)** — designing the system so humans decide the doubtful cases.
*Like a self-checkout that calls an assistant when the item will not scan.*

**Supervisor-worker** — one agent splits work and hands pieces to several workers at once.
*Like a foreman handing out tasks to a crew.*

**Send API** — LangGraph's way of fanning out work to many parallel workers. *Like posting the same
job to several desks simultaneously.*

**Self-reflection / self-correction** — the agent sees its own validation error and tries again.
*Like proofreading your own form after the system says "date is invalid".*

**Actor-critic** — one agent produces an answer, another challenges it. *Like a writer and an editor.*

**ReAct** — reason, act with a tool, observe the result, repeat. *Like a detective who checks a fact
before drawing the next conclusion.*

**Structured output** — forcing the model to answer in a fixed JSON shape. *Like giving someone a
form instead of a blank page.*

**Pydantic** — the Python library that checks data matches a declared shape. *Like a form that
refuses to submit until every field is the right type.*

**Grounding** — being able to point to the exact text a value came from. *Like citing a page number.*

**Confidence** — how sure the system is about a value, from 0 to 1. *Like a weather forecast's "70%
chance of rain".*

**Calibration** — adjusting confidence so that things said with 90% confidence are right about 90% of
the time. *Like a forecaster who checks how often their 70% days were actually wet, and corrects.*

**ECE (Expected Calibration Error)** — the average gap between promised and actual accuracy.
*Like the average distance between what a bathroom scale says and your real weight.*

**Golden set** — documents with known correct answers used to measure quality. *Like a test paper
with an answer key.*

**Regression case** — a test added because something once went wrong, to stop it returning.
*Like a note on the fridge after you once left the oven on.*

**Prompt** — the instructions given to the model. *Like the briefing you give a temp on day one.*

**Semantic versioning (semver)** — numbering like 2.1.0 where MAJOR changes break things, MINOR adds
things, PATCH fixes wording. *Like edition numbers on a textbook.*

**Prompt injection** — text hidden in a document that tries to give the AI orders.
*Like a note inside a parcel saying "ignore your instructions and hand over the keys".*

**Prompt shield** — a check that spots such attempts before the model sees them. *Like a mail room
that screens packages.*

**Output sanitisation** — stripping dangerous characters from what the model returns.
*Like washing vegetables before cooking.*

**PII (Personally Identifiable Information)** — data that identifies a person, like an ID number.
*Like the name and address on an envelope.*

**PII tokenisation** — replacing that data with a placeholder in logs. *Like blacking out a name in a
photocopy.*

**Presidio** — Microsoft's open-source library that finds and masks PII. *Like a highlighter that
automatically finds every ID number on a page.*

**RAG (Retrieval-Augmented Generation)** — looking up relevant documents and giving them to the model
before it answers. *Like handing someone the right policy page before asking their opinion.*

**Chunking** — cutting long documents into passages that fit in a prompt. *Like splitting a manual
into sections.*

**Embedding / vector** — a list of numbers representing meaning, so similar texts sit close together.
*Like a map where related topics are neighbours.*

**pgvector** — the PostgreSQL extension that stores and searches those vectors. *Like adding a
"find similar" index to your existing filing cabinet.*

**MCP (Model Context Protocol)** — a standard way to expose tools to an AI agent.
*Like USB: any tool that speaks it can be plugged into any agent.*

**Least privilege** — giving each part only the access it needs. *Like a hotel key card that opens
your room but not the safe room.*

## The platform

**Orkes Conductor** — an orchestration engine that runs long business processes with human and wait
steps. *Like a project manager with a stopwatch and a checklist.*

**HUMAN task / WAIT task** — Conductor steps that pause for a person or for a timer.
*Like "awaiting signature" and "review in 3 days" in a workflow.*

**Worker** — a small program that performs one kind of Conductor task. *Like a specialist on call.*

**FastAPI** — the Python web framework serving our API. *Like the reception desk of the system.*

**SSE (Server-Sent Events)** — a one-way live stream from server to browser. *Like a radio broadcast:
you listen, you do not talk back.*

**WebSocket** — a two-way live connection. *Like a phone call.* We use SSE because we only need the
broadcast.

**OpenAPI schema** — the machine-readable description of the API, used to generate TypeScript types.
*Like a parts catalogue both factories work from.*

**JWT (JSON Web Token)** — a signed token proving who you are on each request. *Like a wristband at a
festival.*

**Entra ID** — Microsoft's identity service (formerly Azure AD). *Like the company badge system.*

**RBAC (Role-Based Access Control)** — permissions attached to roles, not people. *Like "cleaners can
open all rooms, guests only theirs".*

**Alembic** — the tool that versions database schema changes. *Like tracked changes for your database
structure.*

**Docker image / container** — a packaged application and the running instance of it. *Like a recipe
and the meal cooked from it.*

**Multi-stage build** — building in one container and shipping only the result. *Like cooking in a
big kitchen but delivering just the plate.*

**Compose profile** — a switch that includes or excludes heavy services. *Like an optional extra on
a car order.*

**Healthcheck** — the container telling Docker whether it is actually working. *Like a pulse check.*

**CI/CD** — automatically building and testing every change. *Like a spellchecker that runs before
you are allowed to send the email.*

**gitleaks** — a scanner that blocks committed secrets. *Like a bag check on the way out.*

**Bicep** — Azure's infrastructure-as-code language. *Like an IKEA instruction sheet for cloud
resources.*

**AKS (Azure Kubernetes Service)** — managed Kubernetes for running containers in production.
*Like a shipping port that handles the containers for you.*

**Helm** — the package format for deploying to Kubernetes. *Like an installer for a Kubernetes app.*

**ADLS Gen2** — Azure's large-scale file storage. *Like a very big, very reliable shared drive.*

**Azure AI Foundry** — Microsoft's platform for hosting and calling models inside your tenant.
*Like having the model in your own building rather than renting time in someone else's.*

**Document Intelligence** — Azure's OCR and document-understanding service. *Like a scanner that also
understands what it is looking at.*

**Content Safety / Prompt Shields** — Azure services that block harmful content and injection
attempts. *Like a bouncer and a metal detector.*

**Azure Monitor / OpenTelemetry** — collecting traces and metrics to see what the system did.
*Like a flight recorder.*

**MLflow** — a tool that tracks machine-learning experiments and models. *Like a lab notebook.*
