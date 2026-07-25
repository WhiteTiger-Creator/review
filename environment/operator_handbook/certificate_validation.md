# Certificate path validation

Evaluate every PEM under `leaves/` at `eval_time.txt` (RFC3339 UTC).

Trusted anchors: fingerprints in `trusted_roots` of the **remediated** store.
Distrust: union of remediated fingerprint and name rows.

Enumerate all signature-valid paths to a trusted anchor. Prefer, in order:

1. lowest severity rank: acceptable < not_yet_valid < expired < name_constraint < revoked
2. shortest chain
3. lexicographically smallest comma-separated path fingerprint tuple

| reason | condition |
|--------|-----------|
| `valid` | acceptable path selected |
| `revoked` | distrusted member on path |
| `name_constraint` | shallowest violating CA depth |
| `expired` / `not_yet_valid` | validity window |
| `bad_signature` | issuer name match but no valid signature |
| `no_path` | no anchored path |

Output `certificate_decisions.tsv`:

```
leaf	decision	reason	paths_considered	constraint_depth	tainted_members	selected_path
```

`tainted_members` is comma-separated fingerprints (empty field if none).
`selected_path` is comma-separated fingerprints. `constraint_depth` empty unless
reason is `name_constraint`.
