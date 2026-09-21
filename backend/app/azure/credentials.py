"""How Wathiq authenticates to Azure services.

Two ways, and the order matters:

1. **Microsoft Entra credentials** (`DefaultAzureCredential`) when no key is configured. On
   AKS this resolves to a *workload identity*: the pod gets a federated token from the
   cluster's OIDC issuer and exchanges it for an Azure token. No secret is stored anywhere —
   not in the image, not in a Kubernetes Secret, not in the repository. This is what the
   deployed system uses.

2. **An API key** when one is set. Only for a developer running against a real service from
   their own machine, where there is no managed identity to use.

Preferring identity over keys is the whole reason the Key Vault CSI driver in the Helm chart
has so little to carry: the only secrets left are the database password and the JWT signing
key. See DECISIONS #63.

Nothing here imports an Azure SDK at module level. Demo mode must keep working on a machine
where `azure-identity` is not installed at all.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from app.azure import AzureSdkMissing

if TYPE_CHECKING:  # pragma: no cover - import only for type checkers
    from azure.core.credentials import TokenCredential

logger = logging.getLogger(__name__)


def require_sdk(package: str, service: str) -> Any:
    """Import an Azure SDK module, or say plainly which extra is missing."""
    from importlib import import_module

    try:
        return import_module(package)
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise AzureSdkMissing(package, service) from exc


@lru_cache(maxsize=1)
def token_credential() -> TokenCredential:
    """One shared `DefaultAzureCredential` for the whole process.

    Cached because the credential holds a token cache: building a new one per call would ask
    Entra for a fresh token on every request, which is slow and needlessly rate-limited.
    """
    identity = require_sdk("azure.identity", "Microsoft Entra credentials")
    credential = identity.DefaultAzureCredential(
        # The pod's workload identity, or the developer's `az login`. Excluding the
        # interactive and device-code flows keeps a server process from ever trying to open a
        # browser or block on a prompt while a case is waiting.
        exclude_interactive_browser_credential=True,
        exclude_shared_token_cache_credential=True,
    )
    logger.info("azure.credential: using DefaultAzureCredential (no key configured)")
    return credential


def key_credential(key: str) -> Any:
    """An `AzureKeyCredential` for the services that take one."""
    core = require_sdk("azure.core.credentials", "Azure key credential")
    return core.AzureKeyCredential(key)


def credential_for(key: str, service: str) -> Any:
    """Key if one is configured, otherwise the shared Entra credential.

    `service` is only used for the error message when an SDK is missing.
    """
    if key.strip():
        logger.info("azure.credential: %s is using an API key", service)
        return key_credential(key.strip())
    return token_credential()


def describe_credential(key: str) -> str:
    """How a service is authenticating, for the Settings screen. Never the key itself."""
    return "API key" if key.strip() else "Managed identity (Entra)"


__all__ = [
    "credential_for",
    "describe_credential",
    "key_credential",
    "require_sdk",
    "token_credential",
]
