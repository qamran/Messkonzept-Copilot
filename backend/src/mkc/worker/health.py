"""`mkc-worker-health`: exit 0 if the worker's heartbeat file is fresh, else 1.

The worker has no HTTP port; its Kubernetes probes run this command (MKC-9).
"""

import sys
import time
from pathlib import Path

from mkc.config import get_settings


def is_fresh(heartbeat: Path, max_age_seconds: float) -> bool:
    """True if the file exists and was touched within `max_age_seconds`."""
    try:
        age = time.time() - heartbeat.stat().st_mtime
    except OSError:
        return False
    return age <= max_age_seconds


def main() -> int:
    settings = get_settings()
    if not settings.worker_heartbeat_file:
        print("MKC_WORKER_HEARTBEAT_FILE is not set", file=sys.stderr)
        return 1
    heartbeat = Path(settings.worker_heartbeat_file)
    if not is_fresh(heartbeat, settings.worker_heartbeat_max_age_seconds):
        print(
            f"heartbeat {heartbeat} missing or older than "
            f"{settings.worker_heartbeat_max_age_seconds} s",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
