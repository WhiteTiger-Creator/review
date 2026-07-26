# Supply Logistics

This document is normative for depots, supply reachability, fuel payment, refuel, and unsupplied penalties.

## Depots

An island with `depot: true` is a depot. Depots produce fuel income for their owner during the economy phase:

```text
fuel_income = 3 + island.level
```

Non-depot owned islands produce `0` fuel income.

## Resource production

Each owned island also produces aetherium and crystal during economy:

```text
aetherium += island.aetherium_yield
crystal += island.crystal_yield
timber += island.timber_yield
```

Yield fields are non-negative integers from the scenario.

## Supply reachability

A fleet is **supplied** when there exists a path in the island graph from the fleet's island to any depot owned by the fleet's kingdom such that every island on that path (including endpoints) is owned by that kingdom or by a kingdom that is ALLIED with it (DIPLOMACY_RULES.md). Unowned islands break supply. EMBARGO, PEACE, and WAR owners block allied-style transit unless the owner is the fleet kingdom itself.

Graph adjacency ignores weather. Supply uses edge existence only.

## Fuel payment for MOVE

After selecting the unique shortest path described in WEATHER_SYSTEM.md, compute:

```text
raw_cost = sum(edge_cost)
discount_pct = fuel_use_discount_pct + tech_fuel_discount_pct
paid = max(1, floor(raw_cost * (100 - discount_pct) / 100))
```

MOVE requires `fleet.fuel >= paid`. On success `fleet.fuel -= paid`.

## REFUEL

`REFUEL <fleet>` is legal when:

1. The fleet belongs to the acting kingdom.
2. The fleet's island is owned by that kingdom.
3. The island is a depot.
4. The kingdom treasury has `fuel` resource >= missing fuel, where `missing = fuel_cap - fleet.fuel`.

On success, treasury fuel decreases by `missing`, fleet fuel becomes `fuel_cap`, and readiness becomes `100`.

Kingdom treasury field `fuel` is the stockpile (not to be confused with fleet fuel).

## Unsupplied ENDTURN effects

During ENDTURN upkeep, every surviving fleet of every kingdom:

1. Pays upkeep from its kingdom aetherium: if treasury aetherium >= upkeep, subtract upkeep; else readiness becomes `max(0, readiness - 15)` and no aetherium is taken.
2. If the fleet is unsupplied, readiness becomes `max(0, readiness - 10)` after the upkeep step.
3. If supplied and aetherium upkeep succeeded, readiness becomes `min(100, readiness + 2)`.
