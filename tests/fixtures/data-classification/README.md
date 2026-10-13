# Fixture provenance

`observed-summary.json` preserves only the two results supplied by the lab owner.
It is an anonymized transcription, not a wire response or a new live test.

`synthetic-contract.json` is exclusively an offline test contract. Its query,
pagination, envelope, path and repository keys are invented for exercising the
adapter. **Do not send it to NetApp.** It does not establish the v1.56 wire schema.
Tests construct synthetic pages using these keys and the observed counts. All
paths and repository names in tests are fictional. Obtain the real contract from
the deployed instance before running a live search; see the deployment guide.
