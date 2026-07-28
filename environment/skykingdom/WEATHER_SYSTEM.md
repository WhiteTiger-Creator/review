# Weather System

This document is normative for weather states, schedules, movement cost modifiers, and combat multipliers.

## Weather IDs

Exact set, in catalog order:

`CLEAR`, `THERMAL`, `FOG`, `GALE`, `STORM`

## Schedule

Scenario field `weather_schedule` is an array of length `max_turns`. Each entry is an object mapping every island id in the scenario to a weather ID. Turn `t` (1-indexed campaign turn after creation uses schedule index `t-1`, clamped to the last entry if a doctrine step would overflow) selects the mapping for all islands.

At game creation, `turn` is `1` and current weather for each island is `weather_schedule[0][island]`.

On successful ENDTURN, after economy and NPC doctrine but before victory checks, the campaign increments `turn` by 1 and then refreshes island weather from `weather_schedule[min(turn-1, len-1)]`.

## Movement multipliers

Path edge costs multiply the base cost `1` by the weather of the **destination** vertex of that edge:

| weather | move_mul_pct |
| --- | ---: |
| CLEAR | 100 |
| THERMAL | 80 |
| FOG | 120 |
| GALE | 150 |
| STORM | 200 |

An edge contribution is:

```text
edge_cost = ceil(100 * move_mul_pct / 10000)   # equivalent: ceil(move_mul_pct / 100)
```

Because base edge weight is 1, `edge_cost = ceil(move_mul_pct / 100)` using integer ceil for positive integers: `(move_mul_pct + 99) / 100`.

Total path fuel cost before discounts is the sum of edge_cost along the shortest path (fewest edges). If multiple shortest paths exist, choose the lexicographically smallest sequence of island ids among all minimum-edge paths (compare the full path including origin and destination as id lists).

## Combat multipliers

Applied on the defender island's weather:

| weather | atk_mul_pct | def_mul_pct |
| --- | ---: | ---: |
| CLEAR | 100 | 100 |
| THERMAL | 110 | 90 |
| FOG | 85 | 115 |
| GALE | 95 | 95 |
| STORM | 75 | 125 |

## Illegal weather

Any weather string outside the catalog is a scenario validation error.
