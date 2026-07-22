# Matrix report schema

Output path: `/app/output/matrix_report.json`

Top-level object:

| Field | Type | Notes |
| --- | --- | --- |
| `schema_version` | integer | Current value is `1` |
| `arms` | array | One object per matrix arm |
| `shared_backend_digests` | object | Digests grouped by backend feature |

Each entry in `arms`:

| Field | Type |
| --- | --- |
| `arm_id` | string |
| `mode` | string |
| `build_ok` | boolean |
| `probe_ok` | boolean |
| `digest` | integer or null |
| `tag_p` | string |
| `tag_q` | string |
| `tag_agree` | boolean |

Each entry under `shared_backend_digests` includes `digests` (array), `identical` (boolean), and `arm_ids` (array).
