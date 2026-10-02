from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from agent_policy import MockClassificationProvider, PolicyEngine
from agent_policy.models import ROOT

REPO = Path(__file__).resolve().parents[1]
REQUEST = json.loads((REPO / 'examples/request.json').read_text())


class StubProvider:
    def __init__(self, value):
        self.value = value

    def get_metadata(self, path):
        return self.value


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.provider = MockClassificationProvider()
        self.engine = PolicyEngine(self.provider, today=date(2026, 10, 2))
        self.clean = self.provider.get_metadata(REQUEST['resource_path'])

    def assert_denied(self, decision, reason):
        self.assertEqual(decision.decision, 'DENY')
        self.assertEqual(decision.reason_code, reason)

    def test_all_six_baseline_decisions(self):
        for name, reason in {
            'control-clean.txt': 'EXPLICIT_LAB_ALLOW',
            'product-info.txt': 'EXPLICIT_LAB_ALLOW',
            'public-announcement.txt': 'EXPLICIT_LAB_ALLOW',
            'customers.csv': 'PERSONAL_DATA',
            'employees.csv': 'PERSONAL_DATA',
            'acquisition-plan.txt': 'RESOURCE_NOT_APPROVED',
        }.items():
            with self.subTest(name=name):
                result = self.engine.evaluate(dict(REQUEST, resource_path=ROOT + name))
                self.assertEqual(result.reason_code, reason)
                self.assertEqual(result.decision, 'ALLOW' if reason == 'EXPLICIT_LAB_ALLOW' else 'DENY')

    def test_baseline_observations_preserved(self):
        customer = self.provider.get_metadata(ROOT + 'customers.csv')
        self.assertEqual((customer.personal, customer.email_address_detections, customer.data_subjects), (9, 8, 1))
        employee = self.provider.get_metadata(ROOT + 'employees.csv')
        self.assertEqual((employee.personal, employee.email_address_detections), (6, 6))
        acquisition = self.provider.get_metadata(ROOT + 'acquisition-plan.txt')
        self.assertEqual((acquisition.personal, acquisition.sensitive_personal, acquisition.category), (0, 0, 'Services - SOW'))

    def test_invalid_requests_and_spoofed_metadata(self):
        values = [None, [], 'request', {}, dict(REQUEST, personal=0),
                  dict(REQUEST, classification='normal'), dict(REQUEST, schema_version='2.0')]
        for key in REQUEST:
            missing = dict(REQUEST)
            del missing[key]
            values.append(missing)
            values.extend(dict(REQUEST, **{key: v}) for v in (None, 1, True, [], {}, '', ' ', 'x' * 257))
        for value in values:
            with self.subTest(value=value):
                self.assert_denied(self.engine.evaluate(value), 'INVALID_REQUEST')

    def test_path_aliases_traversal_and_suffixes_denied(self):
        for path in [ROOT + '../Project-A/product-info.txt', ROOT + './product-info.txt',
                     ROOT + 'product-info.txt/child', ROOT + 'product-info.txt:stream',
                     ROOT + 'product-info.txt\n', ROOT + 'PRODUCT-INFO.TXT',
                     ROOT + '%70roduct-info.txt', '/vol1/Project-B/product-info.txt',
                     '//vol1/Project-A/product-info.txt', r'\\server\vol1\Project-A\product-info.txt']:
            with self.subTest(path=path):
                self.assert_denied(self.engine.evaluate(dict(REQUEST, resource_path=path)), 'INVALID_REQUEST')

    def test_unapproved_context_does_not_query_provider(self):
        with patch.object(self.provider, 'get_metadata', side_effect=AssertionError) as get:
            for field, reason in [('agent_id', 'AGENT_NOT_ALLOWED'), ('action', 'ACTION_NOT_ALLOWED'),
                                  ('purpose', 'PURPOSE_NOT_ALLOWED')]:
                self.assert_denied(self.engine.evaluate(dict(REQUEST, **{field: 'unknown'})), reason)
            get.assert_not_called()

    def test_missing_and_unknown_resource(self):
        self.assert_denied(self.engine.evaluate(dict(REQUEST, resource_path=ROOT + 'unknown.txt')), 'METADATA_MISSING')
        engine = PolicyEngine(StubProvider(replace(self.clean, resource_path=ROOT + 'unknown.txt')), today=date(2026, 10, 2))
        self.assert_denied(engine.evaluate(dict(REQUEST, resource_path=ROOT + 'unknown.txt')), 'RESOURCE_NOT_APPROVED')

    def test_provider_exception_is_sanitized(self):
        with patch.object(self.provider, 'get_metadata', side_effect=RuntimeError('private-detail')):
            result = self.engine.evaluate(REQUEST)
        self.assert_denied(result, 'PROVIDER_ERROR')
        self.assertNotIn('private-detail', json.dumps(result.to_dict()))

    def test_invalid_metadata(self):
        bad = [False, {}, replace(self.clean, resource_path=ROOT + 'control-clean.txt')]
        for key, values in {
            'personal': [None, -1, True, '0'], 'sensitive_personal': [-1, False, 0.0],
            'data_subjects': [None, -1, True], 'observed_on': ['', '2026-13-01', '20261001', None],
            'source': ['api', None], 'category': ['', None], 'open_permissions': ['', None],
            'email_address_detections': [-1, True, 1, '0'],
        }.items():
            bad.extend(replace(self.clean, **{key: value}) for value in values)
        for metadata in bad:
            with self.subTest(metadata=metadata):
                engine = PolicyEngine(StubProvider(metadata), today=date(2026, 10, 2))
                self.assert_denied(engine.evaluate(REQUEST), 'METADATA_INVALID')

    def test_freshness_boundary_and_future(self):
        for today, reason in [(date(2026, 10, 8), 'EXPLICIT_LAB_ALLOW'),
                              (date(2026, 10, 9), 'METADATA_STALE'),
                              (date(2026, 9, 30), 'METADATA_FUTURE')]:
            self.assertEqual(PolicyEngine(self.provider, today=today).evaluate(REQUEST).reason_code, reason)

    def test_default_clock_is_consulted(self):
        with patch('agent_policy.engine.date') as clock:
            clock.today.return_value = date(2026, 10, 9)
            clock.fromisoformat.side_effect = date.fromisoformat
            self.assert_denied(PolicyEngine(self.provider).evaluate(REQUEST), 'METADATA_STALE')

    def test_sensitive_signals_override_explicit_resource_allowlist(self):
        for field in ['personal', 'sensitive_personal']:
            engine = PolicyEngine(StubProvider(replace(self.clean, **{field: 1})), today=date(2026, 10, 2))
            self.assert_denied(engine.evaluate(REQUEST), 'PERSONAL_DATA')

    def test_ambiguous_category_and_subjects_fail_closed(self):
        for update in [dict(category='Unknown'), dict(data_subjects=1)]:
            engine = PolicyEngine(StubProvider(replace(self.clean, **update)), today=date(2026, 10, 2))
            self.assert_denied(engine.evaluate(REQUEST), 'METADATA_NOT_APPROVED')

    def test_open_permissions_does_not_grant_access(self):
        engine = PolicyEngine(StubProvider(replace(self.clean, open_permissions='Private')), today=date(2026, 10, 2))
        self.assertEqual(engine.evaluate(REQUEST).decision, 'ALLOW')  # application decision only

    def test_corrupt_or_ambiguous_fixture_fails_closed(self):
        for text in ['{', '{}', json.dumps({'records': [self.clean.__dict__, self.clean.__dict__]})]:
            with patch('agent_policy.providers.Path.read_text', return_value=text):
                self.assert_denied(self.engine.evaluate(REQUEST), 'PROVIDER_ERROR')

    def test_decision_contract_fields(self):
        schema = json.loads((REPO / 'schemas/decision.schema.json').read_text())
        for payload in [REQUEST, None, dict(REQUEST, action='export')]:
            result = self.engine.evaluate(payload).to_dict()
            self.assertEqual(set(result), set(schema['required']))
            self.assertIn(result['reason_code'], schema['properties']['reason_code']['enum'])

    def test_bad_age_configuration(self):
        for value in [-1, True, '7', None]:
            with self.assertRaises(ValueError):
                PolicyEngine(self.provider, max_age_days=value)

    def test_cli_json_and_exit_codes(self):
        for raw, code, reason in [(json.dumps(REQUEST), 0, 'EXPLICIT_LAB_ALLOW'),
                                  ('{', 1, 'INVALID_REQUEST'),
                                  ('{"action":"read","action":"summarize"}', 1, 'INVALID_REQUEST'),
                                  ('x' * 16385, 1, 'INVALID_REQUEST'),
                                  (json.dumps(dict(REQUEST, action='export')), 1, 'ACTION_NOT_ALLOWED')]:
            run = subprocess.run([sys.executable, '-m', 'agent_policy', '--baseline-demo'],
                                 input=raw, text=True, capture_output=True, cwd=REPO)
            self.assertEqual(run.returncode, code, run.stderr)
            self.assertEqual(json.loads(run.stdout)['reason_code'], reason)


if __name__ == '__main__':
    unittest.main()
