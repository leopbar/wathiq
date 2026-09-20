"""The five demo accounts — one per role. Synthetic people, demo-only domain."""

from __future__ import annotations

from dataclasses import dataclass

from app.db.enums import Role


@dataclass(frozen=True)
class DemoAccount:
    role: Role
    email: str
    full_name: str
    full_name_ar: str
    title: str
    description: str


DEMO_ACCOUNTS: tuple[DemoAccount, ...] = (
    DemoAccount(
        role=Role.ops_officer,
        email="layla.almansoori@wathiq.demo",
        full_name="Layla Al Mansoori",
        full_name_ar="ليلى المنصوري",
        title="Operations Officer",
        description="Creates cases, uploads documents and tracks their progress.",
    ),
    DemoAccount(
        role=Role.reviewer,
        email="omar.haddad@wathiq.demo",
        full_name="Omar Haddad",
        full_name_ar="عمر حداد",
        title="Reviewer",
        description="Works the review queue: approve, correct or reject doubtful fields.",
    ),
    DemoAccount(
        role=Role.supervisor,
        email="noura.alzaabi@wathiq.demo",
        full_name="Noura Al Zaabi",
        full_name_ar="نورة الزعابي",
        title="Supervisor",
        description="Handles escalations and SLA breaches, and sees the team dashboards.",
    ),
    DemoAccount(
        role=Role.admin,
        email="rashid.belhoul@wathiq.demo",
        full_name="Rashid Belhoul",
        full_name_ar="راشد بالهول",
        title="Administrator",
        description="Manages document types, prompts, rules, users and integrations.",
    ),
    DemoAccount(
        role=Role.auditor,
        email="fatima.darwish@wathiq.demo",
        full_name="Fatima Darwish",
        full_name_ar="فاطمة درويش",
        title="Auditor",
        description="Read-only access to every case and the full audit trail.",
    ),
)

DEMO_ACCOUNTS_BY_ROLE = {account.role: account for account in DEMO_ACCOUNTS}
