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

**Evidence recovered:** the owner supplied prior Swagger/test notes on
2026-10-14 containing the request body and code that reads the response fields.
They report successful customers.csv metadata retrieval. The product-info.txt
counts above were supplied separately by the owner in the lab request; the
recovered notes show its test command, not its raw result. The notes reference
screenshots, but no original Swagger images or raw response export were supplied
for this change. This is historical lab evidence, not a fresh live execution.

The script now uses that recorded v1.56 request and response shape directly.
Offline tests check both recorded requests and reconstructed response records.
**Remaining reproduction gap:** the repository identifier field name/type is
absent from the notes. A verified `-RepositoryPointer` is required, with no guessed
default or path-only fallback. The hardened script, multi-page behavior and
repository validation still need a live replay; do not label those live-verified.

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

## Recorded v1.56 request and response

The recovered Swagger-based request for customers.csv is:

```json
{
  "findQuery": "customers.csv",
  "pagination": { "fromIndex": 0, "size": 10 },
  "track_total_hits": true
}
```

For product-info.txt, change only `findQuery` to `"product-info.txt"`. `findQuery`
is a **string**, not a rules object. The client does not add unverified
`query.rules` filters. The request fixtures preserve both recorded bodies.

| Recorded field | Use in this script |
|---|---|
| `pagination.fromIndex` / `pagination.size` | Start at zero; advance by actual returned row count; bound page size |
| `track_total_hits` | Always `true`, requesting an exact total |
| `total_hits` / `files` | Nonnegative integer total and file array |
| `file_name` | Full file path to compare with `ExpectedPath` |
| `personal_patterns_count` / `sensitive_patterns_count` | Nonnegative integer classification counts |
| `ds_extraction_status` | Must equal `COMPLETE`; emitted as diagnostic `status` |

The notes also name `category`, `group_read`, `group_write` and
`ds_last_scanned_time`. These are not required or emitted by this test. Scanner
permission metadata is not an effective SMB/NFS ACL authorization check, and the
timestamp's format/freshness semantics were not supplied. The normalized JSON
object in the notes was explicitly a proposed lab schema, not a native API
response; this implementation does not mistake it for the wire schema.

The script checks all pages, rejects duplicate identities/changing totals/
truncation, and stops at `MaxPages`. The historical example begins at index zero;
multi-page advancement is covered offline and still needs a live test with more
than one page. Object-valued or approximate totals are rejected, not coerced.

## Verify repository identity, then search

Inspect the deployed v1.56 schema or a response privately to identify a stable
repository ID field within each `files` record. The supplied notes do not name
that field. Set `-RepositoryPointer` to its JSON pointer and
`-ExpectedRepository` to the exact expected ID string. Do not use the filename,
file ID, or a human display label as a substitute for repository identity.

Pointers use `/` between object keys (`~1` escapes `/`, `~0` escapes `~`). Only
object-key traversal is supported, not arrays. The selected repository value
must currently be a nonempty string. If the actual ID is numeric or the record
does not include repository identity, obtain the documented mapping and adapt
the validator/tests before use; do not bypass the check. There is no default
repository field, no automatic discovery, and no contract file to configure.

The following example uses an explicit **placeholder** pointer. Replace it,
the fictional path and repository value before running:

```powershell
./scripts/Test-DataClassificationApi.ps1 `
    -BaseUrl 'https://classification.example.invalid' `
    -AgentId '<your-agent-id>' `
    -FindQuery 'customers.csv' `
    -RepositoryPointer '/REPLACE_WITH_VERIFIED_REPOSITORY_ID_FIELD' `
    -ExpectedPath '/synthetic/Project-A/customers.csv' `
    -ExpectedRepository 'synthetic-repository' -PageSize 10 -MaxPages 100
```

Repeat with `-FindQuery 'product-info.txt'` and its exact identity. Pass an existing
SecureString to both calls if desired; dispose it afterwards. Search is a
**read-only POST** to `/api/v1.56/search/files`. No content retrieval occurs.

Substring lookup in `findQuery` discovers candidates; it is not an identity or
authorization check. A filename can match backups, subdirectories, and other
repositories. The script requires one exact, case-sensitive ordinal path plus
repository pair across the complete result set. It does not normalize separators,
case, aliases, mount paths or symlinks. If canonicalization is required, implement
and validate it in trusted code. Never select the first substring match.

The recovered notes explicitly describe a path different from the earlier lab
dataset location. Resolve that discrepancy using the actual returned identity;
do not assume files with the same basename are the same dataset. Environment
paths from the notes have been replaced with fictional paths in public fixtures.

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
cases. Request fixtures come from the recovered transcript. Response fixtures
are reconstructed using the recorded field names and owner-reported counts,
with fictional paths and an explicitly artificial `fixture_repository_id` key.
They are not raw captures and do not establish the native repository field.

Before marking this lab reproduction verified:

- Confirm the native repository ID field/type, then test the exact path/repository
  match. Do not use the artificial fixture field against NetApp.
- Run options and both exact-file searches against the lab; record version and
  actual test date, and confirm counts/status without inventing a prior run date.
- Exercise multiple pages and verify `fromIndex` advancement and exact
  `total_hits` behavior against the deployed version.
- Review only allowlisted metadata. Remove tokens, refresh tokens, cookies,
  private addresses/hostnames, real usernames/SIDs, repository IDs, absolute
  environment paths and pattern values. Never commit raw responses, HAR files or
  screenshots. Inspect `git diff --cached` before publication.

Existing baseline screenshots elsewhere in the repository are outside this
change; none are added, copied or embedded here.
