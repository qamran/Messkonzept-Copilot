"""MKC-4.1: health and version endpoints."""

from importlib.metadata import version

import pytest
from fastapi.testclient import TestClient

from mkc.api.app import create_app


def test_health_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_reports_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MKC_COMMIT", "abc1234")
    client = TestClient(create_app())

    response = client.get("/api/version")

    assert response.status_code == 200
    assert response.json() == {"version": version("mkc"), "commit": "abc1234"}


def test_version_commit_defaults_to_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MKC_COMMIT", raising=False)
    client = TestClient(create_app())

    response = client.get("/api/version")

    assert response.json()["commit"] == "dev"
