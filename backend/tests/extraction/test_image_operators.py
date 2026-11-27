"""MKC-22 fetch hardening (PR #197 finding 7): the built image can call `load_operators()`.

`test_the_image_ships_operators_yaml_where_the_setting_points` (MKC-21) reads the Dockerfile
as text. This test runs the real image instead, so it needs a built image: it runs only when
`MKC_TEST_IMAGE` names one (for example `mkc-backend:smoke`, which `scripts/compose_smoke.sh`
builds) and is skipped otherwise, so a plain `pytest` never builds an image. Wiring it into
CI's `image` job (after the Compose build) is the coordinator's call.
"""

import os
import shutil
import subprocess

import pytest

IMAGE = os.environ.get("MKC_TEST_IMAGE")


@pytest.mark.skipif(not IMAGE, reason="MKC_TEST_IMAGE names no built image")
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")
def test_the_image_loads_the_operator_allow_list() -> None:
    script = (
        "from mkc.extraction.operators import load_operators; "
        "print(' '.join(sorted(load_operators())))"
    )
    done = subprocess.run(
        ["docker", "run", "--rm", "--entrypoint", "python", str(IMAGE), "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "stromnetz-berlin" in done.stdout.split()
