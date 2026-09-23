"""Azure Data Lake Storage Gen2: where uploaded documents live in Azure mode.

A `StorageBackend` like `LocalStorage`, with the same three operations and the same opaque
storage path, so nothing that stores or reads a document knows which one it is talking to.

**Why ADLS Gen2 rather than plain blob storage.** It is blob storage with a hierarchical
namespace turned on, which means `case-id/document.pdf` is a real directory and a real file
rather than a blob whose name happens to contain a slash. That buys two things a bank cares
about: a per-directory ACL, so access can be granted per case rather than per container, and
an atomic rename, which matters the day documents are moved to an archive tier.

**SAS links, and why they are short.** The viewer is an `<iframe>`, and an iframe cannot send
an `Authorization` header — which is why M1 had to add a `?token=` query parameter to the local
file endpoint. In Azure mode the browser can fetch the file from storage directly instead,
using a short-lived SAS URL generated per request. The default is 15 minutes: long enough to
open a document, short enough that a URL copied out of a browser history is useless by the time
anyone finds it. See DECISIONS #69.

The SAS is signed with a **user delegation key** whenever we authenticate with a managed
identity. That key is itself issued by Entra and expires, so the signature is traceable to the
identity that asked for it — unlike an account-key signature, which is anonymous and valid
until the account key is rotated.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app.azure.credentials import describe_credential, require_sdk, token_credential
from app.core.config import settings
from app.services.storage import StorageBackend, safe_filename

logger = logging.getLogger(__name__)

# A user delegation key is valid for up to 7 days; we re-request it well before that and cache
# it, because asking for one on every page view would add a round trip to every document open.
_DELEGATION_KEY_HOURS = 6
# Clock skew allowance, so a link is not rejected as "not yet valid" by a server a few seconds
# behind us.
_CLOCK_SKEW = timedelta(minutes=5)


class AdlsStorage(StorageBackend):
    """`StorageBackend` implemented by ADLS Gen2."""

    def __init__(self) -> None:
        account_url = settings.azure_storage_account_url.strip()
        if not account_url:
            raise ValueError("Azure storage account URL is not configured")
        self._account_url = account_url.rstrip("/")
        self._filesystem = settings.azure_storage_filesystem.strip() or "documents"
        self._key = settings.azure_storage_key
        self._service: Any | None = None
        self._delegation_key: Any | None = None
        self._delegation_expiry: datetime | None = None

    # -- clients ---------------------------------------------------------

    def _service_client(self) -> Any:
        if self._service is None:
            module = require_sdk("azure.storage.filedatalake", "ADLS Gen2")
            credential: Any = self._key.strip() or token_credential()
            self._service = module.DataLakeServiceClient(
                account_url=self._account_url, credential=credential
            )
        return self._service

    def _filesystem_client(self) -> Any:
        """The container, created on first use if it is not there.

        Creating it here rather than in Bicep keeps a fresh deployment working when someone
        changes the filesystem name in configuration and forgets to change the template.
        """
        client = self._service_client().get_file_system_client(self._filesystem)
        try:
            if not client.exists():
                client.create_file_system()
                logger.info("adls: created filesystem %s", self._filesystem)
        except Exception as exc:  # pragma: no cover - depends on the account's RBAC
            # A role that can read and write files but not create a container is a perfectly
            # normal least-privilege setup, so this must not be fatal.
            logger.debug("adls: could not ensure filesystem exists: %s", exc)
        return client

    # -- StorageBackend --------------------------------------------------

    def save(self, case_id: UUID, filename: str, data: bytes) -> str:
        """Same path shape as `LocalStorage`, so a path is portable between the two."""
        rel = f"{case_id}/{uuid4().hex[:8]}_{safe_filename(filename)}"
        file_client = self._filesystem_client().get_file_client(rel)
        file_client.upload_data(data, overwrite=True)
        logger.info("adls: stored %s (%d bytes)", rel, len(data))
        return rel

    def read(self, storage_path: str) -> bytes:
        file_client = self._filesystem_client().get_file_client(storage_path)
        return file_client.download_file().readall()

    def exists(self, storage_path: str) -> bool:
        try:
            return bool(self._filesystem_client().get_file_client(storage_path).exists())
        except Exception as exc:  # pragma: no cover - network failure shape
            logger.warning("adls: exists(%s) failed: %s", storage_path, exc)
            return False

    @property
    def label(self) -> str:
        auth = describe_credential(self._key)
        return f"Azure ADLS Gen2 ({self._filesystem}, {auth})"

    # -- SAS -------------------------------------------------------------

    def _user_delegation_key(self) -> Any:
        """A cached delegation key, re-requested before it expires."""
        now = datetime.now(UTC)
        if (
            self._delegation_key is not None
            and self._delegation_expiry is not None
            and now < self._delegation_expiry - timedelta(minutes=10)
        ):
            return self._delegation_key

        expiry = now + timedelta(hours=_DELEGATION_KEY_HOURS)
        self._delegation_key = self._service_client().get_user_delegation_key(
            key_start_time=now - _CLOCK_SKEW, key_expiry_time=expiry
        )
        self._delegation_expiry = expiry
        return self._delegation_key

    def signed_url(
        self,
        storage_path: str,
        *,
        content_type: str | None = None,
        filename: str | None = None,
    ) -> str | None:
        """A short-lived, read-only URL the browser can open directly.

        `None` when a SAS cannot be produced, and the caller then falls back to streaming the
        file through the API — which always works, just less efficiently.
        """
        try:
            module = require_sdk("azure.storage.filedatalake", "ADLS Gen2")
            now = datetime.now(UTC)
            expiry = now + timedelta(minutes=settings.azure_storage_sas_minutes)
            account_name = self._account_url.split("//", 1)[-1].split(".", 1)[0]

            # `generate_file_sas` wants the path split: the directory and the file name are
            # separate arguments, and `directory_name` is required even at the root. Passing
            # the whole `case-id/file.pdf` as `file_name` raises a TypeError about a missing
            # argument, which says nothing about the real cause. Found by the live smoke test —
            # no amount of offline testing would have.
            directory, _, file_name = storage_path.rpartition("/")

            common: dict[str, Any] = {
                "account_name": account_name,
                "file_system_name": self._filesystem,
                "directory_name": directory,
                "file_name": file_name,
                # Read only. A viewer link must never be able to replace the document it is
                # showing, which is also why there is no write SAS anywhere in this file.
                "permission": module.FileSasPermissions(read=True),
                "expiry": expiry,
                "start": now - _CLOCK_SKEW,
            }
            # Files are stored as opaque bytes, so their persisted ADLS content type may be
            # application/octet-stream. Sign response-header overrides into the SAS so an
            # existing JPEG/PNG renders inline instead of becoming a blank iframe/download.
            if content_type:
                common["content_type"] = content_type
            if filename:
                common["content_disposition"] = (
                    f'inline; filename="{safe_filename(filename)}"'
                )
            if self._key.strip():
                token = module.generate_file_sas(credential=self._key.strip(), **common)
            else:
                # The Data Lake SDK accepts either an account key or a UserDelegationKey in
                # its required `credential` parameter. Blob Storage exposes a similarly named
                # `user_delegation_key` keyword, but Data Lake does not — a distinction only a
                # real call exposed.
                token = module.generate_file_sas(
                    credential=self._user_delegation_key(), **common
                )
            return f"{self._account_url}/{self._filesystem}/{storage_path}?{token}"
        except Exception as exc:  # pragma: no cover - depends on the account's RBAC
            logger.warning("adls: could not sign a URL for %s: %s", storage_path, exc)
            return None


__all__ = ["AdlsStorage"]
