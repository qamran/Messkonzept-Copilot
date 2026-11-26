"""Record/replay of model replies (MKC-13.4).

The key is a sha256 over canonical JSON of everything that shapes a reply: role, model,
method, messages (image bytes as digests), tools and the structured-output schema. A stored
file holds the reply only, never the request text or images.
"""

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from mkc.models.types import Message, ModelReply, ReplayMiss, Role, ToolSpec

_KEY = re.compile(r"^[0-9a-f]{64}$")


def _message(message: Message) -> dict[str, Any]:
    data = message.model_dump(mode="json", exclude={"images"})
    data["images"] = [
        {"media_type": i.media_type, "sha256": hashlib.sha256(i.data).hexdigest()}
        for i in message.images
    ]
    return data


def replay_key(
    *,
    role: Role,
    model_id: str,
    method: str,
    messages: Sequence[Message],
    tools: Sequence[ToolSpec],
    schema: type[BaseModel] | None,
) -> str:
    payload = {
        "role": role,
        "model_id": model_id,
        "method": method,
        "messages": [_message(m) for m in messages],
        "tools": [
            {"name": t.name, "description": t.description, "args": t.args.model_json_schema()}
            for t in tools
        ],
        "schema": schema.model_json_schema() if schema is not None else None,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ReplayStore:
    """One JSON file per key in a directory."""

    def __init__(self, directory: Path) -> None:
        self._dir = directory

    def _path(self, key: str) -> Path:
        if not _KEY.match(key):
            raise ValueError(f"not a sha256 replay key: {key!r}")
        return self._dir / f"{key}.json"

    def get(self, key: str) -> ModelReply:
        path = self._path(key)
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise ReplayMiss(f"no recorded reply {key} in {self._dir}") from error
        return ModelReply.model_validate_json(text)

    def put(self, key: str, reply: ModelReply) -> None:
        """Write atomically, so a killed process never leaves half a file."""
        path = self._path(key)
        self._dir.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=self._dir, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                file.write(reply.model_dump_json(indent=2))
            os.replace(temp, path)
        except BaseException:
            Path(temp).unlink(missing_ok=True)
            raise
