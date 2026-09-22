"""The ReAct investigator: reason, act with a tool, observe, repeat.

ReAct means the agent alternates between *thinking* about what it needs to know and *acting* to
find out, using the observation from each action to decide the next one. It is the right shape
here because the questions a KYC case raises can only be answered outside the document: a
company name that differs between two papers is settled by the registry, not by reading the
papers again.

Each step is recorded as a thought, an action and an observation, and that record is what the
reviewer sees. An agent that cannot show its work is not auditable, and in a bank an unauditable
decision is worthless however good it is.

**What chooses the next action.** In demo mode, the controller below: a small, deterministic
policy over the open questions. In Azure mode (M6) a model chooses, with the same tools, the
same limit and the same record. The controller is swapped; nothing else is. The UI says which
one ran, because "an agent decided" and "a rule decided" are not the same claim.

**Limits.** At most `MAX_STEPS` actions. A ReAct loop with no ceiling is the standard way an
agent spends an afternoon and a fortune on one document, and a loop limit is one of the things
the agent test band checks.

**Least privilege.** The investigator is handed the registry, the sanctions list and the
read-only document store. It has no address for core banking, and the broker would refuse the
call even if it did.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.agent.tools import ToolBroker
from app.casetypes import CaseProfile

MAX_STEPS = 6

# Similarity below which two company names are treated as a real difference rather than a
# spelling variant. Matches the rule engine's threshold, deliberately.
NAME_MATCH_THRESHOLD = 0.7


@dataclass(slots=True)
class Step:
    index: int
    thought: str
    action: str
    action_input: dict[str, Any]
    observation: str
    ok: bool
    duration_ms: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
            "ok": self.ok,
            "duration_ms": self.duration_ms,
        }


@dataclass
class Question:
    """Something the case cannot answer from its own documents."""

    kind: str
    prompt: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class Outcome:
    steps: list[Step] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    review_reasons: list[dict[str, str]] = field(default_factory=list)
    controller: str = "deterministic (demo mode); model-driven in Azure mode"

    def as_dict(self) -> dict[str, Any]:
        return {
            "controller": self.controller,
            "step_count": len(self.steps),
            "steps": [step.as_dict() for step in self.steps],
        }


def plan(
    values_by_doc: dict[str, dict[str, str | None]],
    profile: CaseProfile | None = None,
) -> list[Question]:
    """Work out what has to be asked of the outside world, before asking anything.

    Three kinds of question arise:

    * **Screening** — policy KYC-POL-006 §3.1 requires every named party to be screened. This
      is asked on every case, not only doubtful ones.
    * **Reconciliation** — where two documents disagree about a name, the registry decides.
    * **Registry checks** — names the case type's profile says must belong to a registered,
      trading company (the employer on a salary certificate). Declared in configuration, so a
      new use case adds a check without adding code here.
    """
    questions: list[Question] = []

    for check in profile.registry_checks if profile else []:
        name = (values_by_doc.get(check.document) or {}).get(check.field)
        if name:
            questions.append(
                Question(
                    kind="registry_check",
                    prompt=f"Is the {check.role} {name!r} a registered company that is trading?",
                    payload={"name": name, "role": check.role, "policy": check.policy},
                )
            )

    licence_name = (values_by_doc.get("trade_license") or {}).get("company_name_en")
    moa_name = (values_by_doc.get("moa") or {}).get("company_name_en")
    licence_number = (values_by_doc.get("trade_license") or {}).get("license_number")

    names_differ = bool(licence_name and moa_name) and (
        _rough_similarity(licence_name or "", moa_name or "") < NAME_MATCH_THRESHOLD
    )
    if names_differ:
        questions.append(
            Question(
                kind="company_name_mismatch",
                prompt=(
                    f"The trade licence says {licence_name!r} and the memorandum says "
                    f"{moa_name!r}. Which is the registered name?"
                ),
                payload={"name_a": licence_name, "name_b": moa_name},
            )
        )
    elif licence_number:
        questions.append(
            Question(
                kind="licence_status",
                prompt=(
                    f"Is licence {licence_number} on the registry, and is the company still "
                    "trading?"
                ),
                payload={"license_number": licence_number},
            )
        )

    # Every named party gets screened, company and people alike.
    parties: list[tuple[str, str]] = []
    if licence_name:
        parties.append((licence_name, "company"))
    elif moa_name:
        parties.append((moa_name, "company"))
    for doc_type, field_name in (
        ("emirates_id", "full_name_en"),
        ("passport", "full_name"),
        ("salary_certificate", "employee_name"),
    ):
        name = (values_by_doc.get(doc_type) or {}).get(field_name)
        if name and all(name != existing for existing, _ in parties):
            parties.append((name, "person"))

    for name, entity_type in parties:
        questions.append(
            Question(
                kind="sanctions",
                prompt=f"Is {name!r} on the sanctions sample list?",
                payload={"name": name, "entity_type": entity_type},
            )
        )

    return questions


def _rough_similarity(left: str, right: str) -> float:
    """Token overlap, matching the rule engine. Only used to decide whether to ask."""
    from app.agent.rules import _similar  # local import keeps the rule engine self-contained

    return _similar(left, right)


async def investigate(questions: list[Question], broker: ToolBroker) -> Outcome:
    """Run the ReAct loop over the open questions, within the step limit."""
    outcome = Outcome()
    if not questions:
        return outcome

    for question in questions:
        if len(outcome.steps) >= MAX_STEPS:
            outcome.findings.append(
                {
                    "code": "INVESTIGATION_INCOMPLETE",
                    "severity": "warning",
                    "title": "The investigation hit its step limit",
                    "description": (
                        f"{len(questions) - len(outcome.steps)} question(s) were not asked "
                        f"because the loop limit of {MAX_STEPS} steps was reached. A person "
                        "should complete the checks."
                    ),
                    "policy_citation": "AI-POL-001 §3.2",
                    "source": "investigator",
                }
            )
            outcome.review_reasons.append(
                {
                    "code": "INVESTIGATION_INCOMPLETE",
                    "label": "Not every external check could be completed",
                }
            )
            break

        handler = _HANDLERS.get(question.kind)
        if handler is None:
            continue
        await handler(question, broker, outcome)

    return outcome


# --- one handler per kind of question ------------------------------------------


async def _handle_mismatch(question: Question, broker: ToolBroker, outcome: Outcome) -> None:
    started = time.perf_counter()
    call = await broker.call(
        "company_registry",
        "reconcile_names",
        name_a=question.payload["name_a"],
        name_b=question.payload["name_b"],
    )
    result = call.result or {}

    if not call.ok:
        observation = f"the registry could not be reached ({call.error})"
        outcome.findings.append(
            {
                "code": "REGISTRY_UNAVAILABLE",
                "severity": "warning",
                "title": "The company registry could not be reached",
                "description": (
                    "The name difference between the trade licence and the memorandum was not "
                    f"resolved: {call.error}. A person must check it."
                ),
                "policy_citation": "KYC-POL-006 §2.1",
                "source": "investigator",
            }
        )
        outcome.review_reasons.append(
            {"code": "CROSS_DOC_MISMATCH", "label": "Company names differ and could not be checked"}
        )
    elif result.get("same_company"):
        registered = result.get("registered_name")
        observation = f"both spellings resolve to {registered!r} in the registry"
        outcome.findings.append(
            {
                "code": "COMPANY_NAME_RESOLVED",
                "severity": "info",
                "title": f"Name difference resolved: {registered}",
                "description": (
                    f"{question.payload['name_a']!r} and {question.payload['name_b']!r} are "
                    f"the same company in the simulated registry, registered as {registered!r} "
                    f"under licence {result.get('license_number')}."
                ),
                "policy_citation": "KYC-POL-006 §2.1",
                "source": "investigator",
            }
        )
    else:
        observation = "the registry does not treat these as the same company"
        outcome.findings.append(
            {
                "code": "COMPANY_NAME_UNRESOLVED",
                "severity": "critical",
                "title": "The two company names are not the same entity",
                "description": (
                    f"{question.payload['name_a']!r} and {question.payload['name_b']!r} do not "
                    "resolve to one company in the simulated registry. The file cannot be "
                    "refreshed until a person establishes which company it is for."
                ),
                "policy_citation": "KYC-POL-006 §2.1",
                "source": "investigator",
            }
        )
        outcome.review_reasons.append(
            {"code": "CROSS_DOC_MISMATCH", "label": "Company names refer to different entities"}
        )

    outcome.steps.append(
        Step(
            index=len(outcome.steps) + 1,
            thought=question.prompt,
            action="company_registry.reconcile_names",
            action_input=question.payload,
            observation=observation,
            ok=call.ok,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    )


async def _handle_licence_status(question: Question, broker: ToolBroker, outcome: Outcome) -> None:
    started = time.perf_counter()
    call = await broker.call(
        "company_registry", "lookup_by_license", license_number=question.payload["license_number"]
    )
    result = call.result or {}

    if not call.ok:
        observation = f"the registry could not be reached ({call.error})"
    elif not result.get("found"):
        observation = "no company in the registry holds this licence number"
        outcome.findings.append(
            {
                "code": "LICENCE_NOT_IN_REGISTRY",
                # Information, not a warning: the simulated registry only carries fifteen
                # invented companies, so a licence it does not know is expected in a demo. In
                # production this would be a warning, and the wording says so.
                "severity": "info",
                "title": "Licence number is not in the simulated registry",
                "description": (
                    f"Licence {question.payload['license_number']} was not found. In a demo the "
                    "usual cause is a licence number generated for a document that the "
                    "simulated registry does not carry; in production it would mean the "
                    "licence could not be confirmed."
                ),
                "policy_citation": "KYC-POL-004 §1.1",
                "source": "investigator",
            }
        )
    else:
        company = result.get("company") or {}
        status = str(company.get("status", "unknown"))
        observation = f"{company.get('registered_name')} — status {status}"
        if status != "active":
            outcome.findings.append(
                {
                    "code": "REGISTRY_STATUS_NOT_ACTIVE",
                    "severity": "critical",
                    "title": f"The registry reports this company as {status}",
                    "description": (
                        f"{company.get('registered_name')!r} is {status} in the simulated "
                        "registry. A file may not be refreshed for a company that is not "
                        "trading."
                    ),
                    "policy_citation": "KYC-POL-004 §3.2",
                    "source": "investigator",
                }
            )
            outcome.review_reasons.append(
                {"code": "REGISTRY_STATUS_NOT_ACTIVE", "label": f"Company is {status}"}
            )

    outcome.steps.append(
        Step(
            index=len(outcome.steps) + 1,
            thought=question.prompt,
            action="company_registry.lookup_by_license",
            action_input=question.payload,
            observation=observation,
            ok=call.ok,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    )


async def _handle_sanctions(question: Question, broker: ToolBroker, outcome: Outcome) -> None:
    started = time.perf_counter()
    name = question.payload["name"]
    call = await broker.call(
        "sanctions", "screen_name", name=name, entity_type=question.payload["entity_type"]
    )
    result = call.result or {}

    if not call.ok:
        observation = f"screening could not be run ({call.error})"
        outcome.findings.append(
            {
                "code": "SCREENING_UNAVAILABLE",
                "severity": "critical",
                "title": f"{name} could not be screened",
                "description": (
                    "The sanctions screening server could not be reached, so this party was "
                    "not screened. Policy does not allow a refresh to complete without it."
                ),
                "policy_citation": "KYC-POL-006 §3.1",
                "source": "investigator",
            }
        )
        outcome.review_reasons.append(
            {"code": "SANCTIONS_POSSIBLE_MATCH", "label": f"{name} was not screened"}
        )
    elif result.get("band") == "none":
        # Policy KYC-POL-006 §3.1 wants the absence of a match recorded as positively as a
        # match. The step below does exactly that, in the timeline and in the tool-call
        # record. It is deliberately NOT a finding: a findings panel that fills up on every
        # clean case teaches a reviewer to ignore it.
        observation = f"no match for {name!r} on the sample list"
    else:
        matches = result.get("matches") or []
        best = matches[0] if matches else {}
        observation = (
            f"{result.get('band')} match: {best.get('matched_name')!r} "
            f"(score {best.get('score')})"
        )
        outcome.findings.append(
            {
                "code": "SANCTIONS_POSSIBLE_MATCH",
                "severity": "critical",
                "title": f"Possible sanctions match: {name}",
                "description": (
                    f"{name!r} is similar to {best.get('matched_name')!r} on the simulated "
                    f"sample list (score {best.get('score')}). This is never resolved "
                    "automatically. The list is invented and the match says nothing about any "
                    "real person or company."
                ),
                "policy_citation": "KYC-POL-006 §3.1",
                "source": "investigator",
            }
        )
        outcome.review_reasons.append(
            {
                "code": "SANCTIONS_POSSIBLE_MATCH",
                "label": f"{name} resembles an entry on the screening list",
            }
        )

    outcome.steps.append(
        Step(
            index=len(outcome.steps) + 1,
            thought=question.prompt,
            action="sanctions.screen_name",
            action_input=question.payload,
            observation=observation,
            ok=call.ok,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    )


async def _handle_registry_check(
    question: Question, broker: ToolBroker, outcome: Outcome
) -> None:
    started = time.perf_counter()
    name = question.payload["name"]
    role = question.payload["role"]
    policy = question.payload["policy"]
    call = await broker.call("company_registry", "verify_employer", name=name)
    result = call.result or {}

    if not call.ok:
        observation = f"the registry could not be reached ({call.error})"
        outcome.findings.append(
            {
                "code": "REGISTRY_UNAVAILABLE",
                "severity": "warning",
                "title": "The company registry could not be reached",
                "description": (
                    f"The {role} {name!r} was not checked: {call.error}. A person must "
                    "check it."
                ),
                "policy_citation": policy,
                "source": "investigator",
            }
        )
        outcome.review_reasons.append(
            {"code": "EMPLOYER_NOT_VERIFIED", "label": f"The {role} could not be checked"}
        )
    elif not result.get("found"):
        observation = f"no registered company matches {name!r}"
        outcome.findings.append(
            {
                "code": "EMPLOYER_NOT_REGISTERED",
                "severity": "critical",
                "title": f"The {role} is not in the registry",
                "description": (
                    f"{name!r} does not match any company in the simulated registry. Income "
                    f"from an {role} that cannot be found is not evidence of anything; a person "
                    "must establish who the employer is."
                ),
                "policy_citation": policy,
                "source": "investigator",
            }
        )
        outcome.review_reasons.append(
            {"code": "EMPLOYER_NOT_VERIFIED", "label": f"The {role} is not a registered company"}
        )
    else:
        registered = result.get("registered_name")
        status = str(result.get("status", "unknown"))
        observation = f"{registered} — status {status}"
        if not result.get("active"):
            outcome.findings.append(
                {
                    "code": "EMPLOYER_NOT_ACTIVE",
                    "severity": "critical",
                    "title": f"The {role} is {status} in the registry",
                    "description": (
                        f"{registered!r} is {status} in the simulated registry. A salary "
                        "certificate from a company that is not trading needs a person to "
                        "confirm the income is real."
                    ),
                    "policy_citation": policy,
                    "source": "investigator",
                }
            )
            outcome.review_reasons.append(
                {"code": "EMPLOYER_NOT_VERIFIED", "label": f"The {role} is {status}"}
            )

    outcome.steps.append(
        Step(
            index=len(outcome.steps) + 1,
            thought=question.prompt,
            action="company_registry.verify_employer",
            action_input={"name": name},
            observation=observation,
            ok=call.ok,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
    )


_HANDLERS = {
    "registry_check": _handle_registry_check,
    "company_name_mismatch": _handle_mismatch,
    "licence_status": _handle_licence_status,
    "sanctions": _handle_sanctions,
}
