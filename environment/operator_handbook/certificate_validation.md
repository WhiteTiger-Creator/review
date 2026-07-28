# Certificate path validation

Evaluate every PEM under `leaves/` at `eval_time.txt` (RFC3339 UTC).

Trusted anchors: fingerprints in `trusted_roots` of the **remediated** store.
Distrust: the union of remediated fingerprint rows, remediated name rows, and
the cascaded authority set from `authority_cascade.md`. A path member counts as
distrusted when its fingerprint is listed, when its common name is listed, or
when its common name is under cascaded distrust.

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

`tainted_members` is comma-separated fingerprints, ascending, of every member of
the selected path that counts as distrusted by any of the three routes above. It
is populated only when the reason is `revoked`, and is an empty field otherwise
even on a path that happens to contain a tainted member.
`selected_path` is comma-separated fingerprints. `constraint_depth` empty unless
reason is `name_constraint`.
