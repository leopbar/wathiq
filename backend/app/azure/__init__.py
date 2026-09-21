"""Azure adapters.

Every module in this package is one implementation of an interface that already existed
before it. Nothing here invents a new shape:

| module                 | interface it implements        | demo implementation it stands beside |
|------------------------|--------------------------------|--------------------------------------|
| `foundry`              | `ExtractorBackend`, `Embedder` | `DemoExtractor`, `HashingEmbedder`   |
| `doc_intelligence`     | `OcrBackend`                   | `DemoOcr`                            |
| `safety`               | prompt shield / content safety | local patterns and term list         |
| `search`               | policy retriever               | pgvector retriever                   |
| `adls`                 | `StorageBackend`               | `LocalStorage`                       |
| `ml`                   | calibration fitter             | local scikit-style fit               |
| `monitor`              | tracing                        | console exporter                     |
| `entra`                | auth backend                   | local JWT                            |

Three rules hold across all of them, and they are the point of the package:

1. **Nothing is imported until it is used.** Demo mode never imports an Azure SDK, so
   `WATHIQ_MODE=demo` keeps working on a machine with no Azure packages installed at all.
2. **A service is on only when its own endpoint is set** (`settings.<service>_enabled`). A
   missing endpoint is a normal, honest state: the demo implementation keeps running and the
   UI reports which one answered. It is never a silent fallback after a failure.
3. **A configured service that fails is an error, not a fallback.** Quietly dropping back to
   the demo reader when Document Intelligence returns 500 would turn an outage into wrong
   data with a confident label on it. See DECISIONS #64.
"""

from __future__ import annotations

__all__ = ["AzureSdkMissing", "describe_azure_services"]


class AzureSdkMissing(RuntimeError):
    """An Azure service is configured but its SDK is not installed.

    Raised at adapter construction, never swallowed. The message names the extra to install,
    because the alternative — falling back to the demo implementation — would mean a
    deployment that believes it is calling Azure while it is not.
    """

    def __init__(self, package: str, service: str) -> None:
        super().__init__(
            f"{service} is configured but the `{package}` package is not installed. "
            f"Install the Azure extra: `uv sync --extra azure`."
        )
        self.package = package
        self.service = service


def describe_azure_services() -> list[dict[str, object]]:
    """Which Azure services are configured right now, for the Settings screen.

    Read from the running settings rather than from a document, so the screen cannot claim a
    service that is not switched on. Endpoints are shown; keys never are.
    """
    from app.core.config import settings

    return [
        {
            "key": "foundry",
            "name": "Azure AI Foundry (models)",
            "enabled": settings.foundry_enabled,
            "endpoint": settings.azure_openai_endpoint,
            "detail": settings.azure_openai_deployment or "no deployment set",
            "replaces": "Demo extractor (deterministic label reader)",
        },
        {
            "key": "doc_intelligence",
            "name": "Document Intelligence (OCR)",
            "enabled": settings.doc_intelligence_enabled,
            "endpoint": settings.azure_doc_intelligence_endpoint,
            "detail": settings.azure_doc_intelligence_model,
            "replaces": "Demo OCR (reads the PDF text layer)",
        },
        {
            "key": "content_safety",
            "name": "Content Safety + Prompt Shields",
            "enabled": settings.content_safety_enabled,
            "endpoint": settings.azure_content_safety_endpoint,
            "detail": "prompt shield and four safety categories",
            "replaces": "Local pattern set and term list",
        },
        {
            "key": "search",
            "name": "Azure AI Search (RAG)",
            "enabled": settings.azure_search_enabled,
            "endpoint": settings.azure_search_endpoint,
            "detail": settings.azure_search_index,
            "replaces": "pgvector retriever",
        },
        {
            "key": "adls",
            "name": "ADLS Gen2 (document storage)",
            "enabled": settings.adls_enabled,
            "endpoint": settings.azure_storage_account_url,
            "detail": settings.azure_storage_filesystem,
            "replaces": "Local folder",
        },
        {
            "key": "azure_ml",
            "name": "Azure ML (calibration fitting)",
            "enabled": settings.azure_ml_enabled,
            "endpoint": settings.azure_ml_workspace,
            "detail": settings.azure_ml_compute,
            "replaces": "Local fit in the API process",
        },
        {
            "key": "monitor",
            "name": "Azure Monitor (tracing)",
            "enabled": settings.azure_monitor_enabled,
            # A connection string carries an instrumentation key, so it is never shown.
            "endpoint": "configured" if settings.azure_monitor_enabled else "",
            "detail": "OpenTelemetry spans for nodes, tools and guardrails",
            "replaces": "Console exporter and the per-case timeline in PostgreSQL",
        },
        {
            "key": "entra",
            "name": "Microsoft Entra ID (sign-in)",
            "enabled": settings.entra_enabled,
            "endpoint": settings.entra_tenant_id,
            "detail": settings.entra_client_id or "no client id set",
            "replaces": "Local accounts with a Wathiq-signed JWT",
        },
    ]
