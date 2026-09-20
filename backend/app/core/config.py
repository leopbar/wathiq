"""Application settings.

Everything that differs between DEMO mode and AZURE mode is a setting, never a code branch
that is hard to find. `WATHIQ_MODE=demo` must work with no external service at all.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Mode = Literal["demo", "azure"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WATHIQ_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- identity -------------------------------------------------------
    app_name: str = "Wathiq"
    app_version: str = "0.1.0"
    build_sha: str = "dev"
    mode: Mode = "demo"
    environment: str = "local"
    log_level: str = "INFO"

    # --- database -------------------------------------------------------
    database_url: str = "postgresql+psycopg://wathiq:wathiq@db:5432/wathiq"
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # --- auth -----------------------------------------------------------
    jwt_secret: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 12 * 60
    # Shared password for the seeded demo accounts. Demo mode only.
    demo_password: str = "Wathiq!Demo2026"

    # --- storage --------------------------------------------------------
    storage_backend: Literal["local", "adls"] = "local"
    storage_dir: str = "/app/storage"
    max_upload_mb: int = 25

    # --- MCP tool servers ------------------------------------------------
    # Each node of the graph is given only the servers it needs (least privilege). An empty
    # URL means "this server is not configured", and the agent says so rather than pretending
    # the check was done.
    mcp_document_store_url: str = ""
    mcp_company_registry_url: str = ""
    mcp_sanctions_url: str = ""
    mcp_core_banking_url: str = ""
    # A tool call that hangs must not hold a case open; the investigator records a timeout and
    # hands the case to a person instead.
    mcp_timeout_seconds: float = 8.0

    # --- SLA / business rules -------------------------------------------
    review_sla_hours: int = 4
    sla_at_risk_fraction: float = 0.25

    # --- web ------------------------------------------------------------
    # NoDecode: the value arrives as a plain comma-separated string, not JSON.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    api_prefix: str = "/api/v1"

    # --- azure (only read when mode == "azure") --------------------------
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_doc_intelligence_endpoint: str = ""
    azure_content_safety_endpoint: str = ""
    azure_search_endpoint: str = ""
    azure_search_index: str = "wathiq-policies"
    azure_storage_account_url: str = ""
    azure_monitor_connection_string: str = ""
    entra_tenant_id: str = ""
    entra_client_id: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_demo(self) -> bool:
        return self.mode == "demo"

    @property
    def sync_database_url(self) -> str:
        """libpq-style URL for Alembic and startup probes."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql://")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
