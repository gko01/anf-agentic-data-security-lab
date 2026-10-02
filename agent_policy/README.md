# Offline Agent Policy Engine MVP

This package is an **offline policy-engine MVP**, not the Data Classification API milestone. It uses only the manually verified 2026-10-01 synthetic dataset UI baseline stored in [`baseline.json`](baseline.json). The fixture and CLI output are explicitly marked as mock data and **must not be represented as an actual API response**.

The MVP does not connect to ANF, NetApp Data Classification, Claude, Streamlit, or MCP. It does not read file contents, modify ACLs, or implement redaction.

## Run

From the repository root, using Python 3.10 or newer:

```powershell
python -m unittest discover -s tests -v
python -m agent_policy --baseline-demo < examples/request.json
```

The CLI reads one strict JSON request from standard input and prints one JSON policy decision. The checked-in example requests summarization of `product-info.txt` and should return `ALLOW` while its mock metadata is fresh. A denied policy decision is a normal CLI result; malformed JSON returns a `DENY` result and a non-zero exit code.

## Request and decision contracts

- [`schemas/request.schema.json`](../schemas/request.schema.json) defines the exact request properties: `agent_id`, `action`, `purpose`, and `resource`. Additional properties are rejected, so requesters cannot provide or spoof classification metadata or a decision.
- [`schemas/decision.schema.json`](../schemas/decision.schema.json) defines `ALLOW`/`DENY`, the reason code, the evaluated request, and optional classification metadata.
- The runtime independently validates the request and provider data. The schemas document the contracts; the Python engine does not require an external JSON Schema package.

## Mock metadata provenance

[`baseline.json`](baseline.json) contains transcribed observations from the 2026-10-01 NetApp Data Classification UI baseline documented in [`docs/testing/dataset-test-plan.md`](../docs/testing/dataset-test-plan.md). Its local field names (`personal_count`, `sensitive_personal_count`, `data_subjects_count`, `category`, `open_permissions`, and `personal_details`) are a lab fixture format, **not claimed API field names or a NetApp JSON schema**. `Data Subjects: 1` is preserved as a value only; no semantics are inferred.

The provider abstraction in [`providers.py`](providers.py) exposes `ClassificationProvider`. The included `BaselineJsonProvider` is local-file only and declares its source as `synthetic-ui-baseline-mock-not-api-response`. It is not an API adapter. The `data_subjects` value preserves the UI's displayed `Data Subjects` value without inferring its meaning. The `open_permissions` value is retained in metadata output for observation but is not used by policy.

Metadata is considered fresh for at most seven calendar days from `observed_on`, inclusive. Missing, malformed, mismatched, future-dated, expired, or unavailable metadata yields `DENY`. The fixed baseline is dated 2026-10-01; after its freshness window the demo intentionally denies until the mock fixture is deliberately refreshed from verified evidence or replaced by a future validated provider.

## MVP policy

The engine denies by default. Only these exact request tuples are approved:

| Agent | Action | Purpose | Resource |
|---|---|---|---|
| `lab-agent` | `summarize` | `validate-negative-control` | `/vol1/Project-A/control-clean.txt` |
| `lab-agent` | `summarize` | `summarize-public-product-information` | `/vol1/Project-A/product-info.txt` |
| `lab-agent` | `summarize` | `summarize-public-announcement` | `/vol1/Project-A/public-announcement.txt` |

The approved resource must also have fresh, path-matched metadata that matches the observed clean baseline: Personal = 0, Sensitive Personal = 0, Data Subjects = 0, no Personal detail entries, and Category = `Miscellaneous Documents`. `Personal = 0` alone never grants access. `Open Permissions` is not a policy input.

`customers.csv`, `employees.csv`, and `acquisition-plan.txt` have no approved request tuple and therefore return `DENY` even though the acquisition-plan baseline has Personal = 0. Unlisted agents, actions, purposes, paths, path traversal/encoding variants, extra request fields, and provider failures are denied.

The seven-day freshness window and approved tuples are **lab policy choices**, not NetApp product features. This MVP is a demonstration, not a production authorization service.

## Provider and API boundary

The provider boundary is intentionally small so a future API-backed provider can be validated separately. No endpoint, authentication flow, request shape, or response schema is invented here. The next integration remains blocked on validating the live NetApp Data Classification Swagger/API contract for `/vol1/Project-A/customers.csv` and comparing its actual fields with the UI baseline.
