"""MKC-22.4: `content-length` is only an early exit for the download limit (decision 78). A
malformed value is ignored and the streamed body still decides."""

import httpx
import pytest

from tests.extraction.conftest import URL_OK


def _transport(length: str, body: bytes) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-length": length}, content=iter([body]))

    return httpx.MockTransport(handle)


@pytest.mark.parametrize("length", ["abc", "-1", "1e3"])
def test_a_malformed_content_length_is_ignored(length: str) -> None:
    from mkc.extraction.fetch import DownloadTooLarge, http_get

    assert http_get(URL_OK, transport=_transport(length, b"%PDF-1"), max_bytes=10).content == (
        b"%PDF-1"
    )
    with pytest.raises(DownloadTooLarge):
        http_get(URL_OK, transport=_transport(length, b"%PDF-" + b"x" * 20), max_bytes=10)
