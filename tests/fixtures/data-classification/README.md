# Fixture provenance

`observed-summary.json` preserves only the two results supplied by the lab owner.
It is an anonymized transcription, not a wire response or a new live test.

`customers-request.json` and `product-info-request.json` transcribe the bodies
from the owner's prior Swagger/test notes, supplied on 2026-10-14. They preserve
string `findQuery`, `pagination.fromIndex`, `pagination.size` and
`track_total_hits`. No credentials, host addresses or environment paths remain.

`reconstructed-response.json` combines the recorded `files`/`total_hits` envelope,
native field names and observed counts into a minimal **reconstructed test
fixture**, not a raw API capture. Its two-record total, fictional paths and
`fixture_repository_id` field/value are synthetic test scaffolding. The native
repository ID field was not established and must be verified separately; never
use this artificial field as a claimed NetApp field. Both categories are now
transcribed from the supplied result screenshots.

Two result screenshots subsequently supplied by the owner corroborate customers
9/0 COMPLETE and product-info 0/0 COMPLETE. The customers screenshot shows HTTP
200 and Total Hits 1, and establishes that `file_name` is a basename while
`remote_file_path` holds the full path. Its actual path is replaced here. The
product-info table shows no full path; its fixture path is entirely synthetic.
Neither screenshot is committed, and no raw JSON export was supplied.

The combined two-file envelope and repository field remain test scaffolding.
Tests construct additional pages and invalid records to exercise pagination,
redaction and fail-closed handling, not to claim fresh live API validation.
