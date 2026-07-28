# Scenario Schema

Scenario files are strict JSON objects. Unknown or missing fields are invalid at every level. Numbers must be finite integers. Ranges are inclusive. An ordinary object is a non-null JSON object.

## Root

Exact fields:

- `id`: string matching `[A-Za-z0-9_-]+`
- `name`: nonempty string
- `player_kingdom`: kingdom id present in `kingdoms`
- `max_turns`: integer `5..60`
- `victory`: object with exact fields `kind` (`islands`|`crystal`|`elimination`) and `threshold` (integer `1..1000`)
- `kingdoms`: array length `2..6`
- `islands`: array length `3..20`
- `edges`: array length `2..60`
- `fleets`: array length `1..20`
- `captains`: array length `0..20`
- `diplomacy`: array length `0..20`
- `weather_schedule`: array length exactly `max_turns`

## Kingdoms

Each kingdom has exact fields:

- `id`: `[A-Za-z0-9_-]+`, unique
- `name`: nonempty string
- `aetherium`, `crystal`, `timber`, `fuel`: integers `0..10000`
- `researched`: array of unique tech catalog ids (may be empty)

## Islands

Each island has exact fields:

- `id`: unique `[A-Za-z0-9_-]+`
- `name`: nonempty string
- `owner`: kingdom id or `""`
- `fortification`: `0..5`
- `depot`: boolean
- `level`: `1..5`
- `aetherium_yield`, `crystal_yield`, `timber_yield`: `0..20`

## Edges

Each edge has exact fields `a` and `b`, island ids, `a != b`. Undirected; duplicate undirected pairs are illegal. Self-loops (`a == b`) are illegal.

**Connectivity (required):** Treat islands as undirected graph vertices and edges as undirected links. `validateScenario` must reject the scenario unless every island is reachable from every other island by a path of edges. Two or more islands with no bridging path (a disconnected component) is invalid even when every listed edge endpoint exists and every edge is otherwise well-formed.

## Fleets

Each fleet has exact fields:

- `id`: unique `[A-Za-z0-9_-]+`
- `kingdom`: existing kingdom id
- `island`: existing island id
- `hulls`: nonempty array length `1..8` of hull catalog ids
- `fuel`: `0..fuel_cap` for those hulls
- `readiness`: `0..100`
- `captain`: `""` or a captain id belonging to the same kingdom

Initial co-occupation of an island by kingdoms that are WAR with each other is illegal. More than 3 fleets of the same kingdom on one island is illegal.

## Captains

Each captain has exact fields `id` (unique), `kingdom`, `command` `0..5`, `logistics` `0..5`. Each captain id appears on at most one fleet.

## Diplomacy

Each entry has exact fields `kingdom_a`, `kingdom_b`, `stance`. Kingdoms must differ and exist. Stance must be catalogued. At most one entry per undirected pair.

## Weather schedule

Each entry is an object that contains exactly the set of all island ids as keys, each mapped to a weather catalog id.
