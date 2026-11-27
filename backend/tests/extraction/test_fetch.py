"""MKC-21: `fetch_document` (feature 27): allow-listed URLs, hashing, editions.

Pinned interface (module `mkc.extraction.fetch`):

    fetch_document(operator_id, *, sessions, store, get=http_get, operators=None) -> SourceDocument

- `store` is a `mkc.harness.blobs.BlobStore`; the PDF goes there and nowhere else.
- `get(url) -> FetchResponse(url=<final URL after redirects>, content=<bytes>)`.
- `operators` maps operator id to `OperatorConfig`; None means `load_operators()`.
- Refusals raise `DisallowedUrl` before any write.
- `SourceDocument` has at least: operator_id, url, sha256 (hex), fetched_at, page_count,
  edition (1, 2, ... per operator) and new_edition (True when this fetch found a hash that
  differs from the operator's previous edition; False on the first fetch and on a re-fetch
  of the same bytes).
"""

import hashlib

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


@pytest.mark.parametrize(
    "url",
    [
        "http://netz.example/messkonzepte.pdf",  # not https
        "https://evil.example/messkonzepte.pdf",  # host not on the list
        "https://netz.example.evil.example/messkonzepte.pdf",  # look-alike suffix
        "https://evilnetz.example/messkonzepte.pdf",  # look-alike prefix
        "https://netz.example@evil.example/messkonzepte.pdf",  # userinfo trick
        "ftp://netz.example/messkonzepte.pdf",
        "file:///etc/passwd",
        "",
    ],
)
def test_is_allowed_url_refuses(url: str) -> None:
    from mkc.extraction.fetch import is_allowed_url

    assert is_allowed_url(url, ("netz.example",)) is False


def test_is_allowed_url_accepts_a_listed_https_host() -> None:
    from mkc.extraction.fetch import is_allowed_url

    assert is_allowed_url("https://netz.example/a/messkonzepte.pdf", ("netz.example",)) is True


def test_disallowed_url_refused(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.extraction.fetch import DisallowedUrl, fetch_document

    get = FakeGet([("https://evil.example/x.pdf", make_pdf([["Messkonzept 1"]]))])
    ops = operators(url="https://evil.example/x.pdf")
    with pytest.raises(DisallowedUrl):
        fetch_document(OPERATOR_ID, sessions=sessions, store=store, get=get, operators=ops)
    assert get.calls == [], "a disallowed URL must never be requested"
    assert store.data == {}
    assert rows(engine, "select id from source_document") == []


def test_redirect_off_the_allow_list_refused(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.extraction.fetch import DisallowedUrl, fetch_document

    get = FakeGet([("https://evil.example/x.pdf", make_pdf([["Messkonzept 1"]]))])
    with pytest.raises(DisallowedUrl):
        fetch_document(OPERATOR_ID, sessions=sessions, store=store, get=get, operators=operators())
    assert store.data == {}, "bytes from a host off the list must not be cached"
    assert rows(engine, "select id from source_document") == []


def test_fetch_hashes_caches_and_records(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.extraction.fetch import fetch_document

    pdf = make_pdf(berlin_pages(["1", "2a", "3"]))
    get = FakeGet([(URL_OK, pdf)])
    doc = fetch_document(
        OPERATOR_ID, sessions=sessions, store=store, get=get, operators=operators()
    )
    assert get.calls == [URL_OK]
    assert doc.operator_id == OPERATOR_ID
    assert doc.url == URL_OK
    assert doc.sha256 == hashlib.sha256(pdf).hexdigest()
    assert doc.page_count == 6
    assert doc.fetched_at is not None
    assert doc.edition == 1
    assert doc.new_edition is False
    assert list(store.data.values()) == [pdf]
    assert rows(engine, "select operator_id, sha256, edition from source_document") == [
        (OPERATOR_ID, doc.sha256, 1)
    ]


def test_same_hash_again_creates_no_new_edition(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    from mkc.extraction.fetch import fetch_document

    pdf = make_pdf(berlin_pages(["1", "2a", "3"]))
    get = FakeGet([(URL_OK, pdf), (URL_OK, pdf)])
    kw = {"sessions": sessions, "store": store, "get": get, "operators": operators()}
    first = fetch_document(OPERATOR_ID, **kw)
    again = fetch_document(OPERATOR_ID, **kw)
    assert again.sha256 == first.sha256
    assert again.edition == 1
    assert again.new_edition is False
    assert len(rows(engine, "select id from source_document")) == 1


def test_new_hash_at_same_url_creates_new_edition_and_flags_it(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    # Review Focus 1: the operator republishes the PDF at the same URL.
    from mkc.extraction.fetch import fetch_document

    v1 = make_pdf(berlin_pages(["1", "2a", "3"]))
    v2 = make_pdf(berlin_pages(["1", "2a", "3", "4"]))
    get = FakeGet([(URL_OK, v1), (URL_OK, v2)])
    kw = {"sessions": sessions, "store": store, "get": get, "operators": operators()}
    old = fetch_document(OPERATOR_ID, **kw)
    new = fetch_document(OPERATOR_ID, **kw)

    assert get.calls == [URL_OK, URL_OK]
    assert new.url == old.url
    assert new.sha256 == hashlib.sha256(v2).hexdigest() != old.sha256
    assert new.edition == 2
    assert new.new_edition is True, "the change of edition must be flagged"
    assert rows(engine, "select sha256, edition from source_document order by edition") == [
        (old.sha256, 1),
        (new.sha256, 2),
    ]
    assert rows(engine, f"select edition from operator where id = '{OPERATOR_ID}'") == [(2,)]


def test_editions_are_numbered_per_operator(
    engine: Engine, sessions: sessionmaker[Session], store: MemoryStore
) -> None:
    # Review Focus 1 (mutation pass): another operator's editions never count towards this
    # operator's numbering or its new-edition flag.
    from mkc.extraction.fetch import fetch_document
    from mkc.extraction.operators import OperatorConfig

    other_url = "https://other.example/messkonzepte.pdf"
    ops = {
        **operators(),
        "other": OperatorConfig(
            id="other",
            name="Other (test)",
            voltage_level="NS",
            url=other_url,
            allowed_hosts=("other.example",),
        ),
    }
    get = FakeGet(
        [(URL_OK, make_pdf(berlin_pages(["1"]))), (other_url, make_pdf(berlin_pages(["1", "2"])))]
    )
    kw = {"sessions": sessions, "store": store, "get": get, "operators": ops}
    first = fetch_document(OPERATOR_ID, **kw)
    other = fetch_document("other", **kw)
    assert (first.edition, first.new_edition) == (1, False)
    assert (other.edition, other.new_edition) == (1, False)
