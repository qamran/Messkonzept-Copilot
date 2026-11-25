"""One-off connection check: `python -m mkc.db.check`.

Connects to DATABASE_URL, prints the server version and whether the pgvector extension
is available, and exits 0. Exits 1 if the database is unreachable. Read-only: it changes
nothing on the server. The password is never printed.
"""

import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from mkc.config import get_settings

_VECTOR_QUERY = text(
    "SELECT default_version, installed_version FROM pg_available_extensions WHERE name = 'vector'"
)


def main() -> int:
    url = make_url(get_settings().database_url)
    print(f"database: {url.render_as_string(hide_password=True)}")
    engine = create_engine(url, connect_args={"connect_timeout": 10})
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SELECT version()")).scalar_one()
            vector = conn.execute(_VECTOR_QUERY).first()
    except SQLAlchemyError as exc:
        message = str(exc.orig if hasattr(exc, "orig") and exc.orig else exc)
        if url.password:
            message = message.replace(str(url.password), "***")
        print(f"cannot connect: {message.strip()}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    print(f"server: {version}")
    if vector is None:
        print("vector extension: not available")
    else:
        installed = vector.installed_version or "no"
        print(
            f"vector extension: available "
            f"(version {vector.default_version}, installed: {installed})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
