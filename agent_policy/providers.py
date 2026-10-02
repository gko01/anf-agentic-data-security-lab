"""Classification metadata provider interfaces and the offline baseline fixture."""

import json
from pathlib import Path
from typing import Any, Protocol


MOCK_SOURCE = "synthetic-ui-baseline-mock-not-api-response"
FIXTURE_TYPE = "synthetic-ui-baseline-mock-not-api-response"


class ClassificationProvider(Protocol):
    @property
    def source(self) -> str: ...

    def get_metadata(self, resource: str) -> dict[str, Any] | None: ...


class BaselineJsonProvider:
    """Read manually observed UI baseline values; this is not an API client."""

    source = MOCK_SOURCE

    def __init__(self, fixture_path: str | Path | None = None) -> None:
        self._fixture_path = Path(fixture_path) if fixture_path else Path(__file__).with_name("baseline.json")
        self._records: dict[str, dict[str, Any]] | None = None

    def _load_records(self) -> dict[str, dict[str, Any]]:
        with self._fixture_path.open("r", encoding="utf-8") as fixture_file:
            document = json.load(fixture_file)

        if not isinstance(document, dict) or set(document) != {"fixture_type", "notice", "records"}:
            raise ValueError("baseline fixture has an invalid top-level structure")
        if document["fixture_type"] != FIXTURE_TYPE:
            raise ValueError("baseline fixture is not marked as synthetic mock metadata")
        if not isinstance(document["notice"], str) or not document["notice"].strip():
            raise ValueError("baseline fixture is missing its provenance notice")
        if not isinstance(document["records"], list):
            raise ValueError("baseline fixture records must be an array")

        records: dict[str, dict[str, Any]] = {}
        for record in document["records"]:
            if not isinstance(record, dict) or not isinstance(record.get("path"), str):
                raise ValueError("baseline fixture contains a malformed record")
            if record["path"] in records:
                raise ValueError("baseline fixture contains duplicate resource paths")
            records[record["path"]] = record
        return records

    def get_metadata(self, resource: str) -> dict[str, Any] | None:
        if self._records is None:
            self._records = self._load_records()
        record = self._records.get(resource)
        return dict(record) if record is not None else None
