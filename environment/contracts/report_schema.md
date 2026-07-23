# Matrix report schema

Output path: `/app/output/matrix_report.json`

Top-level object:

| Field | Type | Notes |
| --- | --- | --- |
| `schema_version` | integer | Current value is `1` |
| `arms` | array | One object per matrix arm |
| `shared_backend_digests` | object | Digests grouped by backend feature |

Each entry in `arms`:

| Field | Type | Notes |
| --- | --- | --- |
| `arm_id` | string | |
| `mode` | string | One of `dev`, `release`, `static`, `lto` |
| `build_ok` | boolean | |
| `probe_ok` | boolean | |
| `digest` | integer or null | |
| `tag_p` | string | Probe-exported ABI tag |
| `tag_q` | string | Canonical tag for the arm `mode` |
| `tag_agree` | boolean | Must reflect whether `tag_p` and `tag_q` are the same string |

Successful arms require agreeing tags (`tag_agree` true with identical `tag_p` / `tag_q`). Canonical tags are produced by the workspace tag helpers and the native shim export path for the active arm.

Each entry under `shared_backend_digests` includes `digests` (array), `identical` (boolean), and `arm_ids` (array).
