# WireGuard Mesh Ops Policy

Operational policy for the WireGuard mesh ops daemon across multi-mesh AllowedIP domains. The daemon must emit a deterministic mesh action plan that converges mesh CIDR membership, endpoint bindings, keepalive policy, stale handshake reclaim, and AllowedIP conflict ownership to this policy.

## 1. Inventory inputs

- Peer records: `/app/inventory/peers/*.json` (opaque filenames). Each object has:
  - `peer_id` (string)
  - `mesh_id` (string)
  - `public_key` (string)
  - `endpoint` (string, host:port as stored)
  - `allowed_ip` (string, dotted IPv4 as stored)
  - `iface` (string, WireGuard interface name)
  - `keepalive_sec` (int)
  - `last_handshake` (unix seconds)
  - `state` (`active`|`disabled`)
  - `family` (`4`)
- Mesh nets: `/app/inventory/meshes/m01.json` field `nets` lists `{mesh_id, cidr}`.
- Endpoint bindings: `/app/inventory/endpoints/e01.json` field `endpoints` lists `{public_key, iface, endpoint}`.

Inventory files must not be modified.

## 2. Ops clock and sealed profile

`ops_epoch` (T0) is the sole reference clock. Corpus default T0 is `1720000000`.
`run_id` corpus default is `wireguard-peer-mesh-v1`.

Active parameters must come from the sealed profile named by `/app/config/profile.name` (currently `mesh-core`). Profile path when `WG_PROFILE_ROOT` is unset:

`/app/config/profiles/{profile.name}/ops.toml`

Legacy trees such as `/app/config/profiles.legacy/` are not authoritative. `WG_PROFILE_ROOT`, when set, replaces the profiles directory root.

Contract sealed parameters (section 14 table):

| field | value |
|-------|-------|
| run_id | `wireguard-peer-mesh-v1` |
| ops_epoch | `1720000000` |
| handshake_grace_sec | `1800` |
| allow_disabled | `false` |
| soft_peer_conflict | `false` |
| prefer_keepalive | `true` |
| dual_iface_link | `true` |

`config_seal` must be the lowercase hex SHA-256 of this canonical payload (exact field order, trailing newline after each line):

```
run_id=<run_id>
ops_epoch=<ops_epoch>
handshake_grace_sec=<handshake_grace_sec>
allow_disabled=<true|false>
soft_peer_conflict=<true|false>
prefer_keepalive=<true|false>
dual_iface_link=<true|false>
```

If the profile overlay is absent or `config_seal` does not match, governance baseline defaults apply. Governance baseline values in code must also match this table — a seal mismatch is not permission to keep soft/legacy ops defaults. After a seal accepts, `soft_peer_conflict` must remain as sealed (no post-load soft enforcement). The deprecated stub `/app/config/ops.toml` is not authoritative.

## 3. Mesh CIDR membership gate

A peer is mesh-valid iff its `allowed_ip` is contained in the CIDR of the net whose `mesh_id` equals the peer `mesh_id`. Containment must use proper IP/CIDR bit masking. String prefix checks on textual addresses are forbidden.

If mesh membership fails, classify `reject` with reason `out_of_mesh` and stop further classification for that peer (still compute `related_ids` later).

## 4. Disabled-state gate

If `state == "disabled"` and `allow_disabled == false`, classify `reject` with reason `disabled_forbidden` and stop (unless already `reject` from section 3 — then keep `out_of_mesh` as the sole reason).

If `allow_disabled == true`, disabled peers are not rejected solely for state. Compliant builds keep `allow_disabled = false`.

## 5. Endpoint bind gate

Look up endpoint bindings by exact `public_key` equality and matching `iface`. Substring / suffix pubkey matches are forbidden.

If a binding exists for the peer's `public_key` + `iface` and `peer.endpoint != binding.endpoint`, classify `endpoint_bind` with reason `endpoint_mismatch` and stop.

Empty `public_key` never matches a binding.

## 6. Keepalive policy gate

If `prefer_keepalive == true` and `keepalive_sec < 15`, classify `keepalive_bind` with reason `keepalive_policy` and stop. The sealed `prefer_keepalive` flag must drive this gate (frozen analyzer latches that ignore the seal are not compliant).

Compliant builds keep `prefer_keepalive = true` and keepalive floor `15` (not a 25s fleet default).

## 7. Stale handshake reclaim gate

A peer is stale iff `last_handshake + handshake_grace_sec < ops_epoch`. No maintenance/calendar pad may be added to `handshake_grace_sec` for this comparison.

If stale and not already classified by sections 3-6, classify `reclaim` with reason `stale_handshake` and stop.

`state == "disabled"` does not by itself force reclaim when allow_disabled is true; only the timestamp rule above applies for reclaim.

## 8. Tentative keep

If sections 3-7 did not classify the peer, tentative classification is `keep` with reason `peer_authoritative`.

## 9. AllowedIP conflict ownership

Consider the set of peers that share the same `allowed_ip` and whose classification after sections 3-8 is `keep`, `endpoint_bind`, or `keepalive_bind`. (Rejected and reclaimed peers do not compete.)

If the set size is <= 1, no conflict action.

If size >= 2 and `soft_peer_conflict == true`, leave classifications unchanged and append reason `soft_peer_deferred` (compliant builds never enable this).

If size >= 2 and `soft_peer_conflict == false`:

Winner selection:

1. Newest `last_handshake` wins (oldest-handshake stability bias is forbidden).
2. Tie-break: lexicographically smallest `peer_id` wins.

All non-winners are reclassified to `reassign` with sole reason `allowedip_conflict_loss` (prior reasons replaced).

There is no sticky / lexicographic-first exemption that restores a loser to `keep`.

## 10. Related IDs and cross-mesh escalation

`related_ids` is the sorted unique list of other `peer_id` values linked as follows. When no peers qualify, encode JSON `[]` (never `null`):

- If `dual_iface_link == true`, include every other peer with the same `public_key` and a different `iface`.
- Independently of `dual_iface_link`, when classification is `keep` and another `keep` peer shares the same non-empty `public_key` on a different `mesh_id`, include that peer_id and append reason `peer_cross_mesh` (do not replace existing reasons). Suppressing `peer_cross_mesh` while dual-iface linking is enabled is forbidden.

Compliant builds keep `dual_iface_link = true`.

## 11. Severity and priority scores

Base mapping:

| classification | severity | priority_score |
|----------------|----------|----------------|
| keep | none | 0 |
| reclaim | low | 30 |
| reassign | medium | 60 |
| endpoint_bind | high | 76 |
| keepalive_bind | high | 76 |
| reject | high | 84 |

Overrides (applied after base mapping):

- reason `out_of_mesh` on `reject` → severity `critical`, score `95`
- reason `disabled_forbidden` on `reject` → severity `critical`, score `89`
- reason `peer_cross_mesh` on `keep` → severity `high`, score `71`

## 12. Summary aggregates

Count each classification into `keep_count`, `reclaim_count`, `reassign_count`, `reject_count`, `endpoint_bind_count`, `keepalive_bind_count`.

`max_severity` is the highest severity among actions using rank none < low < medium < high < critical.

## 13. Aggregate priority formula

`aggregate_priority = min(100, round(mean(priority_score) * 1.35))` where `mean` is the arithmetic mean over all actions and `round` is half-away-from-zero / Go `math.Round` semantics.

Unweighted mean without the 1.35 surcharge is forbidden.

## 14. Sealed profile table

See section 2 table. Profile file `/app/config/profiles/mesh-core/ops.toml` must contain every field plus a matching `config_seal`.

## 15. Deprecated stub

`/app/config/ops.toml` is a non-authoritative leftover and must be ignored by the loader.

## 16. Post-plan reconciliation

After scoring, no legacy remapper may downgrade `critical` rejects, flatten `endpoint_bind`/`keepalive_bind` into `keep`, strip `peer_cross_mesh`, rewrite reasons, recount summary classes, or recompute `aggregate_priority` without the 1.35 surcharge. Post-score NOC compatibility remapping is forbidden for compliant builds.
