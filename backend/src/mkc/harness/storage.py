"""Blob stores beyond the Postgres table (MKC-21.4, decisions 56 and 63).

- `StorageBlobStore`: Supabase Storage over its S3 protocol (path-style URLs, SigV4 signed
  by hand: only PUT and GET of one object are needed, so no AWS SDK). Object key
  `sha256/<hex>`, the same content address as the ref `blob:sha256:<hex>`.
- `LayeredBlobStore`: writes go to the primary store; a ref the primary lacks is read from
  the fallback. Turn results use Storage first and the `blob` table second, so refs written
  before MKC-21 stay readable.
- `FileBlobStore`: a folder, for a local run without Storage settings.
"""

import hashlib
import hmac
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlsplit

import httpx
from pydantic import SecretStr

from mkc.config import Settings
from mkc.harness.blobs import PREFIX, BlobStore

TIMEOUT_SECONDS = 60.0
_HEX = re.compile(r"[0-9a-f]{64}")


class StorageNotConfigured(ValueError):
    """Some, but not all, of the Storage settings are set."""


def digest_of(ref: str) -> str:
    """The hex digest of a well-formed ref, or `KeyError` (nothing is requested)."""
    digest = ref.removeprefix(PREFIX) if ref.startswith(PREFIX) else ""
    if not _HEX.fullmatch(digest):
        raise KeyError(ref)
    return digest


def _hmac(key: bytes, text: str) -> bytes:
    return hmac.new(key, text.encode(), hashlib.sha256).digest()


def sigv4_headers(
    method: str,
    url: str,
    payload_sha256: str,
    *,
    key_id: str,
    secret: str,
    region: str,
    now: datetime,
) -> dict[str, str]:
    """AWS Signature Version 4 headers for an S3 request without a query string, signing
    `host`, `x-amz-content-sha256` and `x-amz-date`."""
    parts = urlsplit(url)
    stamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    day = stamp[:8]
    headers = {"host": parts.netloc, "x-amz-content-sha256": payload_sha256, "x-amz-date": stamp}
    signed = ";".join(sorted(headers))
    canonical = "\n".join(
        [
            method,
            quote(parts.path or "/", safe="/-_.~"),
            "",
            *(f"{name}:{headers[name]}" for name in sorted(headers)),
            "",
            signed,
            payload_sha256,
        ]
    )
    scope = f"{day}/{region}/s3/aws4_request"
    to_sign = "\n".join(
        ["AWS4-HMAC-SHA256", stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()]
    )
    key = _hmac(_hmac(_hmac(_hmac(f"AWS4{secret}".encode(), day), region), "s3"), "aws4_request")
    signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    return {
        "x-amz-content-sha256": payload_sha256,
        "x-amz-date": stamp,
        "authorization": (
            f"AWS4-HMAC-SHA256 Credential={key_id}/{scope}, "
            f"SignedHeaders={signed}, Signature={signature}"
        ),
    }


class StorageBlobStore:
    """Blobs as objects `sha256/<hex>` in one Supabase Storage bucket."""

    def __init__(
        self,
        *,
        endpoint: str,
        region: str,
        bucket: str,
        key_id: str,
        secret: SecretStr,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base = f"{endpoint.rstrip('/')}/{bucket}/sha256/"
        self._region = region
        self._key_id = key_id
        self._secret = secret
        self._client = httpx.Client(transport=transport, timeout=TIMEOUT_SECONDS)

    def __repr__(self) -> str:
        return f"StorageBlobStore({self._base!r})"

    def _headers(self, method: str, url: str, payload_sha256: str) -> dict[str, str]:
        return sigv4_headers(
            method, url, payload_sha256, key_id=self._key_id,
            secret=self._secret.get_secret_value(), region=self._region, now=datetime.now(UTC),
        )  # fmt: skip

    def put(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        url = self._base + digest
        headers = self._headers("PUT", url, digest)
        headers["content-type"] = "application/octet-stream"
        self._client.put(url, content=data, headers=headers).raise_for_status()
        return PREFIX + digest

    def get(self, ref: str) -> bytes:
        url = self._base + digest_of(ref)
        empty = hashlib.sha256(b"").hexdigest()
        response = self._client.get(url, headers=self._headers("GET", url, empty))
        if response.status_code == 404:  # Supabase answers a missing object with 404
            raise KeyError(ref)
        response.raise_for_status()
        return response.content


class LayeredBlobStore:
    """Put to `primary`; get from `primary`, then from `fallback` on a miss."""

    def __init__(self, primary: BlobStore, fallback: BlobStore) -> None:
        self._primary = primary
        self._fallback = fallback

    def put(self, data: bytes) -> str:
        return self._primary.put(data)

    def get(self, ref: str) -> bytes:
        try:
            return self._primary.get(ref)
        except KeyError:
            return self._fallback.get(ref)


class FileBlobStore:
    """Blobs as files `<root>/<hex>` (a local run; the folder must be gitignored)."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def put(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._root / digest
        if not path.exists():
            tmp = path.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.replace(path)
        return PREFIX + digest

    def get(self, ref: str) -> bytes:
        path = self._root / digest_of(ref)
        try:
            return path.read_bytes()
        except FileNotFoundError:
            raise KeyError(ref) from None


STORAGE_FIELDS = (
    "storage_s3_endpoint",
    "storage_s3_region",
    "storage_bucket",
    "storage_access_key_id",
    "storage_secret_access_key",
)


def storage_from_settings(settings: Settings) -> StorageBlobStore | None:
    """The Storage store when all five settings are set, None when none is."""
    values = {
        name: (v.get_secret_value() if isinstance(v, SecretStr) else v)
        for name in STORAGE_FIELDS
        for v in [getattr(settings, name)]
    }
    missing = [name for name, value in values.items() if not value]
    if len(missing) == len(STORAGE_FIELDS):
        return None
    if missing:
        names = ", ".join(missing)
        raise StorageNotConfigured(f"Storage needs all five settings; missing: {names}")
    return StorageBlobStore(
        endpoint=settings.storage_s3_endpoint,
        region=settings.storage_s3_region,
        bucket=settings.storage_bucket,
        key_id=settings.storage_access_key_id,
        secret=settings.storage_secret_access_key,
    )
