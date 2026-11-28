"""MKC-23 (PR #215 finding 8, decision 62 (5)): intermediate redirect hops stay on the
allow-listed host and port.

Until MKC-22, `http_get` requested any https hop and only the final URL was checked. Pinned
(assumption): with no new argument, a hop is refused with `DisallowedUrl` **before it is
requested** unless it keeps the host and port of the URL `http_get` was given (the
configured URL, which `fetch_document` has already checked against the allow-list; every
operator in `operators.yaml` lists exactly one host). Redirects on the same host still work
(`test_a_cookie_set_by_a_hop_is_not_sent_on_a_later_hop`).
"""

import httpx
import pytest

from tests.extraction.conftest import URL_OK


def _chain(*hops: tuple[str, httpx.Response]) -> tuple[httpx.MockTransport, list[str]]:
    answers = {str(httpx.URL(url)): response for url, response in hops}  # `:443` dropped
    seen: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return answers[str(request.url)]

    return httpx.MockTransport(handle), seen


def _to(url: str) -> httpx.Response:
    return httpx.Response(302, headers={"location": url})


@pytest.mark.parametrize(
    "hop",
    [
        "https://cdn.other.example/a.pdf",  # another host
        "https://netz.example:8443/a.pdf",  # the listed host on another port
        "https://evil.netz.example/a.pdf",  # a subdomain is another host
    ],
)
def test_an_off_list_hop_is_refused_before_it_is_requested(hop: str) -> None:
    from mkc.extraction.fetch import DisallowedUrl, http_get

    final = "https://netz.example/final.pdf"
    transport, seen = _chain(
        (URL_OK, _to(hop)), (hop, _to(final)), (final, httpx.Response(200, content=b"%PDF-x"))
    )
    with pytest.raises(DisallowedUrl):
        http_get(URL_OK, transport=transport)
    assert seen == [URL_OK], "the off-list hop was never requested"


def test_the_explicit_default_port_is_the_same_host() -> None:
    from mkc.extraction.fetch import http_get

    hop = "https://netz.example:443/b.pdf"
    transport, seen = _chain((URL_OK, _to(hop)), (hop, httpx.Response(200, content=b"%PDF-x")))
    assert http_get(URL_OK, transport=transport).content == b"%PDF-x"
    assert seen == [URL_OK, "https://netz.example/b.pdf"]
