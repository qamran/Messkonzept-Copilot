"""MKC-21.1 (development agent): where `load_operators` finds `operators.yaml`.

The image installs `mkc` into the venv, so the path next to the source tree does not exist
there. The Dockerfile copies the YAML into the image and points `MKC_OPERATORS_FILE` at it.
"""

import re
from pathlib import Path, PurePosixPath

import pytest

BACKEND = Path(__file__).resolve().parents[2]
DOCKERFILE = BACKEND / "Dockerfile"


def test_load_operators_reads_the_file_named_by_the_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mkc.extraction.operators import load_operators

    path = tmp_path / "ops.yaml"
    path.write_text(
        "operators:\n"
        "  - id: netz-test\n"
        "    name: Netz Test\n"
        "    voltage_level: NS\n"
        "    url: https://netz.example/a.pdf\n"
        "    allowed_hosts: [Netz.Example]\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MKC_OPERATORS_FILE", str(path))
    ops = load_operators()
    assert list(ops) == ["netz-test"]
    assert ops["netz-test"].allowed_hosts == ("netz.example",), "hosts are kept in lower case"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("operators:\n  - id: a\n", "name"),
        (
            "operators:\n  - {id: a, name: A, voltage_level: NS, url: 'http://a.example/x.pdf',"
            " allowed_hosts: [a.example]}\n",
            "https",
        ),
        (
            "operators:\n  - {id: a, name: A, voltage_level: NS, url: 'https://b.example/x.pdf',"
            " allowed_hosts: [a.example]}\n",
            "allowed_hosts",
        ),
        (
            "operators:\n"
            "  - {id: a, name: A, voltage_level: NS, url: 'https://a.example/x.pdf',"
            " allowed_hosts: [a.example]}\n"
            "  - {id: a, name: A, voltage_level: NS, url: 'https://a.example/x.pdf',"
            " allowed_hosts: [a.example]}\n",
            "twice",
        ),
    ],
)
def test_load_operators_refuses_a_bad_file(
    body: str, message: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mkc.extraction.operators import OperatorsFileError, load_operators

    path = tmp_path / "ops.yaml"
    path.write_text(body, encoding="utf-8")
    monkeypatch.setenv("MKC_OPERATORS_FILE", str(path))
    with pytest.raises(OperatorsFileError, match=message):
        load_operators()


def test_the_image_ships_operators_yaml_where_the_setting_points() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    runtime = text.split(" AS runtime", 1)[1]
    workdir = PurePosixPath(re.findall(r"^WORKDIR (\S+)", runtime, re.M)[-1])
    copies = re.findall(r"^COPY (?!--from)(\S+) (\S+)$", runtime, re.M)
    shipped = {workdir / dest for src, dest in copies if src == "data/operators.yaml"}
    env = re.search(r"MKC_OPERATORS_FILE=(\S+)", runtime)
    assert env is not None, "the runtime stage must set MKC_OPERATORS_FILE"
    assert PurePosixPath(env.group(1)) in shipped
