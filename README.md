# Agent Policy Engine MVP

Offline Python 3.10+ lab. No third-party packages are required. The engine evaluates
metadata only; it never reads a requested resource or invokes a model, storage API,
classification API, MCP server, or UI. It does not read credentials or change ACLs.

## Run from the repository root

```powershell
python -m unittest discover -s tests -v
Get-Content examples/request.json -Raw | python -m agent_policy --baseline-demo
```

On POSIX shells: `python -m agent_policy --baseline-demo < examples/request.json`.
The CLI accepts one JSON request through stdin and emits one JSON decision to stdout.
Exit status is 0 for ALLOW, 1 for DENY. Malformed JSON, duplicate keys, and inputs
over 16 KiB produce an INVALID_REQUEST denial. No request file path is opened.

`--baseline-demo` explicitly replays the historical scan using evaluation date
2026-10-02. Without it, the engine uses the current local calendar date and denies
observations more than seven calendar days old (age 7 accepted, age 8 denied).
Future dates also deny. This seven-day window is a **lab choice**, not a product
recommendation. The recorded scan has date precision only. Never refresh its date
to manufacture freshness; collect new evidence for a new baseline.

## Request and decision contracts

Machine-readable contracts: [request](../schemas/request.schema.json) and
[decision](../schemas/decision.schema.json). Runtime validation uses the standard
library; a JSON Schema package is not needed.

All request fields are required strings, at most 256 characters; unknown fields
are rejected. Classification, roles, approval flags, and evaluation time cannot
be supplied in the request.

| Field | Meaning |
|---|---|
| `schema_version` | Exactly `1.0` |
| `request_id` | Caller correlation ID; not an authorization input |
| `agent_id` | Exact lab actor ID: `lab-summary-agent` is approved |
| `resource_path` | Exact UI resource ID, e.g. `/vol1/Project-A/product-info.txt` |
| `action` | Only `summarize` is approved |
| `purpose` | Only `lab_summary` is approved |

Resource IDs are case-sensitive and are not filesystem paths to open. Traversal,
UNC paths, percent encoding, alternate streams, subdirectories and path aliases
are rejected rather than normalized. Unknown but syntactically valid resources deny.
Spelling and casing of actions/purposes must match exactly.

Decisions contain `schema_version`, `policy_version`, `request_id`, `decision`
(`ALLOW` or `DENY`), a stable `reason_code`, a human-readable `reason`, and nullable
`metadata_source` / `observed_on`. Invalid requests have null request IDs; metadata
provenance is included only after validation. No object content or exception text
is returned. Consumers must check `decision`, not merely successful JSON parsing.

## Policy and precedence

Rules run in order; the first failed check returns DENY:

1. Strict request shape, version and canonical resource ID.
2. Exact agent, action and purpose allowlists.
3. Provider availability, metadata presence, type, valid values and exact resource match.
4. Observation freshness (including rejection of future dates).
5. Any Personal or Sensitive Personal detections deny.
6. Explicit resource approval: only the three clean baseline files below.
7. Approved metadata must have Data Subjects = 0 and Category = Miscellaneous Documents.
8. Only passing every check returns EXPLICIT_LAB_ALLOW.

| Baseline file | Personal | Sensitive Personal | Policy result in baseline replay |
|---|---:|---:|---|
| `control-clean.txt` | 0 | 0 | ALLOW |
| `product-info.txt` | 0 | 0 | ALLOW |
| `public-announcement.txt` | 0 | 0 | ALLOW |
| `customers.csv` | 9 | 0 | DENY: PERSONAL_DATA |
| `employees.csv` | 6 | 0 | DENY: PERSONAL_DATA |
| `acquisition-plan.txt` | 0 | 0 | DENY: RESOURCE_NOT_APPROVED |

Zero detections alone never grant access. The acquisition file is deliberately
excluded from the lab resource approval list; the scanner did **not** label it
Confidential. Category and Data Subjects are compared conservatively with approved
baseline values without claiming broader product semantics. Open Permissions is
preserved as evidence and **never grants or denies this application-level use**.

## Metadata provenance and provider boundary

[baseline.json](baseline.json) manually transcribes the six observations from
[the 2026-10-01 UI baseline](../docs/testing/dataset-test-plan.md#baseline-scan--2026-10-01).
It is a mock in a **lab-defined schema**, not an invented NetApp API payload.
Customers has Personal = 9 but only Email Address = 8 was explicitly recorded;
employees has Personal = 6 / Email Address = 6. The remaining customer detection
is not assigned an invented type. Null email breakdown means not recorded.
The source document and screenshots remain unchanged.

`ClassificationProvider.get_metadata(resource_path)` returns immutable `Metadata`,
None for a missing record, or raises on provider failure. The engine sanitizes
exceptions and fails closed. The mock reads only its bundled metadata fixture.
Duplicate matching records, incomplete records, malformed values and mismatched
resource IDs cannot produce an allow. Metadata is validated even for custom providers.

A future live adapter needs verified endpoint/authentication/response evidence,
an explicit mapping, resource identity and freshness validation, timeouts, and
contract tests. This MVP intentionally accepts only `ui-baseline-mock` provenance;
live provenance requires a reviewed contract/policy update, not just swapping in
a network call. No live adapter or credentials are included.

## Trust boundary and limitations

The agent ID and purpose are asserted lab inputs, not authenticated identity or
proof of actual purpose. Anyone can reproduce an allowed lab request. This engine
is an offline decision component, not a deployed enforcement boundary. A future
trusted caller must authenticate the actor, bind task context, enforce the decision
before retrieval, and bind the checked metadata to the exact object/version used.
The frozen synthetic snapshot has no live change detection or content binding.

An ALLOW does not mean a file is generally safe, public, readable under ANF ACLs,
or authorized for other actions. ANF independently enforces storage access.
No retrieval, authentication, redaction, Claude, Streamlit or MCP integration is
implemented. Classification API validation remains a separate pending milestone.

Tests cover all baseline decisions, request spoofing, path aliases, unknown
resources, provider errors, invalid metadata, freshness boundaries, signal
precedence, decision fields, duplicate JSON keys and CLI exit behavior.
