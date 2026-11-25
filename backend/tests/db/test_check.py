"""MKC-5.4: `python -m mkc.db.check` reports the server version and pgvector availability."""

import subprocess
import sys

import pytest
from sqlalchemy.engine import URL

from mkc.db.check import main


def test_check_prints_version_and_vector(
    database_env: URL, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main() == 0
    out = capsys.readouterr().out
    assert "PostgreSQL 17" in out
    assert "vector extension: available" in out


def test_check_hides_the_password(database_env: URL, capsys: pytest.CaptureFixture[str]) -> None:
    main()
    out = capsys.readouterr().out
    assert database_env.password
    # The local password ("mkc") also occurs in the database name, so check the userinfo part.
    assert f"{database_env.username}:{database_env.password}@" not in out
    assert f"{database_env.username}:***@" in out


def test_check_fails_cleanly_when_unreachable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:secret-pw@127.0.0.1:1/x")
    assert main() == 1
    captured = capsys.readouterr()
    assert "cannot connect" in captured.err
    assert "secret-pw" not in captured.out + captured.err


def test_module_runs_as_script(database_env: URL) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "mkc.db.check"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "vector extension: available" in result.stdout
