"""MKC-22 sub-issue "fetch hardening": the wave 1 review findings on MKC-21 (PR #197).

Pinned (module `mkc.extraction.fetch`):

1. A redirect whose `Location` carries userinfo (`https://u:p@cdn.example/y`) is refused with
   `DisallowedUrl` before it is requested; no request ever carries `authorization`.
2. No cookie jar: a cookie set by one hop is never sent on a later hop, also to the same host.
3. `is_allowed_url` refuses userinfo on a listed host (`https://user@netz.example/`), a
   pin for the MKC-21 mutation survivor 1.
4. The port is part of the match: only the default (no port, or `:443`) is allowed; another
   port, or a port that is no number, is refused (False, never an exception).
5. `MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024` (the bucket's limit) and
   `http_get(url, *, transport=None, max_bytes=MAX_DOWNLOAD_BYTES)`: a body over the limit
   raises `DownloadTooLarge` (a `ValueError`), whether `content-length` says so or not; the
   body is read as a stream and reading stops at the limit; nothing is stored.
"""

from collections.abc import Iterator

import httpx
import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from tests.extraction.conftest import (
    OPERATOR_ID,
    URL_OK,
    MemoryStore,
    berlin_pages,
    make_pdf,
    operators,
    rows,
)


def test_a_redirect_with_userinfo_is_refused_before_it_is_requested() -> None:
    from mkc.extraction.fetch import DisallowedUrl, http_get

    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(302, headers={"location": "https://u:p@cdn.example/y.pdf"})
        return httpx.Response(200, content=b"%PDF-data")

    with pytest.raises(DisallowedUrl):
        http_get(URL_OK, transport=httpx.MockTransport(handle))
    assert [str(r.url) for r in seen] == [URL_OK]
    assert not any("authorization" in r.headers for r in seen)


def test_a_cookie_set_by_a_hop_is_not_sent_on_a_later_hop() -> None:
    from mkc.extraction.fetch import http_get

    seen: list[httpx.Request] = []
    hops = {
        URL_OK: httpx.Response(
            302, headers={"location": "https://netz.example/b", "set-cookie": "s=1; Path=/"}
        ),
        "https://netz.example/b": httpx.Response(
            302, headers={"location": "https://netz.example/c", "set-cookie": "t=2; Path=/"}
        ),
        "https://netz.example/c": httpx.Response(200, content=b"%PDF-data"),
    }

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return hops[str(request.url)]

    assert http_get(URL_OK, transport=httpx.MockTransport(handle)).url == "https://netz.example/c"
    assert len(seen) == 3
    assert not any("cookie" in r.headers for r in seen)


@pytest.mark.parametrize(
    "url",
    [
        "https://user@netz.example/messkonzepte.pdf",
        "https://user:pw@netz.example/messkonzepte.pdf",
        "https://netz.example:8443/messkonzepte.pdf",
        "https://netz.example:80/messkonzepte.pdf",
        "https://netz.example:abc/messkonzepte.pdf",
        "https://netz.example:99999/messkonzepte.pdf",
    ],
)
def test_is_allowed_url_refuses_userinfo_and_other_ports(url: str) -> None:
    from mkc.extraction.fetch import is_allowed_url

    assert is_allowed_url(url, ("netz.example",)) is False


def test_is_allowed_url_accepts_the_default_port() -> None:
    from mkc.extraction.fetch import is_allowed_url

    assert is_allowed_url("https://netz.example:443/messkonzepte.pdf", ("netz.example",))


class Chunks:
    """A response body of `count` chunks of `size` bytes; counts the chunks read."""

    def __init__(self, count: int, size: int) -> None:
        self.count, self.size, self.read = count, size, 0

    def __iter__(self) -> Iterator[bytes]:
        for _ in range(self.count):
            self.read += 1
            yield b"%PDF-" + b"x" * (self.size - 5) if self.read == 1 else b"x" * self.size


def test_the_download_limit_is_the_buckets() -> None:
    from mkc.extraction.fetch import MAX_DOWNLOAD_BYTES

    assert MAX_DOWNLOAD_BYTES == 50 * 1024 * 1024


def test_a_body_over_the_limit_is_refused_while_it_streams() -> None:
    from mkc.extraction.fetch import DownloadTooLarge, http_get

    body = Chunks(count=10_000, size=1000)  # 10 MB, no content-length
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=iter(body)))
    with pytest.raises(DownloadTooLarge):
        http_get(URL_OK, transport=transport, max_bytes=2500)
    assert body.read < body.count, "reading stops near the limit, not at the end"
    assert issubclass(DownloadTooLarge, ValueError)


def test_a_content_length_over_the_limit_is_refused() -> None:
    from mkc.extraction.fetch import DownloadTooLarge, http_get

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"%PDF-" + b"x" * 3000)
    )
    with pytest.raises(DownloadTooLarge):
        http_get(URL_OK, transport=transport, max_bytes=2500)


def test_a_body_at_the_limit_is_accepted() -> None:
    from mkc.extraction.fetch import http_get

    body = Chunks(count=5, size=500)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=iter(body)))
    assert len(http_get(URL_OK, transport=transport, max_bytes=2500).content) == 2500


def test_an_oversized_download_is_never_stored(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.extraction.fetch import DownloadTooLarge, fetch_document, http_get

    pdf = make_pdf(berlin_pages(["1"]))
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=pdf))
    with pytest.raises(DownloadTooLarge):
        fetch_document(
            OPERATOR_ID, sessions=sessions, store=store, operators=operators(),
            get=lambda url: http_get(url, transport=transport, max_bytes=len(pdf) - 1),
        )  # fmt: skip
    assert store.data == {}
    assert rows(engine, "select id from source_document") == []
