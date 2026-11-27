"""The HTTP fetcher of `mkc corpus load` (MKC-49.6): a source's URL → its plain text.

- Only the URL in the sources file is fetched, over https; a redirect may not leave the host.
- Law pages of gesetze-im-internet.de become one line per paragraph heading and one line per
  Absatz, the layout `mkc.rag.chunking` splits (`law`). Footnotes and the table of contents
  are left out.
- Plain text is passed on. PDFs (the BNetzA decisions, operator catalogues) are refused for
  now: the PDF library comes with lane A (MKC-21), and this lane does not add a second one.

Nothing is written to disk here; the loader's optional cache has its own licence guard.
"""

import re
from collections.abc import Callable
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

from mkc.rag.sources import CorpusSource

MAX_BYTES = 20_000_000
"""The largest body read; the full MsbG page is about 0.3 MB."""

MAX_REDIRECTS = 5
TIMEOUT_SECONDS = 60.0
USER_AGENT = "mkc-corpus-loader/1.0"

_CHARSET = re.compile(rb"""charset=["']?([A-Za-z0-9_-]+)""")
_BLOCK_TAGS = frozenset({"br", "div", "p", "dl", "dt", "dd", "li", "ol", "ul", "table", "tr"})
_VOID_TAGS = frozenset({"br", "img", "hr", "meta", "link", "input", "area", "col", "wbr"})


class CorpusFetchError(RuntimeError):
    """A source could not be fetched, or its format cannot be read yet."""


def _clean(value: str) -> str:
    return " ".join(value.split())


class _LawPage(HTMLParser):
    """Collects (heading, [Absatz, …]) per `jnheader`; `law_text` keeps the `§` ones."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.norms: list[tuple[str, list[str]]] = []
        self._stack: list[str | None] = []  # the capture opened by each open tag, if any
        self._buffers: dict[str, list[str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = (dict(attrs).get("class") or "").split()
        capture = None
        if "jnheader" in classes:  # one per paragraph, with or without a jnnorm wrapper
            self.norms.append(("", []))
        elif "jnenbez" in classes or "jnentitel" in classes or "jurAbsatz" in classes:
            capture = next(c for c in ("jnenbez", "jnentitel", "jurAbsatz") if c in classes)
            self._buffers[capture] = []
        if tag in _BLOCK_TAGS:
            self._text(" ")
        if tag not in _VOID_TAGS:
            self._stack.append(capture)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _BLOCK_TAGS:
            self._text(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_TAGS or not self._stack:
            return
        capture = self._stack.pop()
        if capture is None or not self.norms:
            return
        value = _clean("".join(self._buffers.pop(capture, [])))
        heading, absaetze = self.norms[-1]
        if capture == "jurAbsatz":
            if value:
                absaetze.append(value)
        else:
            self.norms[-1] = (_clean(f"{heading} {value}"), absaetze)

    def handle_data(self, data: str) -> None:
        self._text(data)

    def _text(self, value: str) -> None:
        for buffer in self._buffers.values():
            buffer.append(value)


def law_text(page: str) -> str:
    """The plain text of a gesetze-im-internet.de page: paragraphs only, blank-line separated."""
    parser = _LawPage()
    parser.feed(page)
    parser.close()
    blocks = [
        "\n".join([heading, *absaetze])
        for heading, absaetze in parser.norms
        if heading.startswith("§")
    ]
    if not blocks:
        raise CorpusFetchError("no paragraphs found: not a gesetze-im-internet.de law page")
    return "\n\n".join(blocks) + "\n"


def _decode(body: bytes, content_type: str) -> str:
    match = _CHARSET.search(content_type.encode()) or _CHARSET.search(body[:4096])
    encoding = match.group(1).decode() if match else "utf-8"
    try:
        return body.decode(encoding)
    except (LookupError, UnicodeDecodeError) as error:
        raise CorpusFetchError(f"cannot decode the page as {encoding}: {error}") from error


def _get(client: httpx.Client, url: str) -> tuple[bytes, str]:
    """GET over https, following redirects on the same host only, at most `MAX_BYTES`."""
    host = urlsplit(url).hostname
    for _ in range(MAX_REDIRECTS + 1):
        if urlsplit(url).scheme != "https":
            raise CorpusFetchError(f"only https URLs are fetched: {url}")
        if urlsplit(url).hostname != host:
            raise CorpusFetchError(f"redirect to another host refused: {url}")
        with client.stream("GET", url, headers={"user-agent": USER_AGENT}) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers["location"])
                continue
            if response.status_code != 200:
                raise CorpusFetchError(f"HTTP {response.status_code} for {url}")
            body = bytearray()
            for part in response.iter_bytes():
                body += part
                if len(body) > MAX_BYTES:
                    raise CorpusFetchError(f"body too large (over {MAX_BYTES} bytes): {url}")
            return bytes(body), response.headers.get("content-type", "")
    raise CorpusFetchError(f"more than {MAX_REDIRECTS} redirects: {url}")


def http_fetcher(*, client: httpx.Client | None = None) -> Callable[[CorpusSource], str]:
    """A fetcher over `client` (a test seam; default: a fresh client with a timeout)."""
    http = client or httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False)

    def fetch(source: CorpusSource) -> str:
        body, content_type = _get(http, source.url)
        kind = content_type.split(";")[0].strip().lower()
        if body.startswith(b"%PDF") or kind == "application/pdf":
            raise CorpusFetchError(
                f"{source.id}: PDF sources are not supported yet (the PDF library comes "
                "with MKC-21); load the others with --source"
            )
        if kind == "text/html":
            return law_text(_decode(body, content_type))
        if kind == "text/plain":
            return _decode(body, content_type)
        raise CorpusFetchError(f"{source.id}: cannot read content type {kind or 'none'!r}")

    return fetch
