# Matrix report schema

Output path: `/app/output/matrix_report.json`

Companion per-arm rows: `/app/output/arm_<id>.json` for each documented arm id (same `arm_id`, `mode`, `digest`, `tag_p`, `tag_q`, `tag_agree` fields the probe records).

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
| `digest` | integer or null | Layout fingerprint for the arm |
| `tag_p` | string | Probe-exported ABI tag |
| `tag_q` | string | Documented ABI tag expected for the arm `mode` |
| `tag_agree` | boolean | True only when `tag_p` and `tag_q` are the same string |

Shared-backend arms must publish identical digests. On backend arms a correct digest's high 32 bits equal `native_w`, and the low half is a non-zero mix of that same width. Probe rows may also record companion span fields; those fields are observational. Backend arms keep a 16-byte native cell (`native_w == 16` on non-dev arms).

Documented ABI tags (what both `tag_p` and `tag_q` must equal on a successful arm):

| `mode` | Tag |
| --- | --- |
| `dev` | `dev` |
| `release` | `t4` |
| `static` | `t4` |
| `lto` | `t4` |

`tag_agree` alone is not enough if both sides were rewritten to some other shared string. Successful arms require `tag_p == tag_q` and that shared value equals the documented tag for the arm's `mode`. Do not rename those documented tags or retarget the mode→tag table to paper over a rejecting agreement gate or a mis-emitting native export.

Each entry under `shared_backend_digests` includes `digests` (array), `identical` (boolean), and `arm_ids` (array).
