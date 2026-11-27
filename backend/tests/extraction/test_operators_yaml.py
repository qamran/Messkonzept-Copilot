"""MKC-21: `backend/data/operators.yaml` lists Berlin and SachsenNetze with allow-listed URLs.

Shape (pinned for the development agent):

    operators:
      - id: stromnetz-berlin
        name: ...
        voltage_level: ...
        url: https://...            # the catalogue PDF
        allowed_hosts: [<host>]     # the fetch allow-list for this operator

The test checks structure only, never real host names: every URL is https and its host is on
its own operator's allow-list.
"""

from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

OPERATORS_YAML = Path(__file__).resolve().parents[2] / "data" / "operators.yaml"
IDS = {"stromnetz-berlin", "sachsennetze"}


def _entries() -> list[dict[str, Any]]:
    assert OPERATORS_YAML.is_file(), f"missing {OPERATORS_YAML}"
    data = yaml.safe_load(OPERATORS_YAML.read_text("utf-8"))
    return list(data["operators"])


def test_operators_yaml_lists_berlin_and_sachsennetze() -> None:
    ids = [e["id"] for e in _entries()]
    assert len(ids) == len(set(ids)), "duplicate operator ids"
    assert set(ids) >= IDS


def test_every_operator_url_is_https_and_allow_listed() -> None:
    for entry in _entries():
        for key in ("id", "name", "voltage_level", "url", "allowed_hosts"):
            assert entry.get(key), (entry.get("id"), key)
        parts = urlsplit(entry["url"])
        assert parts.scheme == "https", entry["id"]
        assert parts.username is None and parts.password is None, entry["id"]
        assert parts.hostname in [h.lower() for h in entry["allowed_hosts"]], entry["id"]


def test_load_operators_reads_the_yaml() -> None:
    from mkc.extraction.operators import OPERATORS_YAML as PACKAGED
    from mkc.extraction.operators import load_operators

    assert Path(PACKAGED).resolve() == OPERATORS_YAML
    ops = load_operators()
    assert set(ops) >= IDS
    berlin = ops["stromnetz-berlin"]
    assert berlin.id == "stromnetz-berlin"
    assert berlin.url.startswith("https://")
    assert urlsplit(berlin.url).hostname in berlin.allowed_hosts
