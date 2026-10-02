"""Strict request, metadata, and decision models for the offline policy MVP."""

from dataclasses import dataclass
from datetime import date
from typing import Any


class ValidationError(ValueError):
    """Raised when untrusted request or provider data is invalid."""


REQUEST_FIELDS = frozenset({"agent_id", "action", "purpose", "resource"})
METADATA_FIELDS = frozenset(
    {
        "path",
        "observed_on",
        "personal_count",
        "sensitive_personal_count",
        "data_subjects",
        "category",
        "open_permissions",
        "personal_details",
    }
)


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValidationError(f"{field} must be a non-empty string without surrounding whitespace")
    return value


def _nonnegative_integer(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    return value


@dataclass(frozen=True)
class PolicyRequest:
    agent_id: str
    action: str
    purpose: str
    resource: str

    @classmethod
    def from_value(cls, value: Any) -> "PolicyRequest":
        if not isinstance(value, dict) or set(value) != REQUEST_FIELDS:
            raise ValidationError("request must contain exactly agent_id, action, purpose, and resource")
        return cls(
            agent_id=_nonempty_string(value["agent_id"], "agent_id"),
            action=_nonempty_string(value["action"], "action"),
            purpose=_nonempty_string(value["purpose"], "purpose"),
            resource=_nonempty_string(value["resource"], "resource"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "agent_id": self.agent_id,
            "action": self.action,
            "purpose": self.purpose,
            "resource": self.resource,
        }


@dataclass(frozen=True)
class ClassificationMetadata:
    path: str
    observed_on: date
    personal_count: int
    sensitive_personal_count: int
    data_subjects: int
    category: str
    open_permissions: str
    personal_details: dict[str, int]

    @classmethod
    def from_value(cls, value: Any) -> "ClassificationMetadata":
        if not isinstance(value, dict) or set(value) != METADATA_FIELDS:
            raise ValidationError("metadata must contain exactly the documented mock fields")

        path = _nonempty_string(value["path"], "path")
        observed_text = _nonempty_string(value["observed_on"], "observed_on")
        try:
            observed_on = date.fromisoformat(observed_text)
        except ValueError as exc:
            raise ValidationError("observed_on must be an ISO 8601 date") from exc
        if observed_on.isoformat() != observed_text:
            raise ValidationError("observed_on must use YYYY-MM-DD format")

        details = value["personal_details"]
        if not isinstance(details, dict):
            raise ValidationError("personal_details must be an object")
        parsed_details: dict[str, int] = {}
        for key, count in details.items():
            detail_name = _nonempty_string(key, "personal_details key")
            parsed_details[detail_name] = _nonnegative_integer(
                count, f"personal_details[{detail_name}]"
            )

        return cls(
            path=path,
            observed_on=observed_on,
            personal_count=_nonnegative_integer(value["personal_count"], "personal_count"),
            sensitive_personal_count=_nonnegative_integer(
                value["sensitive_personal_count"], "sensitive_personal_count"
            ),
            data_subjects=_nonnegative_integer(value["data_subjects"], "data_subjects"),
            category=_nonempty_string(value["category"], "category"),
            open_permissions=_nonempty_string(value["open_permissions"], "open_permissions"),
            personal_details=parsed_details,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "observed_on": self.observed_on.isoformat(),
            "personal_count": self.personal_count,
            "sensitive_personal_count": self.sensitive_personal_count,
            "data_subjects": self.data_subjects,
            "category": self.category,
            "open_permissions": self.open_permissions,
            "personal_details": dict(self.personal_details),
        }


@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    reason_code: str
    reason: str
    evaluated_on: date
    request: PolicyRequest | None = None
    classification_metadata: ClassificationMetadata | None = None
    metadata_source: str | None = None
    metadata_is_mock: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "evaluated_on": self.evaluated_on.isoformat(),
            "request": self.request.to_dict() if self.request else None,
            "classification_metadata": (
                self.classification_metadata.to_dict() if self.classification_metadata else None
            ),
            "metadata_source": self.metadata_source,
            "metadata_is_mock": self.metadata_is_mock,
        }
