# Policy API contract

The verifier controls a localhost-only HTTP policy service. The planner receives
only the base URL through `--policy-url`. Perform real HTTP requests. Do not
read verifier fixtures directly. Do not follow redirects. Do not retry.

## Endpoints

### `GET /v1/policy/manifest?environment=<environment>`

Successful response: HTTP 200, content type `application/json` or
`application/json; charset=utf-8`.

JSON object exactly:

- `policy_revision` (nonempty string)
- `environment` (must match request)
- `fragments` (array of exactly three entries)

Each fragment entry exactly: `fragment_id`, `body_sha256`.

Required fragment IDs: `identity`, `database`, `access`. No duplicates. No
unknown IDs. `body_sha256` is a lowercase 64-character SHA-256.

### Fragment endpoints

- `GET /v1/policy/fragments/identity?environment=<e>&revision=<r>`
- `GET /v1/policy/fragments/database?environment=<e>&revision=<r>`
- `GET /v1/policy/fragments/access?environment=<e>&revision=<r>`

Successful response object exactly: `fragment_id`, `policy_revision`,
`environment`, `document`.

## Digest rule

1. Read the exact response-body bytes.
2. Compute SHA-256 over those exact bytes.
3. Compare lowercase hex with the manifest `body_sha256`.
4. Only then parse JSON.
5. Validate `fragment_id`, `policy_revision`, and `environment`.

The digest covers the complete fragment response body. Do not hash a
reserialized object, only the `document` field, whitespace-normalized JSON, or
sorted keys.

## Request ordering

Request one snapshot per distinct local environment. Process environments in
UTF-8 byte order. Within each environment fetch fragments in order: identity,
database, access. Never fetch the same environment twice per execution.

## Failure behavior

Non-200 status → `policy_api_status_error`. Redirect →
`policy_api_redirect_forbidden`. Wrong content type →
`policy_api_content_type_invalid`. Connection failure →
`policy_api_unavailable`. Timeout → `policy_api_timeout`.

Malformed or mismatched manifests and fragments use the fatal tokens defined in
`bootstrap_policy_profile.md`.
