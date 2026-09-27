"""Where uploaded files live: local disk, or private object storage.

Task 19.3 (M19, architecture report § 3.2). Every stored file - document
versions and work-product versions - is addressed by a key that mirrors the
existing local layout (`projects/<project>/originals/<version><ext>`,
`projects/<project>/work_products/<version><ext>`).

- **local** (default, unchanged behaviour): the key is a path under the
  caller's data directory (`DEAL_LAB_DATA_DIR`, `~/DealLabData`).
- **object** (`DEAL_LAB_STORAGE=object`): files live in a private
  S3-compatible bucket (Cloudflare R2 in the approved stack, D25), which is
  what lets a separate web service and worker service see the same files.
  Readers still get a local `Path`: `path_for` downloads the object into a
  local read cache first, so the analysis modules, downloads and workbook
  parsing need no change. Writes go to the bucket first, then the cache.
  The bucket is never public; every download still goes through the app's
  own authorization check. Encryption at rest is the provider's (R2
  encrypts all objects at rest); transport is HTTPS.

Object-storage failures are raised as OSError, which is what every existing
caller already handles for a failed disk write.

Configuration (object mode): `DEAL_LAB_S3_BUCKET`, `DEAL_LAB_S3_ENDPOINT`
(the R2 account endpoint), `DEAL_LAB_S3_PREFIX` (optional key prefix, e.g.
per environment), `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (R2 API
token credentials), `DEAL_LAB_BLOB_CACHE_DIR`, and
`DEAL_LAB_BLOB_CACHE_MAX_BYTES` (default 2 GB; least-recently-used files are
evicted beyond it).
"""

from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Protocol


class BlobStore(Protocol):
    def path_for(self, key: str, local_root: Path) -> Path: ...
    def put(self, key: str, data: bytes, local_root: Path) -> None: ...
    def delete(self, key: str, local_root: Path) -> None: ...


class LocalBlobStore:
    """Today's behaviour: files on local disk under the data directory."""

    def path_for(self, key: str, local_root: Path) -> Path:
        path = local_root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def put(self, key: str, data: bytes, local_root: Path) -> None:
        self.path_for(key, local_root).write_bytes(data)

    def delete(self, key: str, local_root: Path) -> None:
        (local_root / key).unlink(missing_ok=True)


class ObjectBlobStore:
    """Private S3-compatible bucket plus a bounded local read cache.
    `client` is a boto3 S3 client (or anything with the same
    put_object/get_object/delete_object methods - tests inject a fake)."""

    def __init__(self, client: Any, bucket: str, cache_root: Path, prefix: str = "", cache_max_bytes: int = 2 * 1024**3):
        self._client = client
        self._bucket = bucket
        self._cache_root = cache_root
        self._prefix = prefix.strip("/")
        self._cache_max_bytes = cache_max_bytes
        self._lock = threading.Lock()

    def _object_key(self, key: str) -> str:
        return f"{self._prefix}/{key}" if self._prefix else key

    def _cache_path(self, key: str) -> Path:
        return self._cache_root / key

    def path_for(self, key: str, local_root: Path) -> Path:
        cached = self._cache_path(key)
        if cached.is_file():
            os.utime(cached)  # mark as recently used for eviction
            return cached
        try:
            body = self._client.get_object(Bucket=self._bucket, Key=self._object_key(key))["Body"].read()
        except Exception as exc:
            if _is_missing(exc):
                # Same contract as a local path that doesn't exist: callers
                # check is_file() and report the file as missing.
                return cached
            raise OSError(f"could not read {key!r} from object storage: {exc}") from exc
        self._write_cache(key, body)
        return cached

    def put(self, key: str, data: bytes, local_root: Path) -> None:
        try:
            self._client.put_object(Bucket=self._bucket, Key=self._object_key(key), Body=data)
        except Exception as exc:
            raise OSError(f"could not store {key!r} in object storage: {exc}") from exc
        self._write_cache(key, data)

    def delete(self, key: str, local_root: Path) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=self._object_key(key))
        except Exception as exc:
            if not _is_missing(exc):
                raise OSError(f"could not delete {key!r} from object storage: {exc}") from exc
        self._cache_path(key).unlink(missing_ok=True)

    def _write_cache(self, key: str, data: bytes) -> None:
        cached = self._cache_path(key)
        cached.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename so a concurrent reader never sees a partial file.
        fd, tmp = tempfile.mkstemp(dir=cached.parent, prefix=".partial-")
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, cached)
        self._evict(keep=cached)

    def _evict(self, keep: Path) -> None:
        with self._lock:
            files = [p for p in self._cache_root.rglob("*") if p.is_file() and not p.name.startswith(".partial-")]
            total = sum(p.stat().st_size for p in files)
            for path in sorted(files, key=lambda p: p.stat().st_mtime):
                if total <= self._cache_max_bytes:
                    break
                if path == keep:
                    continue
                total -= path.stat().st_size
                path.unlink(missing_ok=True)


def _is_missing(exc: Exception) -> bool:
    code = getattr(exc, "response", {}).get("Error", {}).get("Code") if hasattr(exc, "response") else None
    return code in ("NoSuchKey", "404", "NotFound") or type(exc).__name__ == "NoSuchKey"


_store: BlobStore | None = None


def get_store() -> BlobStore:
    """The configured backend, created once per process."""
    global _store
    if _store is None:
        _store = _from_environment()
    return _store


def set_store(store: BlobStore | None) -> None:
    """Tests and tools only: override (or reset with None) the backend."""
    global _store
    _store = store


def _from_environment() -> BlobStore:
    mode = os.environ.get("DEAL_LAB_STORAGE", "local").strip().lower()
    if mode == "local":
        return LocalBlobStore()
    if mode != "object":
        raise ValueError(f"DEAL_LAB_STORAGE must be 'local' or 'object', not {mode!r}")
    import boto3  # type: ignore[import-untyped]  # only needed in object mode

    bucket = os.environ["DEAL_LAB_S3_BUCKET"]
    client = boto3.client(
        "s3",
        endpoint_url=os.environ.get("DEAL_LAB_S3_ENDPOINT") or None,
        region_name=os.environ.get("DEAL_LAB_S3_REGION", "auto"),
    )
    cache_root = Path(os.environ.get("DEAL_LAB_BLOB_CACHE_DIR", str(Path(tempfile.gettempdir()) / "deal-lab-blob-cache")))
    return ObjectBlobStore(
        client, bucket, cache_root,
        prefix=os.environ.get("DEAL_LAB_S3_PREFIX", ""),
        cache_max_bytes=int(os.environ.get("DEAL_LAB_BLOB_CACHE_MAX_BYTES", 2 * 1024**3)),
    )
