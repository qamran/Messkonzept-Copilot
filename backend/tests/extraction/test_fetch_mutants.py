"""MKC-22 mutation pass (test agent): `http_get` refuses a declared `content-length` over the
limit before it reads any of the body, and its default limit is `MAX_DOWNLOAD_BYTES`."""

import inspect

import httpx
import pytest

from tests.extraction.conftest import URL_OK
from tests.extraction.test_fetch_hardening import Chunks


def test_a_declared_length_over_the_limit_is_refused_before_reading() -> None:
    from mkc.extraction.fetch import DownloadTooLarge, http_get

    body = Chunks(count=2, size=500)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-length": "1000000"}, content=iter(body)
        )
    )
    with pytest.raises(DownloadTooLarge):
        http_get(URL_OK, transport=transport, max_bytes=2500)
    assert body.read == 0


def test_the_default_limit_is_max_download_bytes() -> None:
    from mkc.extraction.fetch import MAX_DOWNLOAD_BYTES, http_get

    default = inspect.signature(http_get).parameters["max_bytes"].default
    assert default == MAX_DOWNLOAD_BYTES
