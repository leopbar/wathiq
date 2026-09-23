"""Settings screen: document types, users, integration honesty, and the current mode."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app import guardrails
from app.agent import confidence, graph, rulepacks
from app.agent import rules as rule_engine
from app.agent.tools import describe_servers
from app.azure import describe_azure_services
from app.azure.credentials import describe_credential
from app.core.config import settings as app_settings
from app.core.deps import ADMIN_ONLY, CurrentUser, DbSession, require_roles
from app.db import models
from app.rag.chunking import load_corpus
from app.rag.embedder import get_embedder
from app.schemas.auth import UserOut
from app.schemas.settings import (
    AssuranceInfo,
    AzureInfo,
    AzureServiceOut,
    DocumentTypeOut,
    GuardrailOut,
    Integration,
    ModeInfo,
    RuleOut,
    RulePackOut,
    SignalWeightOut,
    ToolServerOut,
)
from app.services import assurance
from app.services.catalog import integrations

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/mode", response_model=ModeInfo)
async def mode() -> ModeInfo:
    """Public: the login screen needs to know whether to offer demo sign-in."""
    return ModeInfo(
        mode=app_settings.mode,
        version=app_settings.app_version,
        build_sha=app_settings.build_sha,
        features={
            "demo_login": app_settings.auth_backend == "demo",
            # True only when at least one Azure service is genuinely configured. `not is_demo`
            # would have claimed the feature for a deployment that has the mode set and no
            # endpoints, which is a real and perfectly normal state.
            "azure_services": any(
                bool(service["enabled"]) for service in describe_azure_services()
            ),
            "entra_sign_in": app_settings.entra_enabled,
            "arabic_ui": True,
            "conductor_process_layer": True,
        },
    )


@router.get("/azure", response_model=AzureInfo)
async def azure_info(_: CurrentUser) -> AzureInfo:
    """Which Azure services this deployment is actually using, service by service.

    Generated from the running configuration, exactly like the Assurance and Process tabs.
    A service that is not configured is reported as off, together with what is running in its
    place — so the screen cannot imply a capability the deployment does not have.
    """
    from app.azure import monitor

    return AzureInfo(
        mode=app_settings.mode,
        auth_backend=app_settings.auth_backend,
        services=[AzureServiceOut(**service) for service in describe_azure_services()],
        credential=describe_credential(app_settings.azure_openai_api_key),
        tracing_enabled=monitor.enabled(),
    )


@router.get("/document-types", response_model=list[DocumentTypeOut])
async def document_types(db: DbSession, _: CurrentUser) -> list[DocumentTypeOut]:
    rows = (
        await db.execute(select(models.DocumentType).order_by(models.DocumentType.name_en))
    ).scalars().all()
    return [
        DocumentTypeOut(
            id=row.id,
            key=row.key,
            name_en=row.name_en,
            name_ar=row.name_ar,
            description=row.description,
            version=row.version,
            prompt_key=row.prompt_key,
            rules_version=row.rules_version,
            fields=row.field_schema,
            rules_count=len(row.rules),
            is_active=row.is_active,
        )
        for row in rows
    ]


@router.get("/integrations", response_model=list[Integration])
async def integration_status(_: CurrentUser) -> list[Integration]:
    return integrations()


@router.get("/users", response_model=list[UserOut])
async def list_users(
    db: DbSession, _: Annotated[models.User, Depends(require_roles(*ADMIN_ONLY))]
) -> list[UserOut]:
    rows = (await db.execute(select(models.User).order_by(models.User.full_name))).scalars().all()
    return [UserOut.model_validate(row) for row in rows]


@router.get("/assurance", response_model=AssuranceInfo)
async def assurance_info(db: DbSession, _: CurrentUser) -> AssuranceInfo:
    """How the agent assures its own answers, in one place.

    The Settings screen reads this so that what it claims about guardrails, tools, rules and
    calibration comes from the code that runs, not from a hand-written page that can drift.
    """
    packs = [
        RulePackOut(
            id=pack.id,
            version=pack.version,
            title=pack.title,
            description=pack.description,
            applies_to=pack.applies_to,
            source=pack.source,
            rules=[
                RuleOut(
                    id=str(rule.get("id", "")),
                    severity=str(rule.get("severity", "warning")),
                    message=str(rule.get("message", "")),
                    policy=rule.get("policy"),
                    explain=str(rule.get("explain", "")),
                    expr=rule.get("expr"),
                    check=rule.get("check"),
                )
                for rule in pack.rules
            ],
        )
        for pack in rulepacks.all_packs()
    ]

    # The chunk's title already starts with the policy id, so it is not repeated here.
    documents: dict[str, int] = {}
    for chunk in load_corpus():
        documents[chunk.policy_title] = documents.get(chunk.policy_title, 0) + 1

    return AssuranceInfo(
        guardrails=[GuardrailOut(**item) for item in guardrails.describe()],
        confidence_signals=[SignalWeightOut(**item) for item in confidence.describe()],
        tool_servers=[ToolServerOut(**row) for row in describe_servers()],
        rule_packs=packs,
        registered_checks=rule_engine.registered_checks(),
        graph_steps=[{"key": key, "label": label} for key, label in graph.STEP_LABELS],
        policy_documents=[
            {"name": name, "sections": count} for name, count in sorted(documents.items())
        ],
        embedder=get_embedder().label,
        calibration=(await assurance.load_active(db)).as_dict(),
    )
