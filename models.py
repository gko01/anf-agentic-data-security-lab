"""Strict lab contracts. These are not NetApp API payloads."""

from dataclasses import asdict, dataclass
from datetime import date
import re


ROOT = "/vol1/Project-A/"


def valid_path(value: object) -> bool:
    # Exact canonical IDs only: never normalize an untrusted path into an allow.
    return type(value) is str and re.fullmatch(
        r"/vol1/Project-A/[a-z0-9]+(?:-[a-z0-9]+)*\.(?:txt|csv)", value
    ) is not None


@dataclass(frozen=True)
class Request:
    schema_version: str
    request_id: str
    agent_id: str
    action: str
    purpose: str
    resource_path: str

    @classmethod
    def parse(cls, payload: object) -> "Request":
        if type(payload) is not dict or set(payload) != set(cls.__dataclass_fields__):
            raise ValueError("Invalid request fields")
        if any(type(v) is not str or not v.strip() or len(v) > 256 for v in payload.values()):
            raise ValueError("Request fields must be nonempty bounded strings")
        if payload["schema_version"] != "1.0" or not valid_path(payload["resource_path"]):
            raise ValueError("Unsupported version or noncanonical resource")
        return cls(**payload)


@dataclass(frozen=True)
class Metadata:
    resource_path: str
    observed_on: str
    personal: int
    sensitive_personal: int
    data_subjects: int
    category: str
    open_permissions: str
    email_address_detections: int | None
    source: str = "ui-baseline-mock"

    def valid(self) -> bool:
        if not valid_path(self.resource_path) or self.source != "ui-baseline-mock":
            return False
        if any(type(v) is not int or v < 0 for v in (
            self.personal, self.sensitive_personal, self.data_subjects
        )):
            return False
        if self.email_address_detections is not None and (
            type(self.email_address_detections) is not int
            or not 0 <= self.email_address_detections <= self.personal
        ):
            return False
        if any(type(v) is not str or not v.strip() for v in (
            self.observed_on, self.category, self.open_permissions
        )):
            return False
        try:
            return date.fromisoformat(self.observed_on).isoformat() == self.observed_on
        except ValueError:
            return False


@dataclass(frozen=True)
class Decision:
    request_id: str | None
    decision: str
    reason_code: str
    reason: str
    schema_version: str = "1.0"
    policy_version: str = "baseline-lab-v1"
    metadata_source: str | None = None
    observed_on: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
