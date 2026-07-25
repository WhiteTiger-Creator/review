# Fleet Defense Simulation — Scoring Ruleset v2.1

## 1. Overview

The simulation engine processes a topology manifest containing route declarations and scores zone health according to the game rules. The scoring chain has six ordered stages:

1. **Resolution** — resolve each symlink's chain to its terminal target
2. **Classification** — assign a fault class to each entry based on resolution outcome
3. **Propagation** — propagate upstream faults to downstream dependents
4. **Scoring** — compute per-entry health scores using fault-class weights and propagation state
5. **Aggregation** — compute segment aggregates and fleet score
6. **Verdict** — determine per-segment and overall verdicts

Each stage uses outputs from ALL prior stages. The chain is NOT decomposable into independent steps.

---

## 2. Resolution Stage (Stage 1)

### Rule R1: Chain Resolution Order

Symlinks are resolved in **descending priority order** within each segment group. Within the same priority, resolution order follows manifest array order. The resolution order determines which links are considered "upstream" vs "downstream" for propagation (Stage 3).

### Rule R2: Chain Depth Computation

Chain depth for an entry equals the number of hops from its path to the terminal (non-symlink) target. If `path` → `A` → `B` → `terminal`, depth = 3. If `path` → `terminal`, depth = 1. If the target is not in the link map at all, depth = 0 (dangling) or 1 (direct to existing).

### Rule R3: Cycle Detection

A cycle exists when chain resolution revisits a previously-seen path. ALL members of the cycle are flagged — not just the entry where the cycle was detected. Cycle depth is recorded as the number of unique nodes in the cycle ring (e.g., A→B→C→A has cycle_depth=3 for all three entries).

### Rule R4: Terminal Target Recording

For healthy chains, `final_target` is the last path in the chain that has no further symlink mapping. For dangling chains, `final_target` is the unresolvable path. For cycles, `final_target` is the path where the revisit was detected (the "back-edge" target).

### Rule R5: Max Depth Enforcement

If chain resolution exceeds `max_chain_depth` hops WITHOUT finding a terminal or cycle, the entry is classified as "excessive_depth". The recorded chain_depth equals `max_chain_depth + 1` (one beyond the limit).

---

## 3. Classification Stage (Stage 2)

### Rule C1: Fault Classes (Exclusive)

Each entry receives exactly ONE fault class:
- `healthy` — chain resolves to an existing terminal within depth limit
- `dangling` — target_exists=false AND target is not another tracked symlink
- `cycle` — chain resolution detected a revisit (see R3)
- `excessive_depth` — chain exceeded max_chain_depth without terminal/cycle
- `permission_fault` — permissions comparison fails under the configured mask

### Rule C2: Classification Priority

Classification checks are applied in this order: dangling → cycle → excessive_depth → permission_fault → healthy. The FIRST matching condition wins. A dangling entry is never checked for permissions, a cycle entry is never checked for depth, etc.

### Rule C3: Permission Check Scope

Permission comparison applies between an entry and its DIRECT target (one hop only), not the terminal target. If `path` has permissions P1 and its direct target (the first hop) has permissions P2, compare `(P1 & mask) == (P2 & mask)`. The mask comes from the config's `permission_mask` field.

### Rule C4: Dangling Determination

An entry is dangling if and only if: (a) its `target_exists` field is false, AND (b) its target path is NOT present as a `path` in any other manifest entry. Condition (b) is critical — if target is another tracked symlink (even a faulted one), the entry chains through it rather than being dangling.

---

## 4. Propagation Stage (Stage 3)

### Rule P1: Upstream Fault Propagation

When an entry is classified as `cycle` or `dangling`, all entries that transitively point TO it (directly or through chain) receive a **propagation taint**. The taint does NOT change their classification — it affects their score (Stage 4).

### Rule P2: Propagation Taint Types

- `taint_cycle` — entry's chain passes through a cycle-classified entry
- `taint_dangling` — entry's chain passes through a dangling-classified entry
- An entry can have BOTH taints simultaneously
- An entry that IS the fault source also carries its own taint

### Rule P3: Propagation Direction

Propagation follows the FORWARD direction of symlink chains. If A→B→C and C is dangling, then A and B both get `taint_dangling`. But if A→B→C and A is dangling (target_exists=false for A), then ONLY A gets tainted — B and C are not affected because propagation goes forward (from referrer to target), not backward.

### Rule P4: Taint Does Not Cross Segments

Propagation taints do NOT cross segment boundaries. If A (segment 1) → B (segment 2) → C (segment 2) and C is a cycle, then B gets taint_cycle but A does NOT, because A is in a different segment than the fault source C.

### Rule P5: Self-Taint

An entry classified as `cycle` always carries `taint_cycle`. An entry classified as `dangling` always carries `taint_dangling`. This is automatic — they taint themselves.

---

## 5. Scoring Stage (Stage 4)

### Rule S1: Base Scores by Classification

| Fault Class | Base Score |
|---|---|
| healthy | 10.0 |
| dangling | 5.0 |
| cycle | 2.0 |
| excessive_depth | 7.0 |
| permission_fault | 6.0 |

### Rule S2: Taint Penalty Application

Each propagation taint reduces the entry's score:
- `taint_cycle` penalty: -1.5
- `taint_dangling` penalty: -1.0
- Penalties are ADDITIVE — an entry with both taints gets both penalties
- The penalty applies AFTER the base score (base - taint_penalties)
- Score floor is 0.0 — never negative

### Rule S3: Priority Weighting

Each entry's final `health_score` equals: `max(0.0, base_score - taint_penalties) × priority_weight`

The priority_weight is derived from the entry's `priority` field:
- priority 1 → weight 1.0
- priority 2 → weight 0.8
- priority 3 → weight 0.5

### Rule S4: Segment Score Normalization

A segment's `aggregate_score` is computed as:

```
aggregate_score = sum(entry_health_scores) / sum(entry_max_possible_scores)
```

Where `max_possible_score` for an entry = `10.0 × priority_weight` (the theoretical maximum if healthy with no taints).

### Rule S5: Fleet Score

The `fleet_score` is the **weighted** average of segment aggregate_scores, where the weight is the segment's entry count:

```
fleet_score = sum(seg.aggregate_score × seg.entry_count) / sum(seg.entry_count)
```

This weights larger segments more heavily in the fleet assessment.

---

## 6. Verdict Stage (Stage 5)

### Rule V1: Segment Verdict

A segment's verdict is determined by comparing its `aggregate_score` against the `score_threshold` from config:
- aggregate_score >= score_threshold → "healthy"
- aggregate_score < score_threshold AND aggregate_score >= score_threshold × 0.5 → "degraded"
- aggregate_score < score_threshold × 0.5 → "critical"

### Rule V2: Overall Status

The overall_status is the WORST verdict among all segments, using this ordering: critical > degraded > healthy. If ANY segment is critical, overall is critical. If ANY segment is degraded (and none critical), overall is degraded.

### Rule V3: Fleet Score Override

If fleet_score >= score_threshold AND all segments have verdict "healthy", overall_status is "healthy" regardless of other checks. This is the ONLY way to achieve "healthy" overall status — both conditions must hold.

### Rule V4: Critical Count Escalation

If the total count of (dangling + cycle) entries across ALL segments exceeds 4, the overall_status is forcibly set to "critical" regardless of segment verdicts or fleet score. This overrides V2 and V3.

---

## 7. Configuration Contract

The evaluator reads configuration from the config directory:

- `health_config.json` — base configuration (MUST be used as the authoritative source)
- The following fields must appear in `metadata` output: `max_chain_depth`, `permission_mask`, `score_threshold`, `scoring_mode`, `config_source`, `timestamp`
- `config_source` in metadata must reflect the actual file that provided the active configuration values
- `timestamp` must be taken from the manifest's `scan_timestamp` field

---

## 8. Output Schema

The output JSON must have these exact top-level keys:

```json
{
  "summary": {
    "total": <int>,
    "healthy": <int>,
    "dangling": <int>,
    "cycles": <int>,
    "excessive_depth": <int>,
    "permission_fault": <int>,
    "fleet_score": <float>
  },
  "overall_status": "<string>",
  "entries": [
    {
      "path": "<string>",
      "status": "<fault_class>",
      "chain_depth": <int>,
      "final_target": "<string>",
      "segment_group": <int>,
      "health_score": <float>,
      "taints": ["<taint_type>", ...],
      "detail": "<string or empty>"
    }
  ],
  "segments": [
    {
      "id": <int>,
      "name": "<string>",
      "total": <int>,
      "healthy": <int>,
      "unhealthy": <int>,
      "aggregate_score": <float>,
      "verdict": "<string>"
    }
  ],
  "metadata": {
    "max_chain_depth": <int>,
    "permission_mask": <int>,
    "score_threshold": <float>,
    "scoring_mode": "<string>",
    "config_source": "<string>",
    "timestamp": "<string>"
  }
}
```

### Schema Notes:
- `entries` array preserves manifest order (NOT resolution order)
- `segments` array is sorted by segment ID ascending
- `taints` is an array of strings (may be empty for entries with no taint)
- `health_score` is rounded to 2 decimal places
- `aggregate_score` is rounded to 4 decimal places
- `fleet_score` is rounded to 4 decimal places
- Segment `healthy`/`unhealthy` counts reflect classification only (not taint state)
- `detail` is empty string for healthy entries, descriptive for others

---

## 9. Interaction Cross-References

These rules interact in non-obvious ways:

- R1 + P3: Resolution ORDER determines propagation direction. An entry resolved later can only propagate to entries resolved EARLIER if those earlier entries chain forward to it.
- C2 + P1: An entry classified as dangling (which wins over cycle per C2) does NOT propagate cycle taint even if it was part of a cycle candidate before the dangling check preempted.
- P4 + S4: Cross-segment chains don't propagate taints, so a segment's score only reflects its OWN faults — not faults in segments it depends on.
- S3 + S4: Priority weighting affects both numerator and denominator of segment normalization. A priority-3 entry's maximum possible contribution is 5.0, not 10.0.
- V1 + V2 + V4: The "critical count escalation" (V4) can force overall=critical even when ALL segments individually say "healthy" (because V4 counts entries, not segment verdicts).
- S5 + V3: Fleet score is entry-count-weighted, so a large healthy segment can mask a small critical segment in the fleet score. But V2 (worst-verdict) still triggers degraded/critical from that small segment.
