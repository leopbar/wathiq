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
    mlflow_tracking_uri: str = ""

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

    # --- process layer ---------------------------------------------------
    # Which engine runs the business process. `auto` prefers Conductor and falls back to the
    # in-process engine when Conductor is not reachable, saying so in the case's event log.
    # `conductor` refuses to start a case without Conductor, which is what a real deployment
    # wants: silently degrading in production would hide a broken orchestrator.
    process_engine: Literal["auto", "conductor", "inprocess"] = "auto"
    conductor_url: str = ""
    conductor_timeout_seconds: float = 10.0
    # A separate, short timeout for the "is Conductor up?" probe. A hung orchestrator must not
    # hold up starting a case while the engine decides whether to fall back.
    conductor_probe_timeout_seconds: float = 2.0
    # How long a worker waits for a task before polling again.
    conductor_poll_seconds: float = 1.0
    conductor_batch_size: int = 1
    # The in-process engine has no timer service, so one sweep looks for overdue reviews.
    # Conductor has a WAIT task per case and does not need this.
    sla_sweep_seconds: int = 60
    # On startup, look for cases left mid-process by a crash and carry them on.
    process_recover_on_startup: bool = True

    # --- web ------------------------------------------------------------
    # NoDecode: the value arrives as a plain comma-separated string, not JSON.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    api_prefix: str = "/api/v1"

    # --- azure (only read when mode == "azure") --------------------------
    # Every Azure service is switched on by its OWN endpoint, not by the mode alone. This is
    # the same rule the MCP servers follow: an empty endpoint means "this service is not
    # configured", the demo implementation keeps running, and the UI says which one answered.
    # So `WATHIQ_MODE=azure` with only a Document Intelligence endpoint set gives you real OCR
    # and the demo extractor — a real deployment state, not a broken one.
    #
    # Keys are optional everywhere. When a key is empty we use Microsoft Entra credentials
    # (`DefaultAzureCredential`), which is what runs on AKS through workload identity. A key is
    # only there for local development against a real service. See DECISIONS #63.

    # Model provider (Azure AI Foundry / Azure OpenAI)
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = ""
    azure_openai_embedding_deployment: str = ""
    # `text-embedding-3-*` can return a shortened vector, and 256 is what the `policy_chunks`
    # column is declared as. Asking the service for 256 means the Azure embedder drops into
    # the existing schema with no migration and no second column. See DECISIONS #72.
    azure_openai_embedding_dimensions: int = 256
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_api_key: str = ""
    # A model call that hangs must not hold a case open, exactly like an MCP call.
    azure_openai_timeout_seconds: float = 30.0
    azure_openai_max_retries: int = 2
    # Deterministic by default: an extraction that changes between runs cannot be regression-tested.
    azure_openai_temperature: float = 0.0

    # Document Intelligence
    azure_doc_intelligence_endpoint: str = ""
    azure_doc_intelligence_key: str = ""
    # `prebuilt-layout` returns words, lines, tables and polygons without trying to guess a
    # document type; `prebuilt-document` also returns key-value pairs. We ask for layout and do
    # our own field mapping, because the field schema is ours and versioned. (DECISIONS #65)
    azure_doc_intelligence_model: str = "prebuilt-layout"

    # Content Safety (also serves Prompt Shields)
    azure_content_safety_endpoint: str = ""
    azure_content_safety_key: str = ""

    # AI Search
    azure_search_endpoint: str = ""
    azure_search_index: str = "wathiq-policies"
    azure_search_key: str = ""

    # Storage (ADLS Gen2)
    azure_storage_account_url: str = ""
    azure_storage_filesystem: str = "documents"
    azure_storage_key: str = ""
    # How long a viewer's SAS link stays valid. Short: the link is generated per request.
    azure_storage_sas_minutes: int = 15

    # Azure ML (calibration fitting)
    azure_ml_subscription_id: str = ""
    azure_ml_resource_group: str = ""
    azure_ml_workspace: str = ""
    azure_ml_compute: str = "wathiq-cpu"

    # Monitor / Application Insights
    azure_monitor_connection_string: str = ""

    # Entra ID
    entra_tenant_id: str = ""
    entra_client_id: str = ""
    entra_client_secret: str = ""
    # Which auth backend serves /auth. `demo` is local accounts with our own JWT; `entra`
    # validates Microsoft Entra ID tokens against the tenant's JWKS. Separate from `mode` on
    # purpose: signing in with Microsoft while the models stay offline is a sensible state.
    auth_backend: Literal["demo", "entra"] = "demo"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_demo(self) -> bool:
        return self.mode == "demo"

    # --- which Azure services are actually configured --------------------
    # One question per service, asked the same way everywhere. A service counts as configured
    # only when the mode is `azure` AND its own endpoint is set, so a stray endpoint left in a
    # developer's `.env` cannot quietly switch a demo into calling a paid service.

    def _azure_service(self, endpoint: str) -> bool:
        return self.mode == "azure" and bool(endpoint.strip())

    @property
    def foundry_enabled(self) -> bool:
        return self._azure_service(self.azure_openai_endpoint) and bool(
            self.azure_openai_deployment.strip()
        )

    @property
    def doc_intelligence_enabled(self) -> bool:
        return self._azure_service(self.azure_doc_intelligence_endpoint)

    @property
    def content_safety_enabled(self) -> bool:
        return self._azure_service(self.azure_content_safety_endpoint)

    @property
    def azure_search_enabled(self) -> bool:
        return self._azure_service(self.azure_search_endpoint)

    @property
    def adls_enabled(self) -> bool:
        return self._azure_service(self.azure_storage_account_url)

    @property
    def azure_ml_enabled(self) -> bool:
        return self.mode == "azure" and bool(self.azure_ml_workspace.strip())

    @property
    def azure_monitor_enabled(self) -> bool:
        # Tracing is useful in either mode, so this one does NOT require mode == azure.
        return bool(self.azure_monitor_connection_string.strip())

    @property
    def entra_enabled(self) -> bool:
        return self.auth_backend == "entra" and bool(self.entra_tenant_id.strip())

    @property
    def sync_database_url(self) -> str:
        """libpq-style URL for Alembic and startup probes."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql://")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
