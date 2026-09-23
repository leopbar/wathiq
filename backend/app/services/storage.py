"""Document storage behind one interface.

DEMO mode writes to a local folder; AZURE mode will write to ADLS Gen2 (M6). Callers only ever
see `StorageBackend`, so swapping the implementation is a settings change.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import UUID, uuid4

from app.core.config import settings

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str) -> str:
    cleaned = _SAFE_NAME.sub("_", name.strip())[:120]
    return cleaned or "document"


class StorageBackend(ABC):
    @abstractmethod
    def save(self, case_id: UUID, filename: str, data: bytes) -> str:
        """Store the bytes and return an opaque storage path."""

    @abstractmethod
    def read(self, storage_path: str) -> bytes: ...

    @abstractmethod
    def exists(self, storage_path: str) -> bool: ...

    @property
    @abstractmethod
    def label(self) -> str:
        """How this backend is described in the UI, honestly."""

    def signed_url(
        self,
        storage_path: str,
        *,
        content_type: str | None = None,
        filename: str | None = None,
    ) -> str | None:
        """A URL the browser may fetch directly, or `None` if this backend cannot make one.

        Not abstract: a local folder has no such thing, and the default `None` is the honest
        answer for it. The document endpoint falls back to streaming the bytes itself, which
        is what has happened since M1. ADLS Gen2 overrides this with a short-lived SAS. (M6)
        """
        del storage_path, content_type, filename
        return None


class LocalStorage(StorageBackend):
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, storage_path: str) -> Path:
        candidate = (self.root / storage_path).resolve()
        if not candidate.is_relative_to(self.root.resolve()):
            raise ValueError("Storage path escapes the storage root")
        return candidate

    def save(self, case_id: UUID, filename: str, data: bytes) -> str:
        rel = f"{case_id}/{uuid4().hex[:8]}_{safe_filename(filename)}"
        target = self._resolve(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return rel

    def read(self, storage_path: str) -> bytes:
        return self._resolve(storage_path).read_bytes()

    def exists(self, storage_path: str) -> bool:
        try:
            return self._resolve(storage_path).is_file()
        except ValueError:
            return False

    @property
    def label(self) -> str:
        return "Local folder (demo)"


_backend: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """The storage backend this deployment is configured for.

    ADLS only when its account URL is set. The import is inside the branch so demo mode never
    loads an Azure SDK.
    """
    global _backend
    if _backend is None:
        if settings.adls_enabled:
            from app.azure.adls import AdlsStorage

            _backend = AdlsStorage()
        else:
            _backend = LocalStorage(settings.storage_dir)
    return _backend


def reset_storage() -> None:
    """Drop the cached backend so a test can change the settings and pick a different one."""
    global _backend
    _backend = None
