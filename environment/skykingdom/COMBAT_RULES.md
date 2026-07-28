# Combat Rules

This document is normative for CLASH resolution. Combat is deterministic. There is no random draw.

## Clash targets

`CLASH <fleet> <target>` accepts a target that is either:

- an island id occupied by at least one fleet whose kingdom is at WAR with the attacker kingdom, or whose island owner is at WAR with the attacker and no allied/peace defender fleet is present; or
- a fleet id belonging to a kingdom at WAR with the attacker.

If the target is an island, the defender fleet is the WAR-hostile fleet on that island with the highest `raw_def` (tie: lexicographically smallest fleet id). If the island has a hostile owner but no hostile fleet, resolve as a fortification-only defense with a virtual defender score from fortification alone (attacker still spends the clash readiness cost).

The attacker fleet must be on an island adjacent (graph distance 1) to the defender's island when targeting a fleet or island, or on the same island when already co-located through a prior legal state. Same-island clash is legal only when co-occupation exists (which requires non-WAR diplomacy historically) — therefore same-island CLASH is illegal under these rules; attackers must be at distance exactly 1.

## Power pipeline

Compute in this exact order.

1. `raw_atk`, `raw_def` from FLEET_RULES.md for attacker and defender fleets (defender fleet may be absent).
2. Apply captain percent bonuses (FLEET_RULES.md) by:

```text
atk = floor(raw_atk * (100 + atk_bonus_pct) / 100)
def = floor(raw_def * (100 + def_bonus_pct) / 100)
```

3. Apply readiness:

```text
atk = floor(atk * attacker.readiness / 100)
def = floor(def * defender.readiness / 100)   # if no defender fleet, def = 0 before fort
```

4. Apply technology combat percents from TECHNOLOGY_TREE.md to atk and def independently.
5. Apply weather combat multipliers for the defender island's current weather (WEATHER_SYSTEM.md).
6. Apply supply multipliers (SUPPLY_LOGISTICS.md): supplied fleets use `100`; unsupplied use `60`. Fortification-only defense uses owner supply of the island (supplied `100`, else `60`).
7. Add fortification:

```text
fort_bonus = 10 * island.fortification
defender_score = floor(def * weather_def_mul * supply_mul_def / 10000) + fort_bonus
attacker_score = floor(atk * weather_atk_mul * supply_mul_atk / 10000)
```

Weather multipliers are integers in percent (for example CLEAR uses `100`). The formula above divides by `10000` because two percent multipliers are applied.

## Outcome

Let `A = attacker_score` and `D = defender_score`.

- If `A > D`, attacker wins.
- If `A < D`, defender wins.
- If `A == D`, defender wins (defender advantage).

### Attacker win with defender fleet

```text
loss_hulls = min(len(defender.hulls), 1 + floor((A - D) / 15))
```

Remove that many hulls from the end of `defender.hulls`. If no hulls remain, the defender fleet is destroyed and removed from the campaign. Attacker readiness becomes `max(0, readiness - 10)`. Defender readiness (if alive) becomes `max(0, readiness - 25)`.

If the target island's owner is the defender kingdom (or was, when the defending fleet belonged to the owner), ownership transfers to the attacker kingdom and fortification becomes `max(0, fortification - 1)` after transfer (TERRITORY_CONTROL.md).

### Attacker win, fortification-only

Ownership transfers to the attacker. Fortification becomes `max(0, fortification - 1)`. Attacker readiness `max(0, readiness - 8)`.

### Defender win

Attacker loses:

```text
loss_hulls = min(len(attacker.hulls), 1 + floor((D - A) / 20))
```

hulls from the end of `attacker.hulls` (destroy fleet if empty). Attacker readiness `max(0, readiness - 25)`. Defender readiness `max(0, readiness - 10)` when a defender fleet exists.

## Logging fields

A clash result object used by the API contains:

```text
attacker_id, defender_id (empty if fort-only), island_id,
attacker_score, defender_score, winner ("attacker"|"defender"),
attacker_hulls_lost, defender_hulls_lost, ownership_changed (bool)
```
