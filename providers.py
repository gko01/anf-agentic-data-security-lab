"""Provider boundary; no credentials, network calls, or object-content reads."""

import json
from pathlib import Path
from typing import Protocol

from .models import Metadata


class ClassificationProvider(Protocol):
    def get_metadata(self, resource_path: str) -> Metadata | None:
        """Return metadata for exactly this ID, None if absent, or raise on failure."""
        ...


class MockClassificationProvider:
    def get_metadata(self, resource_path: str) -> Metadata | None:
        fixture = Path(__file__).with_name("baseline.json")
        data = json.loads(fixture.read_text(encoding="utf-8"))
        matches = [row for row in data["records"] if row["resource_path"] == resource_path]
        if len(matches) > 1:
            raise ValueError("Ambiguous metadata")
        return Metadata(**matches[0]) if matches else None
