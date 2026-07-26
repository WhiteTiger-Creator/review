# Fleet Rules

This document is normative for hull catalogs, fleet composition, captains, readiness, fuel, and movement legality. Integer arithmetic uses truncating division toward zero for non-negative operands unless a formula says otherwise. Ranges are inclusive.

## Hull catalog

Hull IDs and fixed stats, in this insertion order:

| hull | atk | def | fuel_cap | base_range | upkeep |
| --- | ---: | ---: | ---: | ---: | ---: |
| SCOUT | 4 | 2 | 6 | 3 | 1 |
| FRIGATE | 7 | 5 | 10 | 2 | 2 |
| GALLEON | 11 | 8 | 14 | 2 | 3 |
| FORTRESS | 9 | 14 | 12 | 1 | 4 |

Unknown hull IDs are illegal in scenarios and commands.

## Fleet records

A live fleet has exactly these fields in logical state:

- `id` (string)
- `kingdom` (string)
- `island` (current island id)
- `hulls` (nonempty array of hull IDs; length `1..8`)
- `fuel` (integer `0..sum(fuel_cap of hulls)`)
- `readiness` (integer `0..100`)
- `captain` (captain id or empty string for unassigned)

Fleet attack rating before modifiers:

```text
raw_atk = sum(hull.atk for hull in hulls)
```

Fleet defense rating before modifiers:

```text
raw_def = sum(hull.def for hull in hulls)
```

Fuel capacity:

```text
fuel_cap = sum(hull.fuel_cap for hull in hulls)
```

Base movement range:

```text
base_range = minimum(hull.base_range for hull in hulls)
```

Upkeep per ENDTURN while the fleet exists:

```text
upkeep = sum(hull.upkeep for hull in hulls)
```

## Captains

A captain has `id`, `kingdom`, `command` (integer `0..5`), and `logistics` (integer `0..5`). A fleet may reference at most one captain. A captain may be assigned to at most one fleet. Captain bonuses:

```text
atk_bonus_pct = 2 * captain.command
def_bonus_pct = 2 * captain.command
range_bonus = 1 if captain.logistics >= 3 else 0
fuel_use_discount_pct = 5 * captain.logistics
```

If unassigned, all captain bonuses are zero.

## Readiness

Readiness is an integer `0..100`. Effective combat multipliers use readiness directly. After a successful MOVE, readiness becomes:

```text
readiness = max(0, readiness - 5 * graph_distance)
```

After REFUEL on an owned depot island (see SUPPLY_LOGISTICS.md), readiness becomes `100`. After CLASH, both participating fleets apply combat readiness loss from COMBAT_RULES.md.

## Movement legality

MOVE `<fleet> <island>` is legal only when all of the following hold:

1. The fleet belongs to the player kingdom (or, during NPC doctrine resolution, to the acting kingdom).
2. Destination differs from the current island.
3. The island graph contains a shortest path whose edge count `d` satisfies:

```text
d <= effective_range
effective_range = base_range + range_bonus + tech_range_bonus
```

`tech_range_bonus` is defined in TECHNOLOGY_TREE.md.

4. The fleet has enough fuel for the path cost defined in SUPPLY_LOGISTICS.md and WEATHER_SYSTEM.md.
5. Diplomacy permits entry: destination owner must not be at WAR with the mover unless the destination is unowned (`owner` empty). Entering an ALLIED or PEACE or EMBARGO owned island is allowed; WAR-owned islands are illegal to enter via MOVE (use CLASH instead).
6. Destination stacking limit: after the move, fleets on that island belonging to the same kingdom must be `<= 3`.

On success, the fleet relocates, pays fuel, and applies readiness loss as above. Path cost and fuel payment are defined in SUPPLY_LOGISTICS.md.

## Stacking and presence

Multiple kingdoms may occupy the same island only when diplomacy among every pair of those kingdoms is not WAR. If a MOVE would create a WAR co-occupation, it is illegal. CLASH is the combat entry path onto contested islands.
