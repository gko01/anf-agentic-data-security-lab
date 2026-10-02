"""Deterministic deny-by-default lab policy, independent of storage authorization."""

from datetime import date

from .models import Decision, Metadata, Request, ROOT
from .providers import ClassificationProvider


APPROVED_RESOURCES = frozenset(ROOT + name for name in (
    "control-clean.txt", "product-info.txt", "public-announcement.txt"
))

REASONS = {
    "INVALID_REQUEST": "Request does not match the strict lab contract.",
    "AGENT_NOT_ALLOWED": "Agent is not in the lab allowlist.",
    "ACTION_NOT_ALLOWED": "Only summarize is approved.",
    "PURPOSE_NOT_ALLOWED": "Only lab_summary is approved.",
    "PROVIDER_ERROR": "Classification metadata is unavailable.",
    "METADATA_MISSING": "No classification metadata exists for this resource.",
    "METADATA_INVALID": "Classification metadata is invalid or mismatched.",
    "METADATA_FUTURE": "Classification observation is in the future.",
    "METADATA_STALE": "Classification observation exceeds the lab age limit.",
    "PERSONAL_DATA": "Personal or sensitive-personal detections prohibit this use.",
    "RESOURCE_NOT_APPROVED": "Resource has no explicit lab approval for this use.",
    "METADATA_NOT_APPROVED": "Observed metadata does not match the approved baseline.",
    "EXPLICIT_LAB_ALLOW": "Exact agent, action, purpose, resource and metadata checks passed.",
}


class PolicyEngine:
    def __init__(self, provider: ClassificationProvider, *, today: date | None = None,
                 max_age_days: int = 7):
        if type(max_age_days) is not int or max_age_days < 0:
            raise ValueError("max_age_days must be a nonnegative integer")
        if today is not None and type(today) is not date:
            raise ValueError("today must be a date")
        self.provider = provider
        self.today = today
        self.max_age_days = max_age_days

    def evaluate(self, payload: object) -> Decision:
        request = None
        metadata = None

        def result(code: str) -> Decision:
            return Decision(
                request_id=request.request_id if request else None,
                decision="ALLOW" if code == "EXPLICIT_LAB_ALLOW" else "DENY",
                reason_code=code, reason=REASONS[code],
                metadata_source=metadata.source if metadata else None,
                observed_on=metadata.observed_on if metadata else None,
            )

        try:
            request = Request.parse(payload)
        except (ValueError, TypeError):
            return result("INVALID_REQUEST")
        if request.agent_id != "lab-summary-agent":
            return result("AGENT_NOT_ALLOWED")
        if request.action != "summarize":
            return result("ACTION_NOT_ALLOWED")
        if request.purpose != "lab_summary":
            return result("PURPOSE_NOT_ALLOWED")
        try:
            candidate = self.provider.get_metadata(request.resource_path)
            if candidate is None:
                return result("METADATA_MISSING")
            if type(candidate) is not Metadata or not candidate.valid() or (
                candidate.resource_path != request.resource_path
            ):
                return result("METADATA_INVALID")
        except Exception:
            # Fail closed without returning exception text that could contain secrets.
            return result("PROVIDER_ERROR")
        metadata = candidate
        age = ((self.today or date.today()) - date.fromisoformat(metadata.observed_on)).days
        if age < 0:
            return result("METADATA_FUTURE")
        if age > self.max_age_days:
            return result("METADATA_STALE")
        if metadata.personal > 0 or metadata.sensitive_personal > 0:
            return result("PERSONAL_DATA")
        if request.resource_path not in APPROVED_RESOURCES:
            return result("RESOURCE_NOT_APPROVED")
        if metadata.data_subjects != 0 or metadata.category != "Miscellaneous Documents":
            return result("METADATA_NOT_APPROVED")
        return result("EXPLICIT_LAB_ALLOW")
