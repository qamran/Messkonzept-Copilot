"""MKC-23.5: redirect hops are held to the operator's `allowed_hosts` (decision 62 (5)).

The red tests (`test_redirect_hops.py`) pin `http_get` without the argument (only the given
URL's host). These pin the rest: a hop to another host on the list is followed, and
`fetch_document`'s default getter passes the operator's list to `http_get`.
"""

from typing import Any

import httpx
import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from mkc.extraction.fetch import FetchResponse
from tests.extraction.conftest import (
    OPERATOR_ID,
    URL_OK,
    MemoryStore,
    berlin_pages,
    make_pdf,
    operators,
)


def test_a_hop_to_another_listed_host_is_followed() -> None:
    from mkc.extraction.fetch import DisallowedUrl, http_get

    cdn = "https://cdn.netz.example/a.pdf"
    seen: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if str(request.url) == URL_OK:
            return httpx.Response(302, headers={"location": cdn})
        return httpx.Response(200, content=b"%PDF-x")

    hosts = ("netz.example", "cdn.netz.example")
    transport = httpx.MockTransport(handle)
    assert http_get(URL_OK, transport=transport, allowed_hosts=hosts).url == cdn
    assert seen == [URL_OK, cdn]
    with pytest.raises(DisallowedUrl, match="off the allow-list"):
        http_get(URL_OK, transport=transport, allowed_hosts=("netz.example",))


def test_fetch_document_passes_the_operators_list_to_http_get(
    engine: Engine,
    sessions: sessionmaker[Session],
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mkc.extraction import fetch

    seen: list[dict[str, Any]] = []
    pdf = make_pdf(berlin_pages(["1"]))

    def fake_get(url: str, **kw: Any) -> FetchResponse:
        seen.append({"url": url, **kw})
        return FetchResponse(url=url, content=pdf)

    monkeypatch.setattr(fetch, "http_get", fake_get)
    ops = operators()
    fetch.fetch_document(OPERATOR_ID, sessions=sessions, store=store, operators=ops)
    assert seen == [{"url": URL_OK, "allowed_hosts": ops[OPERATOR_ID].allowed_hosts}]
