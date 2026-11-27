"""MKC-21.2 (development agent): the edition rules and checks beyond the acceptance tests.

- A hash that differs from the latest edition's is a new edition, even when an older edition
  had it (A, B, A gives editions 1, 2, 3; decision 62).
- A response that is not a PDF is refused before any write.
- `http_get` follows only https redirects and fails on an HTTP error.
"""

import hashlib

import httpx
import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from tests.extraction.conftest import (
    OPERATOR_ID,
    URL_OK,
    FakeGet,
    MemoryStore,
    berlin_pages,
    make_pdf,
    operators,
    rows,
)


def test_a_return_to_an_older_hash_is_a_new_edition(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.extraction.fetch import fetch_document

    a = make_pdf(berlin_pages(["1"]))
    b = make_pdf(berlin_pages(["1", "2"]))
    get = FakeGet([(URL_OK, a), (URL_OK, b), (URL_OK, a)])
    kw = {"sessions": sessions, "store": store, "get": get, "operators": operators()}
    docs = [fetch_document(OPERATOR_ID, **kw) for _ in range(3)]
    assert [(d.edition, d.new_edition) for d in docs] == [(1, False), (2, True), (3, True)]
    assert docs[2].sha256 == docs[0].sha256 == hashlib.sha256(a).hexdigest()
    assert rows(engine, f"select edition from operator where id = '{OPERATOR_ID}'") == [(3,)]
    assert store.puts == 3 and len(store.data) == 2, "the same bytes are one object"


def test_operator_row_follows_the_config(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.extraction.fetch import fetch_document

    pdf = make_pdf(berlin_pages(["1"]))
    fetch_document(
        OPERATOR_ID, sessions=sessions, store=store, get=FakeGet([(URL_OK, pdf)]),
        operators=operators(),
    )  # fmt: skip
    assert rows(engine, "select id, name, voltage_level, url, edition from operator") == [
        (OPERATOR_ID, "Netz Musterstadt (test)", "NS", URL_OK, 1)
    ]


@pytest.mark.parametrize("content", [b"<html>Wartungsarbeiten</html>", b"", b"%PDF-1.4 broken"])
def test_a_response_that_is_no_pdf_is_refused_before_any_write(
    content: bytes, engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.extraction.fetch import NotAPdf, fetch_document

    with pytest.raises(NotAPdf):
        fetch_document(
            OPERATOR_ID, sessions=sessions, store=store, get=FakeGet([(URL_OK, content)]),
            operators=operators(),
        )  # fmt: skip
    assert store.data == {}
    assert rows(engine, "select id from source_document") == []


def test_an_unknown_operator_is_refused(
    sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.extraction.fetch import UnknownOperator, fetch_document

    get = FakeGet([])
    with pytest.raises(UnknownOperator):
        fetch_document("nobody", sessions=sessions, store=store, get=get, operators=operators())
    assert get.calls == []


def _transport(routes: dict[str, httpx.Response]) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        return routes[str(request.url)]

    return httpx.MockTransport(handle)


def test_http_get_follows_an_https_redirect_and_reports_the_final_url() -> None:
    from mkc.extraction.fetch import http_get

    final = "https://netz.example/v2.pdf"
    transport = _transport(
        {
            URL_OK: httpx.Response(302, headers={"location": final}),
            final: httpx.Response(200, content=b"%PDF-data"),
        }
    )
    response = http_get(URL_OK, transport=transport)
    assert response.url == final
    assert response.content == b"%PDF-data"


def test_http_get_refuses_a_redirect_to_plain_http() -> None:
    from mkc.extraction.fetch import DisallowedUrl, http_get

    transport = _transport(
        {URL_OK: httpx.Response(302, headers={"location": "http://netz.example/x.pdf"})}
    )
    with pytest.raises(DisallowedUrl):
        http_get(URL_OK, transport=transport)


def test_http_get_fails_on_an_http_error() -> None:
    from mkc.extraction.fetch import http_get

    with pytest.raises(httpx.HTTPStatusError):
        http_get(URL_OK, transport=_transport({URL_OK: httpx.Response(404)}))
