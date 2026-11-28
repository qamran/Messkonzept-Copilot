"""`MesskonzeptDraft`: one concept as the model sends it to `save_draft` (MKC-23.1, design 7).

The fields are design section 7's Messkonzept without `status`, `approved_by` and
`approved_at`: those belong to the approval (MKC-29), and the model can't set them. Keys
(document hash, concept key) come from the harness, never from the draft (decision 56).
`extra="forbid"` at every level, so an unknown field is refused, not dropped.

The JSON schema for the vision prompt (MKC-26) is exported to `SCHEMA_FILE`; a test checks
that the file equals `model_json_schema()`. After a change to the model, run
`uv run python -m mkc.extraction.draft` to write it again.
"""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictInt

SCHEMA_FILE = Path(__file__).resolve().parents[3] / "prompts" / "messkonzept_draft.schema.json"


def _no_nul(value: str) -> str:
    if "\x00" in value:
        raise ValueError("a NUL character is not allowed")  # Postgres JSONB refuses it
    return value


Text = Annotated[str, Field(min_length=1), AfterValidator(_no_nul)]
"""A non-empty string without NUL."""

Purpose = Literal["Bezug", "Einspeisung", "Zweirichtung", "Erzeugung", "Abgrenzung", "sVE"]
Direction = Literal["Bezug", "Einspeisung"]
ComponentKind = Literal["G", "B", "WR", "SE", "SV", "sVE", "S"]
"""G generator, B battery, WR inverter, SE control unit, SV/sVE, S sensor (section 7)."""


class _Part(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MeterType(_Part):
    """The meter type the operator prints for one power band."""

    band: Text = Field(description="the power band as printed, e.g. '<= 100 kW'")
    type: Text = Field(description="the meter type as printed")


class Meter(_Part):
    label: Text = Field(description="as printed: Z1, Z2, Z3, Zsv ...")
    purpose: Purpose
    directions: list[Direction] = Field(min_length=1)
    upstream: Text | None = Field(
        description="label of the parent meter; null at the grid connection"
    )
    types: list[MeterType] = Field(default_factory=list, description="optional, per power band")


class Component(_Part):
    kind: ComponentKind
    attached_to: Text = Field(description="label of the meter the component hangs on")


class Formula(_Part):
    expression: Text
    provenance: Literal["printed", "derived"] = Field(
        description="printed by the operator, or derived and marked as such"
    )


class Lbs(_Part):
    code: Annotated[str, Field(pattern=r"^[0-9]{13}$", description="13 digits, no spaces")]
    condition: Text | None = Field(
        default=None, description="e.g. 'mit gemessener Erzeugung'; null if none"
    )
    provenance: Literal["stated", "inferred"] = Field(
        description="stated: printed by the operator; inferred: derived, never shown as stated"
    )
    rationale: Text


class Source(_Part):
    document: Text = Field(description="the document hash")
    page: StrictInt = Field(ge=1)


class MesskonzeptDraft(_Part):
    """One Messkonzept as extracted (section 7), before approval."""

    operator: Text
    number: Text = Field(description="the concept number as printed, e.g. '3.2'")
    title: Text
    applications: list[Text]
    meters: list[Meter] = Field(min_length=1)
    components: list[Component]
    formulas: list[Formula] = Field(default_factory=list, description="optional")
    lbs: list[Lbs]
    footnotes: list[Text]
    source: Source


def export_schema(path: Path = SCHEMA_FILE) -> Path:
    """Write `MesskonzeptDraft`'s JSON schema to `path` (UTF-8, indented, one final newline)."""
    import json

    text = json.dumps(MesskonzeptDraft.model_json_schema(), indent=2, ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(export_schema())
