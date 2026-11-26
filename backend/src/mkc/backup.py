"""`mkc-backup`: dump the database, compress it and upload it off-site (MKC-11.2).

1. A row `running` goes into `backup_runs`.
2. `pg_dump --schema=public --no-owner --no-privileges` (plain SQL) is gzipped into
   MKC_BACKUP_DIR. Only `public`: a full Supabase dump (roles, auth, storage) does not
   restore into a plain Postgres.
3. The file is PUT, with a known Content-Length, to MKC_BACKUP_UPLOAD_URL + the object name
   `nightly/mkc-<UTC time>.sql.gz`. The link is an Object Storage pre-authenticated request
   that can only write objects (decision 49).
4. The row becomes `ok` (object name, size) or `failed` (a short error).

Fails closed: a failed dump never uploads and never records `ok`. A failed status write is
logged and does not stop the backup (the status endpoint then shows it as stale).
The database password and the upload link never appear in argv, logs, rows or errors:
the password goes to pg_dump in PGPASSWORD, and every message passes `_redact`.
Exit code: 0 = uploaded, 1 = failed.
"""

import gzip
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from sqlalchemy import Engine, insert, update
from sqlalchemy.engine import make_url

from mkc.config import Settings, get_settings
from mkc.db.models import BackupRun

log = logging.getLogger("mkc.backup")

PREFIX = "nightly/"
_CHUNK = 1024 * 1024
_UPLOAD_TIMEOUT_SECONDS = 600
_ERROR_LIMIT = 500


class Recorder(Protocol):
    """Where the run's status goes (`backup_runs` in production)."""

    def start(self, started_at: datetime) -> int: ...

    def finish(self, run_id: int, **fields: object) -> None: ...


class DbRecorder:
    """Writes the status to the `backup_runs` table."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def start(self, started_at: datetime) -> int:
        with self._engine.begin() as conn:
            run_id = conn.execute(
                insert(BackupRun)
                .values(started_at=started_at, state="running")
                .returning(BackupRun.id)
            ).scalar_one()
        return int(run_id)

    def finish(self, run_id: int, **fields: object) -> None:
        with self._engine.begin() as conn:
            conn.execute(update(BackupRun).where(BackupRun.id == run_id).values(**fields))


class BackupError(Exception):
    """A step failed; the message is already redacted."""


def object_name(now: datetime) -> str:
    return f"{PREFIX}mkc-{now.astimezone(UTC):%Y%m%dT%H%M%SZ}.sql.gz"


def pg_env(database_url: str) -> dict[str, str]:
    """libpq environment for pg_dump from the SQLAlchemy URL (password not in argv)."""
    url = make_url(database_url)
    env = {
        "PGHOST": url.host or "",
        "PGPORT": str(url.port or 5432),
        "PGUSER": url.username or "",
        "PGPASSWORD": url.password or "",
        "PGDATABASE": url.database or "",
    }
    sslmode = url.query.get("sslmode")
    if isinstance(sslmode, str):
        env["PGSSLMODE"] = sslmode
    return {k: v for k, v in env.items() if v}


def dump_to_file(
    pg_dump: Sequence[str], env: Mapping[str, str], target: Path, redact: Callable[[str], str]
) -> int:
    """Run pg_dump, gzip its output into `target`, return the file size."""
    args = [*pg_dump, "--schema=public", "--no-owner", "--no-privileges"]
    # stderr to a file, not a pipe: a long error output can't block pg_dump.
    with gzip.open(target, "wb") as out, tempfile.TemporaryFile(dir=target.parent) as errors:
        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=errors,
            env={**os.environ, **env},
        )
        assert process.stdout is not None
        shutil.copyfileobj(process.stdout, out, _CHUNK)
        code = process.wait()
        errors.seek(0)
        stderr = errors.read().decode(errors="replace")
    if code != 0:
        last = stderr.strip().splitlines()[-1:] or ["no output"]
        raise BackupError(redact(f"pg_dump exit {code}: {last[0]}"))
    return target.stat().st_size


def upload_file(url: str, path: Path, redact: Callable[[str], str]) -> None:
    """PUT the file with a known length. Errors never carry the link."""
    size = path.stat().st_size
    with path.open("rb") as body:
        request = urllib.request.Request(
            url,
            data=body,
            method="PUT",
            headers={"Content-Length": str(size), "Content-Type": "application/gzip"},
        )
        try:
            with urllib.request.urlopen(request, timeout=_UPLOAD_TIMEOUT_SECONDS) as response:
                status = response.status
        except urllib.error.HTTPError as error:
            raise BackupError(f"upload refused: HTTP {error.code}") from None
        except (urllib.error.URLError, OSError) as error:
            reason = getattr(error, "reason", error)
            raise BackupError(redact(f"upload failed: {type(error).__name__}: {reason}")) from None
    if not 200 <= status < 300:
        raise BackupError(f"upload refused: HTTP {status}")


def _redactor(*secrets: str) -> Callable[[str], str]:
    hidden = [s for s in secrets if s]

    def redact(text: str) -> str:
        for secret in hidden:
            text = text.replace(secret, "***")
        return text[:_ERROR_LIMIT]

    return redact


def _check_link(settings: Settings) -> str:
    link = settings.backup_upload_url.get_secret_value()
    if not link:
        raise BackupError("MKC_BACKUP_UPLOAD_URL is not set")
    scheme = urlsplit(link).scheme
    if scheme != "https" and not (scheme == "http" and settings.backup_allow_http):
        raise BackupError("MKC_BACKUP_UPLOAD_URL must be an https link")
    return link


def run_backup(
    settings: Settings,
    *,
    recorder: Recorder,
    pg_dump: Sequence[str] = ("pg_dump",),
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> bool:
    """One backup run. True when the dump was uploaded."""
    link = settings.backup_upload_url.get_secret_value()
    password = make_url(settings.database_url).password or ""
    redact = _redactor(link, password, urlsplit(link).path)

    started = now()
    run_id: int | None = None
    try:
        run_id = recorder.start(started)
    except Exception as error:
        log.error(
            "backup status not recorded at start: %s", redact(f"{type(error).__name__}: {error}")
        )

    def finish(**fields: object) -> None:
        if run_id is None:
            return
        try:
            recorder.finish(run_id, finished_at=now(), **fields)
        except Exception as error:
            log.error("backup status not recorded: %s", redact(f"{type(error).__name__}: {error}"))

    name = object_name(started)
    work = Path(settings.backup_dir)
    target = work / name.removeprefix(PREFIX)
    try:
        link = _check_link(settings)
        work.mkdir(parents=True, exist_ok=True)
        size = dump_to_file(pg_dump, pg_env(settings.database_url), target, redact)
        upload_file(link + name, target, redact)
    except BackupError as error:
        log.error("backup failed: %s", error)
        finish(state="failed", error=str(error))
        return False
    except Exception as error:
        message = redact(f"{type(error).__name__}: {error}")
        log.error("backup failed: %s", message)
        finish(state="failed", error=message)
        return False
    finally:
        target.unlink(missing_ok=True)

    log.info("backup ok: %s (%d bytes)", name, size)
    finish(state="ok", object_name=name, size_bytes=size, error=None)
    return True


def main() -> int:
    """Entry point `mkc-backup` (the Helm CronJob runs it)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    from mkc.db.session import get_engine

    settings = get_settings()
    ok = run_backup(settings, recorder=DbRecorder(get_engine()))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
