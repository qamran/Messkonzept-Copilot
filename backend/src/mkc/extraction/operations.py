"""`fetch_document` and `segment_document` as run-level operations (MKC-21.5, design 8.1),
and `extract_text` and `extract_tables` as item tools (MKC-22.3).

Harness code calls the run-level operations through the registry in the `run` context, so
they get its argument validation, error results and tracing; the model never sees them. The
item tools read the PDF from the store by the item's document hash (`ToolEnv`), never by a
model argument, and return plain JSON, which the tool cache stores (decision 56).
`default_registry` makes all four real when it gets a `DocumentOps`.
"""

from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from mkc.extraction.fetch import Getter, document_by_hash, fetch_document, http_get
from mkc.extraction.operators import OperatorConfig
from mkc.extraction.segment import segment_document
from mkc.extraction.tables import extract_tables
from mkc.extraction.text import read_page
from mkc.harness.blobs import PREFIX, BlobStore
from mkc.harness.tools import ToolEnv


class UnknownDocument(LookupError):
    """No fetched edition has this document hash."""


class DocumentOps:
    """What the two operations need: the database, the blob store, and (for tests) the
    getter and the operator list."""

    def __init__(
        self,
        sessions: sessionmaker[Session],
        store: BlobStore,
        *,
        get: Getter = http_get,
        operators: dict[str, OperatorConfig] | None = None,
    ) -> None:
        self.sessions = sessions
        self.store = store
        self.get = get
        self.operators = operators

    def fetch(self, args: BaseModel, env: ToolEnv) -> dict[str, Any]:
        doc = fetch_document(
            str(args.model_dump()["operator_id"]), sessions=self.sessions, store=self.store,
            get=self.get, operators=self.operators,
        )  # fmt: skip
        return {
            "operator_id": doc.operator_id,
            "url": doc.url,
            "sha256": doc.sha256,
            "fetched_at": doc.fetched_at.isoformat(),
            "page_count": doc.page_count,
            "edition": doc.edition,
            "new_edition": doc.new_edition,
        }

    def segment(self, args: BaseModel, env: ToolEnv) -> dict[str, Any]:
        sha256 = str(args.model_dump()["document_hash"])
        with self.sessions() as session:
            doc = document_by_hash(session, sha256)
        if doc is None:
            raise UnknownDocument(f"no fetched document with hash {sha256}")
        regions = segment_document(doc, store=self.store)
        return {
            "operator_id": doc.operator_id,
            "edition": doc.edition,
            "regions": [
                {"page": r.page, "bbox": list(r.bbox), "number_hint": r.number_hint}
                for r in regions
            ],
        }

    def extract_text(self, args: BaseModel, env: ToolEnv) -> dict[str, Any]:
        values = args.model_dump()
        fields = read_page(self._pdf(env), int(values["page"]), values.get("bbox"))
        return fields.model_dump(mode="json")

    def extract_tables(self, args: BaseModel, env: ToolEnv) -> list[dict[str, Any]]:
        rows = extract_tables(self._pdf(env), args.model_dump()["kind"])
        return [r.model_dump(mode="json") for r in rows]

    def _pdf(self, env: ToolEnv) -> bytes:
        if env.document_hash is None:
            raise UnknownDocument("the item has no document hash")
        return self.store.get(PREFIX + env.document_hash)
