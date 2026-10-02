"""Unit tests for the offline, deny-by-default policy engine."""

import json
import subprocess
import sys
import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

from agent_policy.engine import PolicyEngine
from agent_policy.providers import BaselineJsonProvider, MOCK_SOURCE


ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 10, 2)


class MappingProvider:
    source = MOCK_SOURCE

    def __init__(self, metadata: dict[str, Any] | None) -> None:
        self.metadata = metadata
        self.calls = 0

    def get_metadata(self, resource: str) -> dict[str, Any] | None:
        self.calls += 1
        if self.metadata is None:
            return None
        return deepcopy(self.metadata)


class ErrorProvider:
    source = MOCK_SOURCE

    def get_metadata(self, resource: str) -> dict[str, Any] | None:
        raise OSError("fixture provider unavailable")


class InvalidSourceProvider(MappingProvider):
    source = "unverified-provider"


class BrokenSourceProvider(MappingProvider):
    @property
    def source(self) -> str:
        raise OSError("provider provenance unavailable")


def request_for(filename: str, purpose: str | None = None) -> dict[str, str]:
    purposes = {
        "control-clean.txt": "validate-negative-control",
        "product-info.txt": "summarize-public-product-information",
        "public-announcement.txt": "summarize-public-announcement",
    }
    return {
        "agent_id": "lab-agent",
        "action": "summarize",
        "purpose": purpose or purposes.get(filename, "summarize-public-information"),
        "resource": f"/vol1/Project-A/{filename}",
    }


class PolicyEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = PolicyEngine()
        self.provider = BaselineJsonProvider()

    def evaluate(self, request: dict[str, Any], provider: Any | None = None):
        return self.engine.evaluate(request, provider or self.provider, today=TODAY)

    def test_clean_baseline_files_are_allowed_for_exact_approved_combinations(self) -> None:
        for filename in (
            "control-clean.txt",
            "product-info.txt",
            "public-announcement.txt",
        ):
            with self.subTest(filename=filename):
                result = self.evaluate(request_for(filename))
                self.assertEqual("ALLOW", result.decision)
                self.assertEqual("ALLOW", result.reason_code)
                self.assertTrue(result.metadata_is_mock)
                self.assertEqual(MOCK_SOURCE, result.metadata_source)

    def test_fixture_matches_recorded_ui_baseline_values(self) -> None:
        expected = {
            "control-clean.txt": (0, 0, 0, "Miscellaneous Documents", {}),
            "product-info.txt": (0, 0, 0, "Miscellaneous Documents", {}),
            "public-announcement.txt": (0, 0, 0, "Miscellaneous Documents", {}),
            "customers.csv": (9, 0, 1, "Miscellaneous Spreadsheets", {"Email Address": 8}),
            "employees.csv": (6, 0, 0, "Miscellaneous Spreadsheets", {"Email Address": 6}),
            "acquisition-plan.txt": (0, 0, 0, "Services - SOW", {}),
        }
        for filename, values in expected.items():
            with self.subTest(filename=filename):
                metadata = self.provider.get_metadata(f"/vol1/Project-A/{filename}")
                self.assertIsNotNone(metadata)
                self.assertEqual(
                    values,
                    (
                        metadata["personal_count"],
                        metadata["sensitive_personal_count"],
                        metadata["data_subjects"],
                        metadata["category"],
                        metadata["personal_details"],
                    ),
                )

    def test_customers_employees_and_acquisition_plan_are_denied(self) -> None:
        for filename in ("customers.csv", "employees.csv", "acquisition-plan.txt"):
            with self.subTest(filename=filename):
                result = self.evaluate(request_for(filename))
                self.assertEqual("DENY", result.decision)
                self.assertEqual("REQUEST_NOT_APPROVED", result.reason_code)

    def test_personal_zero_does_not_approve_unlisted_acquisition_plan(self) -> None:
        result = self.evaluate(request_for("acquisition-plan.txt"))
        self.assertEqual("DENY", result.decision)
        self.assertEqual("REQUEST_NOT_APPROVED", result.reason_code)

    def test_nonzero_personal_or_sensitive_personal_denies_even_approved_resource(self) -> None:
        base = self.provider.get_metadata("/vol1/Project-A/product-info.txt")
        self.assertIsNotNone(base)
        for field in ("personal_count", "sensitive_personal_count"):
            metadata = deepcopy(base)
            metadata[field] = 1
            with self.subTest(field=field):
                result = self.evaluate(request_for("product-info.txt"), MappingProvider(metadata))
                self.assertEqual("DENY", result.decision)
                self.assertEqual("CLASSIFICATION_NOT_ALLOWED", result.reason_code)

    def test_non_clean_category_or_data_subject_signal_denies(self) -> None:
        base = self.provider.get_metadata("/vol1/Project-A/product-info.txt")
        changed_values = []
        changed_category = deepcopy(base)
        changed_category["category"] = "Services - SOW"
        changed_values.append(changed_category)
        changed_subjects = deepcopy(base)
        changed_subjects["data_subjects"] = 1
        changed_values.append(changed_subjects)
        changed_details = deepcopy(base)
        changed_details["personal_details"] = {"Email Address": 1}
        changed_values.append(changed_details)

        for metadata in changed_values:
            with self.subTest(metadata=metadata):
                result = self.evaluate(request_for("product-info.txt"), MappingProvider(metadata))
                self.assertEqual(("DENY", "CLASSIFICATION_NOT_ALLOWED"), (result.decision, result.reason_code))

    def test_missing_metadata_denies(self) -> None:
        result = self.evaluate(request_for("product-info.txt"), MappingProvider(None))
        self.assertEqual(("DENY", "METADATA_MISSING"), (result.decision, result.reason_code))

    def test_provider_error_denies(self) -> None:
        result = self.evaluate(request_for("product-info.txt"), ErrorProvider())
        self.assertEqual(("DENY", "PROVIDER_ERROR"), (result.decision, result.reason_code))

    def test_unverified_or_unavailable_provider_provenance_denies(self) -> None:
        metadata = self.provider.get_metadata("/vol1/Project-A/product-info.txt")
        for provider in (InvalidSourceProvider(metadata), BrokenSourceProvider(metadata)):
            with self.subTest(provider=type(provider).__name__):
                result = self.evaluate(request_for("product-info.txt"), provider)
                self.assertEqual(("DENY", "PROVIDER_ERROR"), (result.decision, result.reason_code))

    def test_expired_metadata_denies(self) -> None:
        metadata = self.provider.get_metadata("/vol1/Project-A/product-info.txt")
        metadata["observed_on"] = "2026-09-24"
        result = self.evaluate(request_for("product-info.txt"), MappingProvider(metadata))
        self.assertEqual(("DENY", "METADATA_EXPIRED"), (result.decision, result.reason_code))

    def test_future_dated_metadata_denies(self) -> None:
        metadata = self.provider.get_metadata("/vol1/Project-A/product-info.txt")
        metadata["observed_on"] = "2026-10-03"
        result = self.evaluate(request_for("product-info.txt"), MappingProvider(metadata))
        self.assertEqual(("DENY", "METADATA_EXPIRED"), (result.decision, result.reason_code))

    def test_invalid_metadata_denies(self) -> None:
        base = self.provider.get_metadata("/vol1/Project-A/product-info.txt")
        invalid_values = []
        negative_count = deepcopy(base)
        negative_count["personal_count"] = -1
        invalid_values.append(negative_count)
        boolean_count = deepcopy(base)
        boolean_count["personal_count"] = True
        invalid_values.append(boolean_count)
        extra_field = deepcopy(base)
        extra_field["classification"] = "normal"
        invalid_values.append(extra_field)
        bad_date = deepcopy(base)
        bad_date["observed_on"] = "not-a-date"
        invalid_values.append(bad_date)

        for metadata in invalid_values:
            with self.subTest(metadata=metadata):
                result = self.evaluate(request_for("product-info.txt"), MappingProvider(metadata))
                self.assertEqual(("DENY", "METADATA_INVALID"), (result.decision, result.reason_code))

    def test_metadata_path_mismatch_denies(self) -> None:
        metadata = self.provider.get_metadata("/vol1/Project-A/product-info.txt")
        metadata["path"] = "/vol1/Project-A/public-announcement.txt"
        result = self.evaluate(request_for("product-info.txt"), MappingProvider(metadata))
        self.assertEqual(("DENY", "METADATA_INVALID"), (result.decision, result.reason_code))

    def test_path_bypass_attempts_deny_before_provider_lookup(self) -> None:
        provider = MappingProvider(None)
        for resource in (
            "/vol1/Project-A/../Project-A/product-info.txt",
            "/vol1/Project-A/%2e%2e/product-info.txt",
            r"\vol1\Project-A\product-info.txt",
            "/vol1/Project-A/product-info.txt/",
            "/vol1/Project-A//product-info.txt",
        ):
            request = request_for("product-info.txt")
            request["resource"] = resource
            with self.subTest(resource=resource):
                result = self.evaluate(request, provider)
                self.assertEqual(("DENY", "INVALID_RESOURCE"), (result.decision, result.reason_code))
        self.assertEqual(0, provider.calls)

    def test_request_cannot_spoof_metadata_or_decision_fields(self) -> None:
        request = request_for("product-info.txt")
        request["personal_count"] = "0"
        result = self.evaluate(request)
        self.assertEqual(("DENY", "INVALID_REQUEST"), (result.decision, result.reason_code))

    def test_missing_request_fields_deny(self) -> None:
        request = request_for("product-info.txt")
        del request["purpose"]
        result = self.evaluate(request)
        self.assertEqual(("DENY", "INVALID_REQUEST"), (result.decision, result.reason_code))

    def test_agent_action_and_purpose_must_match_allowlist(self) -> None:
        cases = (
            ("agent_id", "other-agent"),
            ("action", "delete"),
            ("purpose", "general-qa"),
        )
        for field, value in cases:
            request = request_for("product-info.txt")
            request[field] = value
            with self.subTest(field=field):
                result = self.evaluate(request)
                self.assertEqual(("DENY", "REQUEST_NOT_APPROVED"), (result.decision, result.reason_code))

    def test_cli_baseline_demo_emits_allow_json_for_example(self) -> None:
        request_path = ROOT / "examples" / "request.json"
        completed = subprocess.run(
            [sys.executable, "-m", "agent_policy", "--baseline-demo"],
            cwd=ROOT,
            input=request_path.read_text(encoding="utf-8"),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual("ALLOW", output["decision"])
        self.assertTrue(output["metadata_is_mock"])
        self.assertIn("not-api-response", output["metadata_source"])

    def test_schemas_are_valid_json_and_request_is_strict(self) -> None:
        request_schema = json.loads((ROOT / "schemas" / "request.schema.json").read_text(encoding="utf-8"))
        decision_schema = json.loads((ROOT / "schemas" / "decision.schema.json").read_text(encoding="utf-8"))
        self.assertFalse(request_schema["additionalProperties"])
        self.assertFalse(decision_schema["additionalProperties"])
        self.assertEqual(["ALLOW", "DENY"], decision_schema["properties"]["decision"]["enum"])


if __name__ == "__main__":
    unittest.main()
