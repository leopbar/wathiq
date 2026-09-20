from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from app.db.enums import DocTypeKey, IntegrationStatus


class DocumentTypeOut(BaseModel):
    id: UUID
    key: DocTypeKey
    name_en: str
    name_ar: str
    description: str
    version: str
    prompt_key: str
    rules_version: str
    fields: list[dict[str, Any]]
    rules_count: int
    is_active: bool


class Integration(BaseModel):
    key: str
    name: str
    category: str
    status: IntegrationStatus
    detail: str
    docs_url: str | None = None


class ModeInfo(BaseModel):
    mode: Literal["demo", "azure"]
    version: str
    build_sha: str
    features: dict[str, bool]


class RuleOut(BaseModel):
    """One rule in a pack, in the form the Settings screen shows it."""

    id: str
    severity: str
    message: str
    policy: str | None = None
    explain: str = ""
    # Exactly one of these is set: an expression, or the name of a check registered in code.
    expr: str | None = None
    check: str | None = None


class RulePackOut(BaseModel):
    id: str
    version: str
    title: str
    description: str
    applies_to: list[str]
    source: str
    rules: list[RuleOut]


class ToolServerOut(BaseModel):
    """One MCP server and who is allowed to call it — the least-privilege matrix."""

    key: str
    name: str
    url_configured: bool
    can_write: bool
    tools: list[str]
    used_by_nodes: list[str]


class GuardrailOut(BaseModel):
    key: str
    name: str
    purpose: str
    implementation: str
    azure: str


class SignalWeightOut(BaseModel):
    key: str
    label: str
    weight: float


class AssuranceInfo(BaseModel):
    """Everything the Settings screen says about how the agent assures its own answers."""

    guardrails: list[GuardrailOut]
    confidence_signals: list[SignalWeightOut]
    tool_servers: list[ToolServerOut]
    rule_packs: list[RulePackOut]
    registered_checks: list[str]
    graph_steps: list[dict[str, str]]
    policy_documents: list[dict[str, str | int]]
    embedder: str
    calibration: dict[str, Any]
