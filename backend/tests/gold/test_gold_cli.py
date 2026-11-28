"""MKC-24: `mkc gold split` and `mkc gold draft` on the command line, lane A2.

Pinned interface:

    mkc gold split --keys FILE [--pin-dev KEY ...] --out PATH
        # FILE: a YAML list of concept keys; writes dump_split(split_keys(keys, pinned_dev=...))
    mkc gold draft ...
        # drafts with the `gold_draft` role; its options are the development agent's choice
        # (the role and the stored provenance are pinned in test_gold_draft and test_gold_table)

A refused split (an unknown pinned key) exits 2, names the key and writes nothing.
"""

from pathlib import Path

import yaml
from typer.testing import CliRunner

from mkc.cli import app

runner = CliRunner()
KEYS = [f"stromnetz-berlin:{n}" for n in range(1, 8)] + ["sachsennetze:2-1", "sachsennetze:3-5"]


def _keys_file(tmp_path: Path) -> Path:
    path = tmp_path / "keys.yaml"
    path.write_text(yaml.safe_dump(KEYS), encoding="utf-8")
    return path


def test_gold_split_writes_the_split_file(tmp_path: Path) -> None:
    from mkc.gold.split import dump_split, split_keys

    out = tmp_path / "gold_split.yaml"
    args = ["gold", "split", "--keys", str(_keys_file(tmp_path)), "--out", str(out)]
    result = runner.invoke(app, [*args, "--pin-dev", "stromnetz-berlin:3"])
    assert result.exit_code == 0, result.output
    expected = dump_split(split_keys(KEYS, pinned_dev=["stromnetz-berlin:3"]))
    assert out.read_bytes() == expected.encode("utf-8")


def test_gold_split_twice_gives_the_same_bytes(tmp_path: Path) -> None:
    keys = _keys_file(tmp_path)
    outputs = []
    for name in ("a.yaml", "b.yaml"):
        out = tmp_path / name
        result = runner.invoke(app, ["gold", "split", "--keys", str(keys), "--out", str(out)])
        assert result.exit_code == 0, result.output
        outputs.append(out.read_bytes())
    assert outputs[0] == outputs[1]


def test_gold_split_refuses_an_unknown_pin(tmp_path: Path) -> None:
    out = tmp_path / "gold_split.yaml"
    result = runner.invoke(
        app,
        ["gold", "split", "--keys", str(_keys_file(tmp_path)), "--out", str(out),
         "--pin-dev", "stromnetz-berlin:99"],
    )  # fmt: skip
    assert result.exit_code == 2, result.output
    assert "stromnetz-berlin:99" in result.output
    assert not out.exists()


def test_gold_draft_command_exists() -> None:
    result = runner.invoke(app, ["gold", "draft", "--help"])
    assert result.exit_code == 0, result.output
