"""Run-level `fetch_document` (feature 27, MKC-21.2, decisions 62 and 63).

Order, so nothing is written for a refused document: the configured URL must be allow-listed
(else no request), the final URL after redirects must be too, the bytes must parse as a PDF;
only then do the bytes go to the `BlobStore` (Supabase Storage in production) and the edition
row to Postgres. The PDF never touches local disk or the Postgres `blob` table.

Editions (decision 62): an operator's first fetch is edition 1 (`new_edition` False). The
same bytes as the latest edition add nothing. Any other hash, also one an older edition had,
is the next edition with `new_edition` True. The operator row is locked while the edition is
chosen, so two fetches never take the same number.
"""

import hashlib
import io
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from http.cookiejar import DefaultCookiePolicy
from urllib.parse import urlsplit

import httpx
import pdfplumber
from pdfplumber.utils.exceptions import PdfminerException
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from mkc.db.models import Operator
from mkc.db.models import SourceDocument as SourceDocumentRow
from mkc.extraction.operators import OperatorConfig, load_operators
from mkc.harness.blobs import PREFIX, BlobStore

MAX_REDIRECTS = 5
# The Storage bucket's file size limit (decision 63): a larger PDF could not be stored.
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
TIMEOUT_SECONDS = 60.0
USER_AGENT = "mkc-fetch/1 (Messkonzept-Copilot)"


class DisallowedUrl(ValueError):
    """The URL (or a redirect) is not https or not on the operator's allow-list."""


class DownloadTooLarge(ValueError):
    """The response body is over `MAX_DOWNLOAD_BYTES`; nothing is stored."""


class NotAPdf(ValueError):
    """The response is not a readable PDF."""


class UnknownOperator(KeyError):
    """No operator with this id in the allow-list."""


@dataclass(frozen=True)
class FetchResponse:
    url: str  # the final URL after redirects
    content: bytes


@dataclass(frozen=True)
class SourceDocument:
    """One fetched edition, detached from the session. `sha256` is the document hash that
    items, drafts and the tool cache are keyed by; the PDF is at `blob:sha256:<sha256>`."""

    operator_id: str
    url: str
    sha256: str
    fetched_at: datetime
    page_count: int
    edition: int
    new_edition: bool

    @property
    def ref(self) -> str:
        return PREFIX + self.sha256


Getter = Callable[[str], FetchResponse]


def is_allowed_url(url: str, allowed_hosts: tuple[str, ...]) -> bool:
    """https, no userinfo, the default port (none or 443), and a host equal
    (case-insensitive) to one on the list. A malformed URL or port is False, never an error."""
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError:
        return False
    if parts.scheme != "https" or _has_userinfo(url) or not host or port not in (None, 443):
        return False
    return host.lower() in {h.lower() for h in allowed_hosts}


def http_get(
    url: str,
    *,
    transport: httpx.BaseTransport | None = None,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
) -> FetchResponse:
    """GET `url`, following at most five redirects, each to an https URL without userinfo
    (refused before it is requested). The caller checks the final URL against its
    allow-list. No cookie is kept between hops. The body is read as a stream and refused
    with `DownloadTooLarge` once it passes `max_bytes`, whatever `content-length` says.
    Raises on an HTTP error status."""
    with httpx.Client(
        transport=transport,
        timeout=TIMEOUT_SECONDS,
        follow_redirects=False,
        headers={"user-agent": USER_AGENT},
    ) as client:
        # A jar that refuses every cookie: no hop's cookie reaches a later hop. (The client
        # copies a jar it is given, policy lost, so the policy goes on its own jar.)
        client.cookies.jar.set_policy(DefaultCookiePolicy(allowed_domains=[]))
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            with client.stream("GET", current) as response:
                if not response.is_redirect:
                    response.raise_for_status()
                    return FetchResponse(url=current, content=_read(response, max_bytes))
                target = str(response.url.join(response.headers["location"]))
            if urlsplit(target).scheme != "https":
                raise DisallowedUrl(f"redirect from {current} to a non-https URL")
            if _has_userinfo(target):
                raise DisallowedUrl(f"redirect from {current} to a URL with userinfo")
            current = target
    raise DisallowedUrl(f"more than {MAX_REDIRECTS} redirects from {url}")


def _has_userinfo(url: str) -> bool:
    return "@" in urlsplit(url).netloc


def _read(response: httpx.Response, max_bytes: int) -> bytes:
    declared = response.headers.get("content-length", "")
    if declared.isascii() and declared.isdigit() and int(declared) > max_bytes:
        raise DownloadTooLarge(f"content-length {declared} is over {max_bytes} bytes")
    body = bytearray()
    for chunk in response.iter_bytes():
        body += chunk
        if len(body) > max_bytes:
            raise DownloadTooLarge(f"the body is over {max_bytes} bytes")
    return bytes(body)


def page_count(content: bytes) -> int:
    """The number of pages, or `NotAPdf`."""
    if not content.startswith(b"%PDF-"):
        raise NotAPdf("the response does not start with %PDF-")
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            count = len(pdf.pages)
    except (PdfminerException, ValueError, TypeError, KeyError) as error:
        raise NotAPdf(f"the PDF cannot be read: {type(error).__name__}") from error
    if count < 1:
        raise NotAPdf("the PDF has no pages")
    return count


def fetch_document(
    operator_id: str,
    *,
    sessions: sessionmaker[Session],
    store: BlobStore,
    get: Getter = http_get,
    operators: dict[str, OperatorConfig] | None = None,
) -> SourceDocument:
    """Fetch the operator's catalogue, cache it in `store` and record its edition."""
    ops = load_operators() if operators is None else operators
    if operator_id not in ops:
        raise UnknownOperator(operator_id)
    op = ops[operator_id]
    if not is_allowed_url(op.url, op.allowed_hosts):
        raise DisallowedUrl(f"{op.url} is not on the allow-list of {operator_id}")
    response = get(op.url)
    if not is_allowed_url(response.url, op.allowed_hosts):
        raise DisallowedUrl(f"{op.url} ended at {response.url}, off the allow-list")
    pages = page_count(response.content)
    digest = hashlib.sha256(response.content).hexdigest()
    ref = store.put(response.content)
    if ref != PREFIX + digest:
        raise RuntimeError(f"the store returned {ref} for sha256 {digest}")
    with sessions.begin() as session:
        return _record(session, op, response.url, digest, pages)


def _record(
    session: Session, op: OperatorConfig, url: str, digest: str, pages: int
) -> SourceDocument:
    values = {"id": op.id, "name": op.name, "voltage_level": op.voltage_level, "url": op.url}
    session.execute(
        insert(Operator)
        .values(values)
        .on_conflict_do_update(index_elements=["id"], set_={**values, "updated_at": func.now()})
    )
    operator = session.scalars(select(Operator).where(Operator.id == op.id).with_for_update()).one()
    latest = session.scalars(
        select(SourceDocumentRow)
        .where(SourceDocumentRow.operator_id == op.id)
        .order_by(SourceDocumentRow.edition.desc())
        .limit(1)
    ).first()
    if latest is not None and latest.sha256 == digest:
        return _value(latest, new_edition=False)
    row = SourceDocumentRow(
        operator_id=op.id,
        edition=(latest.edition + 1) if latest else 1,
        url=url,
        sha256=digest,
        page_count=pages,
        fetched_at=session.scalar(select(func.now())),
    )
    session.add(row)
    session.flush()
    operator.edition = row.edition
    return _value(row, new_edition=latest is not None)


def _value(row: SourceDocumentRow, *, new_edition: bool) -> SourceDocument:
    return SourceDocument(
        operator_id=row.operator_id,
        url=row.url,
        sha256=row.sha256,
        fetched_at=row.fetched_at,
        page_count=row.page_count,
        edition=row.edition,
        new_edition=new_edition,
    )


def document_by_hash(session: Session, sha256: str) -> SourceDocument | None:
    """The newest edition with this hash (decision 64): a document hash is the sha256 of the
    PDF, and a return to older bytes is a later edition with the same hash and bytes."""
    row = session.scalars(
        select(SourceDocumentRow)
        .where(SourceDocumentRow.sha256 == sha256)
        .order_by(SourceDocumentRow.fetched_at.desc(), SourceDocumentRow.id.desc())
        .limit(1)
    ).first()
    return None if row is None else _value(row, new_edition=False)
