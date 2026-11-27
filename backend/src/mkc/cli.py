"""The run CLI: `mkc run start|resume|status|inspect` (MKC-20.4, feature 26, decision 60)."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import typer

from mkc.config import Settings
from mkc.models.client import ModelClient

app = typer.Typer(no_args_is_help=True)
run_app = typer.Typer(no_args_is_help=True)
app.add_typer(run_app, name="run")


def make_client(settings: Settings, tracers: Sequence[Any]) -> ModelClient:
    return ModelClient.from_settings(settings, tracers=tracers)


@run_app.command()
def start(items: Path = typer.Option(..., "--items")) -> None:
    pass


@run_app.command()
def resume(run_id: int) -> None:
    pass


@run_app.command()
def status(run_id: int) -> None:
    pass


@run_app.command()
def inspect(run_id: int) -> None:
    pass
