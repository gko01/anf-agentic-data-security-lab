"""Deny-by-default policy evaluation for the offline Agent Policy Engine MVP."""

from datetime import date
from typing import Any

from .models import ClassificationMetadata, PolicyDecision, PolicyRequest, ValidationError
from .providers import MOCK_SOURCE, ClassificationProvider


ROOT = "/vol1/Project-A/"
MAX_METADATA_AGE_DAYS = 7

_RESOURCE_NAMES = (
    "control-clean.txt",
    "product-info.txt",
    "public-announcement.txt",
    "customers.csv",
    "employees.csv",
    "acquisition-plan.txt",
)
KNOWN_RESOURCES = frozenset(ROOT + name for name in _RESOURCE_NAMES)

APPROVED_COMBINATIONS = frozenset(
    {
        ("lab-agent", "summarize", "validate-negative-control", ROOT + "control-clean.txt"),
        ("lab-agent", "summarize", "summarize-public-product-information", ROOT + "product-info.txt"),
        ("lab-agent", "summarize", "summarize-public-announcement", ROOT + "public-announcement.txt"),
    }
)
APPROVED_CATEGORY = "Miscellaneous Documents"

_REASONS = {
    "ALLOW": "The exact request is approved and fresh baseline metadata is within the lab allow criteria.",
    "INVALID_REQUEST": "Request does not match the strict policy request contract.",
    "INVALID_RESOURCE": "Resource path is not an exact known synthetic dataset path.",
    "REQUEST_NOT_APPROVED": "The agent, action, purpose, and resource combination is not explicitly approved.",
    "PROVIDER_ERROR": "Classification metadata could not be obtained from the configured provider.",
    "METADATA_MISSING": "No classification metadata exists for the requested resource.",
    "METADATA_INVALID": "Classification metadata is invalid or does not match the requested resource.",
    "METADATA_EXPIRED": "Classification metadata is future-dated or older than the allowed freshness window.",
    "CLASSIFICATION_NOT_ALLOWED": "Classification metadata does not match the approved clean-baseline criteria.",
}


class PolicyEngine:
    def __init__(self, max_metadata_age_days: int = MAX_METADATA_AGE_DAYS) -> None:
        if type(max_metadata_age_days) is not int or max_metadata_age_days < 0:
            raise ValueError("max_metadata_age_days must be a non-negative integer")
        self._max_metadata_age_days = max_metadata_age_days

    def _decision(
        self,
        result: str,
        today: date,
        request: PolicyRequest | None = None,
        metadata: ClassificationMetadata | None = None,
        source: str | None = None,
    ) -> PolicyDecision:
        return PolicyDecision(
            decision="ALLOW" if result == "ALLOW" else "DENY",
            reason_code=result,
            reason=_REASONS[result],
            evaluated_on=today,
            request=request,
            classification_metadata=metadata,
            metadata_source=source,
            metadata_is_mock=True,
        )

    def evaluate(
        self,
        request_value: Any,
        provider: ClassificationProvider,
        today: date | None = None,
    ) -> PolicyDecision:
        evaluation_date = today or date.today()
        try:
            request = PolicyRequest.from_value(request_value)
        except ValidationError:
            return self._decision("INVALID_REQUEST", evaluation_date)

        if not _is_exact_known_resource(request.resource):
            return self._decision("INVALID_RESOURCE", evaluation_date, request)

        combination = (request.agent_id, request.action, request.purpose, request.resource)
        if combination not in APPROVED_COMBINATIONS:
            return self._decision("REQUEST_NOT_APPROVED", evaluation_date, request)

        try:
            raw_metadata = provider.get_metadata(request.resource)
            source = provider.source
            if source != MOCK_SOURCE:
                return self._decision("PROVIDER_ERROR", evaluation_date, request)
        except Exception:
            return self._decision("PROVIDER_ERROR", evaluation_date, request)

        if raw_metadata is None:
            return self._decision("METADATA_MISSING", evaluation_date, request)

        try:
            metadata = ClassificationMetadata.from_value(raw_metadata)
        except ValidationError:
            return self._decision("METADATA_INVALID", evaluation_date, request)

        if metadata.path != request.resource:
            return self._decision("METADATA_INVALID", evaluation_date, request, metadata)

        age_days = (evaluation_date - metadata.observed_on).days
        if age_days < 0 or age_days > self._max_metadata_age_days:
            return self._decision("METADATA_EXPIRED", evaluation_date, request, metadata)

        if (
            metadata.personal_count != 0
            or metadata.sensitive_personal_count != 0
            or metadata.data_subjects != 0
            or metadata.category != APPROVED_CATEGORY
            or metadata.personal_details
        ):
            return self._decision(
                "CLASSIFICATION_NOT_ALLOWED",
                evaluation_date,
                request,
                metadata,
                source,
            )

        return self._decision(
            "ALLOW",
            evaluation_date,
            request,
            metadata,
            source,
        )

def _is_exact_known_resource(resource: str) -> bool:
    if not resource.startswith(ROOT) or "\\" in resource or "%" in resource:
        return False
    if any(character in resource for character in ("?", "#", "\x00")):
        return False
    if any(part in {".", "..", ""} for part in resource[len(ROOT) :].split("/")):
        return False
    return resource in KNOWN_RESOURCES
