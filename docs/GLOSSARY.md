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

## Added in M3

**Guardrail** — a check that runs before or after the AI, not inside it. *Like the handrails on a
staircase: they do not help you climb, they stop you falling.*

**Least privilege** — giving each part of a system only the permissions it needs. *Like a hotel key
card that opens your room and the gym, but not the safe in reception.*

**Tool allowlist** — the named list of tools one part of the agent may call. Asking for anything
else fails before a request is made.

**Streamable HTTP** — the transport the MCP servers speak. *Like a phone line the tool server
answers on, rather than a program you have to start yourself.*

**DNS-rebinding protection** — a server checking which hostname a request claims to be for, so a web
page cannot trick a browser into talking to an internal service. Left switched on here, with each
service's own name allowlisted.

**Idle in transaction** — a database connection that opened a transaction and never finished it. It
holds locks and blocks other work; it caused a real outage in this project (DECISIONS #44).

**Superstep** — one round of a LangGraph run. Everything sent out in parallel runs in the same
superstep, and the next node waits for all of it. *Like a relay: the next runner starts when every
runner in this leg is home.*

**Reducer** — the rule for combining two writes to the same piece of state. *Like deciding whether a
shared shopping list gets appended to or replaced.*

**Fan-out** — sending one piece of work to many workers at once. The Send API is how this graph does
it.

**Self-correction loop limit** — the hard cap on how many times a worker may retry. Two here. An
agent with no limit is the standard way to spend an afternoon and a fortune on one document.

**Grounded value** — one that can be found, word for word, in the document it came from. A value
that cannot be is the strongest reason to distrust it.

**Confidence signal** — one fact contributing to a confidence score: page read quality, grounding,
label match, format match, critic agreement. The score is their weighted average.

**Platt scaling** — fitting one S-shaped curve that maps a raw score to a real probability. *Like
learning that a friend who says "definitely" is right about 70% of the time, and adjusting.*

**Brier score** — how far stated probabilities were from what happened, lower being better. *Like
scoring a weather forecaster on every forecast they made.*

**Reliability bin** — a bar of the calibration chart: "when we said about 80%, we were right 73% of
the time".

**Rule pack** — one versioned YAML file holding the rules for one document type. Changing a bank
rule is then a diff in a pull request, not a code deployment.

**Named check** — a rule written as a Python function because it cannot be expressed as a comparison
of two values, referred to from a pack by name.

**Guard (`when:`)** — a condition that decides whether a rule applies at all. "Expires within 30
days" is nonsense about a licence that lapsed three years ago.

**Chunking** — splitting a document into pieces small enough to retrieve. Here one piece is one
policy section, because that is the unit a finding cites.

**Cosine similarity** — how close two vectors point in the same direction, used to find the nearest
policy section. *Like judging whether two people are talking about the same topic by how much
vocabulary they share.*

**Hashed lexical embedding** — a vector built by hashing words into buckets rather than by a model.
Honest about being about *words*, not meaning; it matches "expired licence" to a section on expired
licences, and does not know "lapsed" is the same thing.

**Few-shot example selection** — picking the worked examples most like the document in front of you,
rather than sending the same fixed ones every time.

**Policy citation** — the section of policy behind a finding, quoted from the indexed corpus, so a
reviewer can see the rule as written rather than a paraphrase of it.

---

## Added in M4 (the process layer)

**Process layer** — the part that knows the *order of business steps*: who must act, how long they
have, and what happens when nobody does. Separate from the reasoning layer, which only works out
what the documents say. *Like the difference between the case manager and the analyst.*

**Orkes Conductor** — the workflow engine that runs the process layer. You give it a workflow
definition (a list of steps in JSON) and it decides when each step runs, retries the ones that fail
and waits — for days if needed — on the ones that need a person.

**Workflow definition** — the steps, written down as data rather than code. Wathiq declares it once
in `process/definition.py`; the Conductor JSON, the step list in the UI and the diagram on the About
screen are all generated from it.

**Workflow instance** — one run of that definition, for one case. Its id is also the LangGraph thread
id, which is how one search finds the business history and the reasoning history together.

**Task queue** — a named list of work waiting to be done (`wathiq_post`, `wathiq_agent`…). Conductor
puts work on it; a worker takes work off it. *Like a job pinned to a board that any free member of
the team can take.*

**Worker** — a small program that polls one queue, does the job and reports the result. Wathiq's
workers run the same image as the API, started differently, so the reasoning code is identical.

**Polling** — asking "is there any work for me?" over and over. Long polling asks and then waits a
moment before answering, so an idle system is not asking a thousand times a second.

**HUMAN task** — a step that simply waits until a person completes it. It is a task in the process,
not a flag on a row, which is why the wait survives a restart of everything around it.

**WAIT task** — a step that does nothing except wait for a set time. Wathiq uses one as the SLA
timer.

**FORK / JOIN** — a fork starts two branches at once; a join waits for the ones you name. Wathiq
forks the human review and the SLA timer, and joins on the review alone, so a fired timer can
escalate but can never finish a case on a person's behalf.

**SWITCH** — a step that picks a branch from a value. Here it reads the agent's own answer to "does a
human have to look?".

**SLA (service level agreement)** — the time a review is allowed to take. *Like a promise to answer
a letter within four hours.*

**Escalation** — what happens when the SLA runs out: the review moves to the supervisor queue and the
case priority is raised. The case is not decided or cancelled — it still needs a human answer.

**Idempotent** — safe to do twice. Posting the same KYC refresh again produces the same reference
instead of a second posting. *Like a lift button: pressing it five times does not call five lifts.*

**Idempotency key** — the identifier that lets the receiver recognise a repeat. Wathiq derives it
from the workflow instance, so a retry always carries the same one.

**At-least-once delivery** — the guarantee a task queue actually gives: your job will run, possibly
more than once. It is why every step here can be repeated safely.

**Redelivery** — when a worker stops answering, the orchestrator gives its task to someone else.
This is what crash recovery *is* under Conductor; the fallback engine has to sweep for stuck cases
itself instead.

**Response timeout** — how long a worker has to report back before its task is redelivered. *Like a
library loan: if you do not renew it, somebody else can borrow the book.*

**System of record** — the system that holds the official version of something. For a customer's KYC
file that is core banking. Wathiq's is *simulated*, and labelled as such everywhere it appears.

**Straight-through processing (STP)** — a case that completes with nobody looking at it. Its posting
is approved by a named *policy* rather than a person, and the record says which.

**Append-only** — a table you may add to but never change or remove from. Wathiq's audit trail is
append-only, and since M4 a database trigger enforces it rather than the code merely promising it.

**Trigger** — a rule the database runs by itself whenever a row changes. Wathiq's raises an error on
any attempt to update or delete an audit entry.

## Added in M5

**Golden dataset** — synthetic documents with independently authored expected answers; like an
exam with a sealed answer sheet.

**Regression snapshot** — a saved input and reviewer-corrected answer replayed after code changes;
like keeping a repaired part to check that the same defect never returns.

**Negative control** — a deliberately broken result that must fail a check; like testing a smoke
alarm with test smoke before trusting its silence.

**Prompt sensitivity** — whether rewording an instruction changes its answer. Stability alone does
not mean correctness: a model can consistently give the wrong answer.

**Brier score** — the average squared difference between each probability and its actual outcome.
Lower is better; chart-bin averages cannot substitute for the individual outcomes.

**Training metric** — a measurement on the data used to fit a model; useful for diagnosis, but not
proof that it works on unseen data.

**MLflow experiment** — a logbook of fit attempts, parameters and metrics, allowing comparisons.
