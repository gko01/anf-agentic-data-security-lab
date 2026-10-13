# NetApp Data Classification REST API v1.56 PowerShell lab

## Evidence and scope

The lab owner reports successful read-only calls to `POST /api/v1.56/search/files`
using `findQuery`, pagination, `Authorization: Bearer <user-access-token>`, and
`x-agent-id`. The following values are the **historical observed results**, not a
new run performed by this change:

| Synthetic file | personal_patterns_count | sensitive_patterns_count | status |
|---|---:|---:|---|
| customers.csv | 9 | 0 | COMPLETE |
| product-info.txt | 0 | 0 | COMPLETE |

The nine is the reported pattern count: do not infer nine unique people or nine
rows. Zero sensitive-personal patterns does not negate personal data. Zero/zero
does not establish that a file is public, nonconfidential, authorized, or safe for
every purpose. `COMPLETE` does not establish freshness.

**Reproduction status: pending instance contract.** The accessible conversation
reference did not contain the successful request body or response envelope.
Consequently, this change does not invent a v1.56 query schema. The reusable
PowerShell transport and validation have been tested offline; their live use
requires the deployed instance's actual query/pagination and field mappings.
The observed summary is separate from the deliberately synthetic test contract.
Do not call this implementation live-verified until the steps below are rerun.

This is classification metadata integration, not an Agent Policy Engine. It
does not read file contents, modify classification, invoke `/actions`, change
ACLs, or return `ALLOW`/`DENY`. The proposed policy layer must evaluate trusted
metadata, identity, action and purpose before retrieval. The separate
[offline policy MVP PR](https://github.com/gko01/anf-agentic-data-security-lab/pull/1)
uses a mock baseline; these changes do not connect it to the live API.

## Authentication without saved credentials

Use PowerShell 7 (`pwsh`) and an account authorized to inspect the intended
repository. For the standard SaaS user-token workflow:

1. Sign in to NetApp's [Refresh Token Generator](https://services.cloud.netapp.com/refresh-token/).
2. Exchange the refresh token with HTTPS `POST https://netapp-cloud-account.auth0.com/oauth/token`.
   The JSON fields are `grant_type: refresh_token`, the privately supplied
   `refresh_token`, and public OAuth `client_id: Mu0V1ywgYteI6w1MbD15fKfVIUrNXGWC`.
   The client ID is not a password or the `x-agent-id` value.
3. Use the returned **`access_token`**, not `id_token` or the refresh token, as the
   Classification bearer token. Respect `expires_in`; exchange again on expiry.

This follows NetApp's [user-token workflow](https://docs.netapp.com/us-en/console-automation/platform/create_user_token.html).
Confirm the authentication environment before using it for a private/restricted
deployment. Never disable TLS validation for the identity provider.

The following optional in-memory exchange avoids a literal secret in command
history. Run it in a private interactive session without transcription, HTTP
tracing, debugging, or screen sharing. It does not write credentials to a file.

```powershell
$refresh = Read-Host 'Refresh token' -AsSecureString
$access = $null
$payload = $null
$reply = $null
try {
    $payload = @{
        grant_type = 'refresh_token'
        client_id = 'Mu0V1ywgYteI6w1MbD15fKfVIUrNXGWC'
        refresh_token = ([pscredential]::new('unused', $refresh)).GetNetworkCredential().Password
    } | ConvertTo-Json -Compress
    try {
        $reply = Invoke-RestMethod -Method Post `
            -Uri 'https://netapp-cloud-account.auth0.com/oauth/token' `
            -ContentType 'application/json' -Body $payload `
            -MaximumRedirection 0 -TimeoutSec 30 -ErrorAction Stop `
            -Verbose:$false -Debug:$false
        if ($reply.token_type -ne 'Bearer' -or
            [string]::IsNullOrWhiteSpace($reply.access_token)) {
            throw 'Invalid token response.'
        }
        $access = ConvertTo-SecureString $reply.access_token -AsPlainText -Force
    } catch { throw 'Token exchange failed; do not publish raw error details.' }
} finally {
    $refresh.Dispose()
    $refresh = $null
    $payload = $null
    $reply = $null
}
# Pass -AccessToken $access to the lab script, then call $access.Dispose().
```

HTTPS/OAuth necessarily handles plaintext in process memory. SecureString and
clearing references reduce accidental exposure; they do not guarantee memory
erasure. PowerShell's in-memory error history and diagnostic tooling can retain
details. Do not publish `$Error`, raw exceptions, request bodies, or responses;
close the private session after use. Never save refresh/access tokens in this
repository, `.env` files, profiles, transcripts, screenshots, or command lines.

## Obtain x-agent-id

Select the Console agent/Connector associated with the Classification deployment
in NetApp Console. Inspect its details/ID. If UI labels differ, inspect a
successful Classification request in your own authenticated browser's Network
panel and copy **only** its `x-agent-id` header value locally. Confirm the selected
deployment and account; do not export a HAR, cookies, authorization headers or a
raw screenshot. Obtain assistance from the deployment administrator if necessary.

Use the full header value exactly as supplied, including a `clients` suffix if
present. Do not derive it from the OAuth client ID, a repository name, or an AI
agent name. NetApp documents its routing meaning in
[Console agents and client identifiers](https://docs.netapp.com/us-en/console-automation/platform/connectors_clients.html).

## Smoke test

NetApp's [Classification API guide](https://docs.netapp.com/us-en/data-services-data-classification/api-classification.html)
documents the deployment's Swagger UI at `/documentation` and the options
endpoint. Open `https://<your-classification-host>/documentation` privately and
select v1.56. The script pins v1.56; it does not silently upgrade/fallback.

From the repository root, substitute your own HTTPS origin and agent ID:

```powershell
./scripts/Test-DataClassificationApi.ps1 `
    -BaseUrl 'https://classification.example.invalid' `
    -AgentId '<your-agent-id>' -SmokeTestOnly
```

It prompts for the **user access token** with hidden input, sends
`GET /api/v1.56/search/options?data_mode=ALL_EXTRACTABLE`, and returns only a smoke
status. A successful response establishes endpoint access, not the files schema
or permission to every repository. No returned options are printed.

Alternatively pass `-AccessToken $access` from the exchange above, or have your
secret manager/CI runner inject a **process-only** environment variable and use
`-TokenEnvironmentVariable NETAPP_CLASSIFICATION_ACCESS_TOKEN`. Do not type a
literal assignment into shell history or persist the environment variable. The
script consumes and clears that process variable immediately, including on
subsequent failure. A parent process's environment cannot be cleared by its child.
Do not provide both token sources. The script disposes tokens it creates; the
caller disposes a supplied SecureString.

TLS certificate/hostname validation is on by default. Prefer installing the
correct lab CA chain. Only for an isolated lab, `-SkipCertificateCheck` opts out
for this script's calls and prints a warning. It weakens server authentication
and can expose the bearer token to interception. It never changes a global TLS
setting. HTTP, URL credentials, base paths, queries, fragments and redirects are
rejected; supply the Classification HTTPS origin, with an optional port.

## Capture the actual request contract, then search

The missing evidence is the successful `findQuery` rule structure, pagination
placement/semantics, response array/total fields, and resource identity fields.
Obtain these from v1.56 Swagger or a successful read-only UI request. Keep values
private. Do not use the offline `synthetic-contract.json` against NetApp.

Create `.local-classification/instance-contract.json` (ignored by Git) with these
adapter configuration entries. The entry names below belong to **this lab**, not
to the NetApp API:

| Entry | Value to copy/derive from the deployed instance |
|---|---|
| `requestTemplate` | Full successful search JSON object, including `findQuery` and pagination fields; no headers or credentials |
| `offsetPointer` | JSON pointer to the existing zero-based item-offset field in the body |
| `limitPointer` | JSON pointer to the existing page-size field in the body |
| `itemsPointer` | JSON pointer to the response's file array |
| `totalPointer` | JSON pointer to the response's exact total result count |
| `pathPointer` | JSON pointer within each file record to its full path |
| `repositoryPointer` | JSON pointer within each record to a stable repository identifier string |
| `statusPointer` | JSON pointer within each record to its classification completion status |

JSON pointers use `/` between object keys (`~1` escapes `/`, `~0` escapes `~`).
Empty pointer selects the root. Array-index traversal is not implemented.
Counts are expected as numeric `personal_patterns_count` and
`sensitive_patterns_count` properties on each file record, as reported by the
owner. If the live schema differs, update the adapter with captured sanitized
evidence and tests before proceeding. Do not silently substitute missing fields.

**Current adapter constraint:** pagination must use zero-based item offset and
limit in the request body and an exact integer total in the response. It advances
by actual returned rows, checks all pages, rejects duplicate identities/changing
totals/truncation, and stops at `MaxPages`. Cursor, page-number, query-string or
approximate-total pagination needs a separately validated adapter. The presence
of this mechanism does not prove these are the deployed v1.56 semantics.

```powershell
./scripts/Test-DataClassificationApi.ps1 `
    -BaseUrl 'https://classification.example.invalid' `
    -AgentId '<your-agent-id>' `
    -ContractPath './.local-classification/instance-contract.json' `
    -ExpectedPath '/synthetic/Project-A/customers.csv' `
    -ExpectedRepository 'synthetic-repository' -PageSize 100 -MaxPages 100
```

Replace the fictional identity values with the exact strings returned by your
instance. Repeat with the product-info query and exact identity. Pass an existing
SecureString to both calls if desired; dispose it afterwards. Search is a
**read-only POST** to `/api/v1.56/search/files`. No content retrieval occurs.

Substring lookup in `findQuery` discovers candidates; it is not an identity or
authorization check. A filename can match backups, subdirectories, and other
repositories. The script requires one exact, case-sensitive ordinal path plus
repository pair across the complete result set. It does not normalize separators,
case, aliases, mount paths or symlinks. If canonicalization is required, implement
and validate it in trusted code. Never select the first substring match.

Only `Lookup`, `ApiVersion`, `status`, and the two counts are emitted. No paths,
repository IDs, owners, SIDs, pattern values or file contents are returned. The
script's output is a diagnostic summary, **not** a production policy input with
freshness or cryptographic resource binding.

## Fail closed and policy boundary

Transport/authentication errors, invalid schema/counts, non-COMPLETE status,
missing exact identity, duplicate records, changed totals, truncated results or
page limits throw terminating errors without emitting partial success. An
unhandled script error yields a nonzero `pwsh -File` exit. Callers must not catch
an error and turn it into clean/zero metadata.

A future Agent Policy Engine must treat missing, stale, ambiguous, unauthorized
or unavailable metadata as `DENY`, independently enforce agent/action/purpose
rules and storage authorization, and prevent content reaching the model before
permission. This diagnostic script has no scan-time/freshness validation and
offset pagination is not a transactional snapshot. Concurrent changes can evade
total/duplicate checks; a production integration needs stronger consistency and
resource version binding. Historical counts alone cannot authorize current data.

Illustrative proposed policy: deny an unapproved request involving customers.csv
personal data; allow product-info.txt only when all identity, action, purpose,
freshness and storage checks pass. Neither result was demonstrated by the
Classification API test. NetApp Classification is not claimed to intercept reads.

## Offline validation and publication checklist

```powershell
pwsh -NoProfile -File tests/Test-DataClassificationApi.ps1
```

The dependency-free suite mocks HTTP, checks request construction, exhausts
multiple pages, verifies exact matching/redaction, and exercises fail-closed
cases. Fixtures contain fictional identities and a minimal transcription of
owner-reported counts. They prove adapter behavior, not API compatibility.

Before marking this lab reproduction verified:

- Supply and independently inspect the sanitized successful v1.56 request and
  response shape; replace the synthetic contract with a clearly attributed,
  sanitized contract fixture and any necessary adapter changes.
- Run options and both exact-file searches against the lab; record version and
  actual test date, and confirm counts/status without inventing a prior run date.
- Review only allowlisted metadata. Remove tokens, refresh tokens, cookies,
  private addresses/hostnames, real usernames/SIDs, repository IDs, absolute
  environment paths and pattern values. Never commit raw responses, HAR files or
  screenshots. Inspect `git diff --cached` before publication.

Existing baseline screenshots elsewhere in the repository are outside this
change; none are added, copied or embedded here.
