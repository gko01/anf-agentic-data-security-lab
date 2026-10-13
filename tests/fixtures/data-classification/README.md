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
repository ID field was not supplied and must be verified separately; never use
this artificial field as a claimed NetApp field. The customers category was
reported in the notes; no category is invented for product-info.txt.

The original screenshots and raw response were not supplied. The notes report
successful customers metadata retrieval and propose the product-info test; its
0/0 COMPLETE result comes from the owner's original lab request. Tests construct
additional pages and invalid records from these fixtures to exercise pagination,
redaction and fail-closed handling, not to claim fresh live API validation.
