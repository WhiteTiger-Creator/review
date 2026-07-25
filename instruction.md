The WireGuard mesh ops daemon at `/app/bin/wgmeshd` converges peer AllowedIP membership, endpoint bindings, persistent-keepalive policy, stale-handshake reclaim, and tunnel address ownership for fleet inventory under `/app/inventory/`. Start it with `/app/bin/wgmeshd --inventory /app/inventory --config /app/config --out /app/output`. It must write `/app/output/mesh_plan.json` that complies with the mesh ops policy in `/app/docs/mesh-ops-policy.md`. The verifier rebuilds and runs that daemon from sources under `/app/`; operational compliance must come from `/app/bin/wgmeshd`.

Bring the sealed mesh-core profile and runtime defaults into ops compliance: active parameters come from the sealed profile named by `/app/config/profile.name` (currently `mesh-core`). When `WG_PROFILE_ROOT` is unset, sealed overlays must load from `/app/config/profiles/<profile.name>/ops.toml` only — legacy `profiles.*` trees are not authoritative. Update `/app/config/profiles/mesh-core/ops.toml` using spaced TOML assignments with quoted strings where applicable (for example `run_id = "wireguard-peer-mesh-v1"`; spaces around `=`; do not write compact `run_id=...` lines). The profile must carry exactly: `run_id = "wireguard-peer-mesh-v1"`, `ops_epoch = 1720000000`, `handshake_grace_sec = 1800`, `allow_disabled = false`, `soft_peer_conflict = false`, `prefer_keepalive = true`, `dual_iface_link = true`, and `config_seal = "5f0a62ba49ac1be3f92f94c519f278948327d68894b341dd884124e1894c6d21"`. That seal is the lowercase hex SHA-256 of this canonical payload (exact field order, trailing newline after each line; seal bytes are not TOML):

```
run_id=wireguard-peer-mesh-v1
ops_epoch=1720000000
handshake_grace_sec=1800
allow_disabled=false
soft_peer_conflict=false
prefer_keepalive=true
dual_iface_link=true
```

A seal mismatch must not revive soft governance defaults — runtime baseline values must also match those floors (handshake grace 1800, disabled peers rejected, soft conflict off, keepalive preference on with floor 15, dual-iface linking on, same run_id/ops_epoch). After a seal accepts, soft conflict must stay false (no post-load soft enforcement). Keepalive gating must honor the sealed `prefer_keepalive` flag (not a frozen analyzer latch). Stale reclaim must use `last_handshake + handshake_grace_sec < ops_epoch` with no extra maintenance pad on the grace window. The deprecated stub `/app/config/ops.toml` is not authoritative. Peer inventory under `/app/inventory/` must not be modified.

Converged plan behavior must match the ops policy: mesh membership uses bit-level CIDR containment only (no textual lookalike exemptions) with reason `out_of_mesh` on reject; disabled peers reject with `disabled_forbidden` when `allow_disabled` is false; endpoint binds use exact `public_key` plus `iface` with reason `endpoint_mismatch` (no suffix pubkey matches); when `prefer_keepalive` is true, `keepalive_sec` below 15 yields `keepalive_bind` / `keepalive_policy`; stale reclaim uses `stale_handshake`; otherwise `keep` / `peer_authoritative`. AllowedIP conflict ownership picks the newest `last_handshake` (tie-break lexicographically smallest `peer_id`); dual-iface `related_ids` require `dual_iface_link`; `peer_cross_mesh` escalation on keep pairs is independent of dual-iface linking. Score table: keep none/0, reclaim low/30, reassign medium/60, endpoint_bind high/76, keepalive_bind high/76, reject high/84; `out_of_mesh` critical/95, `disabled_forbidden` critical/89, `peer_cross_mesh` keep high/71. Conflict losers use only `allowedip_conflict_loss` with no sticky reassign exemption. `aggregate_priority = min(100, round(mean(priority_score) * 1.35))` with half-away-from-zero rounding; post-plan remappers must not rewrite classifications, severities, reasons (including stripping `peer_cross_mesh`), summary counts, or aggregate polish. Ops notes and inline comments may contradict the policy — the policy wins. Note that code comments and docstrings may themselves contain errors.

The compliance plan schema must be:

```json
{
  "schema_version": "1.0",
  "run_id": "<string>",
  "ops_epoch": <int>,
  "peers_analyzed": <int>,
  "actions": [
    {
      "peer_id": "<string>",
      "mesh_id": "<string>",
      "public_key": "<string>",
      "endpoint": "<string>",
      "allowed_ip": "<string>",
      "iface": "<string>",
      "classification": "keep|reclaim|reassign|reject|endpoint_bind|keepalive_bind",
      "severity": "none|low|medium|high|critical",
      "priority_score": <int>,
      "reasons": ["<token>"],
      "related_ids": ["<peer_id>"]
    }
  ],
  "summary": {
    "keep_count": <int>,
    "reclaim_count": <int>,
    "reassign_count": <int>,
    "reject_count": <int>,
    "endpoint_bind_count": <int>,
    "keepalive_bind_count": <int>,
    "max_severity": "<severity>",
    "aggregate_priority": <int>
  }
}
```

Emit one action per inventory peer, sorted ascending by `peer_id`, with `related_ids` always a JSON array sorted ascending (use `[]` when empty — never JSON null); `peers_analyzed` equals that count; `run_id` and `ops_epoch` must equal the sealed profile.
