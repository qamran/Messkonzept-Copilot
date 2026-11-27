"""MKC-49.6 unit tests for the HTTP fetcher: law HTML from gesetze-im-internet.de becomes
plain text with one line per heading and per Absatz; anything it cannot read is refused.

Synthetic HTML in the site's layout; the transport is fake, nothing reaches the network.
"""

from collections.abc import Callable

import httpx
import pytest

from mkc.rag.sources import CorpusSource, LicenceClass, SourceType

LAW_HTML = """<html><head><meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1"/>
</head><body><div id="paddingLR12">
<div class="jnnorm" title="Einzelnorm"><div class="jnheader"><a name="x"/>
<a href="index.html">Nichtamtliches Inhaltsverzeichnis</a>
<h3><span class="jnenbez">Inhalts&#252;bersicht</span>&#160;
<span class="jnentitel"></span></h3></div>
<div class="jnhtml"><div class="S2">Teil 1</div></div></div>
<div class="jnnorm" title="Einzelnorm"><div class="jnheader">
<h3><span class="jnenbez">&#167; 1</span>&#160;
<span class="jnentitel">Zweck</span></h3></div>
<div><div class="jnhtml"><div><div class="jurAbsatz">(1) Das Gesetz regelt
den Messstellenbetrieb.</div><div class="jurAbsatz">(2) Es gilt f\xfcr:<dl><dt>1.</dt>
<dd><div>Z\xe4hler,</div></dd><dt>2.</dt><dd><div>Gateways nach &#167; 14a.</div></dd></dl>
</div></div></div></div></div>
<div class="jnnorm" title="Einzelnorm"><div class="jnheader">
<h3><span class="jnenbez">&#167;&#167; 2 und 3</span>&#160;
<span class="jnentitel">(weggefallen)</span></h3>
</div></div>
<div class="jnnorm" title="Einzelnorm"><div class="jnheader">
<h3><span class="jnenbez">&#167; 4</span>&#160;
<span class="jnentitel">Inkrafttreten</span></h3></div>
<div class="jnhtml"><div class="jurAbsatz">Das Gesetz tritt in Kraft.<br/>Sofort.</div>
<div class="jnfussnote">Fu\xdfnote: nicht Teil des Textes.</div></div></div>
</div></body></html>
""".encode("iso-8859-1")

EXPECTED = """\
§ 1 Zweck
(1) Das Gesetz regelt den Messstellenbetrieb.
(2) Es gilt für: 1. Zähler, 2. Gateways nach § 14a.

§§ 2 und 3 (weggefallen)

§ 4 Inkrafttreten
Das Gesetz tritt in Kraft. Sofort.
"""


def _source(url: str = "https://www.gesetze-im-internet.de/musterg/x.html") -> CorpusSource:
    return CorpusSource(
        id="musterg",
        title="Mustergesetz",
        source_type=SourceType.LAW,
        url=url,
        version="2026",
        licence=LicenceClass.OFFICIAL,
    )


def _fetcher(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[..., str]:
    from mkc.rag.fetch import http_fetcher

    return http_fetcher(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_law_html_becomes_one_line_per_heading_and_absatz() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, content=LAW_HTML, headers={"content-type": "text/html"})

    assert _fetcher(handler)(_source()) == EXPECTED
    assert seen == ["https://www.gesetze-im-internet.de/musterg/x.html"]


def test_the_law_text_chunks_per_absatz() -> None:
    from mkc.rag.chunking import chunk_text

    refs = [c.source_ref for c in chunk_text(EXPECTED, source_id="musterg")]
    assert refs == ["§ 1 Abs. 1", "§ 1 Abs. 2", "§§ 2 und 3", "§ 4"]


def test_plain_text_is_passed_on() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="§ 1 A\n(1) B.\n", headers={"content-type": "text/plain"})

    assert _fetcher(handler)(_source()) == "§ 1 A\n(1) B.\n"


@pytest.mark.parametrize(
    ("status", "content", "content_type"),
    [
        (200, b"%PDF-1.7 ...", "application/pdf"),
        (200, b"%PDF-1.7 ...", "text/html"),  # BNetzA serves a PDF under an .html URL
        (200, b"<html><body><p>Kein Gesetz</p></body></html>", "text/html"),
        (200, b"\x00\x01", "application/octet-stream"),
        (404, b"not found", "text/html"),
        (503, b"down", "text/html"),
    ],
)
def test_what_it_cannot_read_is_refused(status: int, content: bytes, content_type: str) -> None:
    from mkc.rag.fetch import CorpusFetchError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=content, headers={"content-type": content_type})

    with pytest.raises(CorpusFetchError):
        _fetcher(handler)(_source())


def test_only_https_and_no_redirect_to_another_host() -> None:
    from mkc.rag.fetch import CorpusFetchError

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.gesetze-im-internet.de":
            return httpx.Response(302, headers={"location": "https://evil.example/x.html"})
        return httpx.Response(200, content=LAW_HTML, headers={"content-type": "text/html"})

    fetch = _fetcher(handler)
    with pytest.raises(CorpusFetchError, match="https"):
        fetch(_source("http://www.gesetze-im-internet.de/musterg/x.html"))
    with pytest.raises(CorpusFetchError, match="host"):
        fetch(_source())


def test_a_redirect_on_the_same_host_is_followed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old.html":
            return httpx.Response(301, headers={"location": "/musterg/x.html"})
        return httpx.Response(200, content=LAW_HTML, headers={"content-type": "text/html"})

    url = "https://www.gesetze-im-internet.de/old.html"
    assert _fetcher(handler)(_source(url)) == EXPECTED


def test_a_body_over_the_size_limit_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    from mkc.rag import fetch
    from mkc.rag.fetch import CorpusFetchError

    monkeypatch.setattr(fetch, "MAX_BYTES", 100)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=LAW_HTML, headers={"content-type": "text/html"})

    with pytest.raises(CorpusFetchError, match="large"):
        _fetcher(handler)(_source())


SINGLE_PARAGRAPH_HTML = b"""<html><body><div id="paddingLR12">
<div class="jnheader"><a name="x"/><a href="index.html">Nichtamtliches Inhaltsverzeichnis</a>
<h1>Gesetz (EnWG)<br /><span class="jnenbez">&#167; 14a</span>&#160;
<span class="jnentitel">Netzorientierte Steuerung</span></h1></div>
<div><div class="jnhtml"><div><div class="jurAbsatz">(1) Erster.</div>
<div class="jurAbsatz">(2) Zweiter.</div></div></div></div>
</div></body></html>
"""


def test_a_single_paragraph_page_without_a_norm_wrapper() -> None:
    from mkc.rag.fetch import law_text

    text = law_text(SINGLE_PARAGRAPH_HTML.decode())
    assert text == "§ 14a Netzorientierte Steuerung\n(1) Erster.\n(2) Zweiter.\n"
