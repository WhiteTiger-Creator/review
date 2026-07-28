# API Specification

This document is normative for the `/app/skykingdom/skykingdom` binary.

## Document map (read all sections)

| Topic | Section |
| --- | --- |
| Eval ops including `validateScenario` / `validateGame` | Eval operations |
| Live Game JSON shape (id-keyed maps) | Game object shape |
| Exact MAP / STATUS / FLEET / ISLAND text | MAP render format, STATUS render format, FLEET render format, ISLAND render format |
| Success strings (`Moved`, `Exiting`, …) | Command outputs |
| `kind:id` violation grammar | Violation strings |

Scenario connectivity, weather ids, stacking, and edge legality are defined in `/app/skykingdom/SCENARIO_SCHEMA.md`, `/app/skykingdom/WEATHER_SYSTEM.md`, and `/app/skykingdom/FLEET_RULES.md` — not only in this file.

## Build

From `/app/skykingdom`:

```bash
go build -o skykingdom .
```

## Modes

### play

```bash
./skykingdom play <scenario.json>
```

Reads newline-delimited commands from stdin until EXIT or EOF. Prints human-readable lines to stdout. Rejected commands begin with `Rejected command:`. Successful command acknowledgements use the exact strings in the Command outputs section below. EXIT prints exactly `Exiting` then ends the loop.

### eval

```bash
./skykingdom eval
```

Reads one JSON request object from stdin. Writes one JSON response object to stdout and exits. No other stdout bytes. Stderr must be empty on success.

Request envelope:

```json
{"op": "<name>", ...}
```

Response envelope:

```json
{"ok": true, "result": ...}
```

or

```json
{"ok": false, "error": "<message>"}
```

Error message text is not graded except that rejected command execution through `executeCommand` returns `ok: true` with a result object containing the unchanged game and an `output` string beginning with `Rejected command:`.

## Operations (exact op names)

1. `validateScenario` — args: `scenario`. Result: deep copy of validated scenario.
2. `createGame` — args: `scenario`. Result: full game object using the Game object shape below (JSON objects keyed by id, not arrays).
3. `hullCatalog` — no args. Result: ordered array of hull objects `{id,atk,def,fuel_cap,base_range,upkeep}`.
4. `techCatalog` — no args. Result: ordered array of tech objects `{id,cost_aetherium,cost_crystal,prerequisite,range_bonus,fuel_discount_pct,atk_pct,def_pct,crown_docks}`.
5. `shortestPath` — args: `game`, `from`, `to`. Result: `{distance, path}` where path is the lex-smallest min-edge island id list.
6. `pathFuelCost` — args: `game`, `fleet_id`, `to`. Result: `{raw_cost, paid, path}`.
7. `isSupplied` — args: `game`, `fleet_id`. Result: boolean.
8. `combatPreview` — args: `game`, `fleet_id`, `target`. Result: clash-style scores without mutating (`attacker_score`, `defender_score`, `island_id`, `defender_id`). Must leave the caller's game argument unchanged.
9. `simulateClash` — args: `game`, `fleet_id`, `target`. Result: `{game, clash}` after applying clash mutation (deep independent game copy in / out: input game must not be mutated — operate on a copy).
10. `executeCommand` — args: `game`, `line`. Result: `{game, output}` where `output` is exactly one of the Command outputs strings below (success or rejection).
11. `replayRun` — args: `scenario`, `commands` (array of strings). Result: `{game, outputs}` after applying commands in order via executeCommand semantics (including rejected lines).
12. `scoreGame` — args: `game`. Result: score_breakdown object (computes even if still running, using current counters; does not change state).
13. `renderGame` — args: `game`. Result: string (same text STATUS would print).
14. `validateGame` — args: `game`. Result: `{legal: bool, violations: [string, ...]}` independent consistency checks (fleet fuel caps, ownership references, diplomacy keys, stacking, researched prereqs). When `legal` is false, each violation string uses the exact `kind:id` grammar in Violation strings below.

## Game object shape

`createGame`, `executeCommand`, `replayRun`, and `simulateClash` expose this JSON shape. Collections that are maps in CAMPAIGN_RULES.md must serialize as JSON objects keyed by id strings, never as arrays:

```json
{
  "scenario": {},
  "state": "running",
  "turn": 1,
  "player": "SKY",
  "kingdoms": { "SKY": { "id": "SKY", "name": "...", "aetherium": 0, "crystal": 0, "timber": 0, "fuel": 0, "researched": [] } },
  "islands": { "A1": { "id": "A1", "name": "...", "owner": "SKY", "fortification": 0, "depot": true, "level": 1, "aetherium_yield": 0, "crystal_yield": 0, "timber_yield": 0, "weather": "CLEAR" } },
  "fleets": { "SF1": { "id": "SF1", "kingdom": "SKY", "island": "A1", "hulls": ["FRIGATE"], "fuel": 0, "readiness": 100, "captain": "" } },
  "captains": { "CAP_SKY": { "id": "CAP_SKY", "kingdom": "SKY", "command": 0, "logistics": 0 } },
  "diplomacy": { "IRON|SKY": "WAR" },
  "history": [],
  "last_clash": null,
  "score_breakdown": null
}
```

Field `player` is the player kingdom id (not `player_kingdom`). Diplomacy keys are `pairKey = min(idA,idB) + "|" + max(idA,idB)` with lexicographic min/max of the two kingdom ids.

## Export order note

Documentation order above is the graded catalog order for `hullCatalog` and `techCatalog`. Ops may be called independently.

## Command outputs

`executeCommand` and interactive play print these exact success strings (no trailing punctuation, no fleet/island echo):

| Verb | Success `output` |
| --- | --- |
| MOVE | `Moved` |
| REFUEL | `Refueled` |
| CLASH | `Clash resolved` |
| RESEARCH | `Researched` |
| TREATY | `Treaty updated` |
| FORTIFY | `Fortified` |
| ENDTURN | `Turn advanced to <t> [<state>]` where `<t>` is the post-advance turn integer and `<state>` is `running`, `won`, or `lost` |
| REBOOT | `Rebooted` |
| EXIT | `Exiting` |

Rejected lines always begin with the exact prefix `Rejected command:` followed by a space and a short reason. They must not append history and must leave the full campaign unchanged.

Information commands STATUS, MAP, FLEET, and ISLAND return their render text and do not append history.

### MAP render format

One line per island in lexicographic island id order, each ending with newline:

```text
<island_id> owner=<owner_or_empty> fort=<n> weather=<weather> depot=<true|false>
```

Boolean depot uses lowercase `true` or `false`.

### FLEET render format

Exact single line (trailing newline):

```text
<fleet_id> kingdom=<kid> island=<iid> fuel=<n> readiness=<n> hulls=<comma-joined> captain=<id_or_empty>
```

Unknown fleet id yields `Rejected command: fleet`.

### ISLAND render format

Exact single line (trailing newline):

```text
<island_id> owner=<owner_or_empty> fort=<n> weather=<weather> depot=<true|false> level=<n>
```

Unknown island id yields `Rejected command: island`.

REBOOT replaces the live campaign with a fresh `createGame` of the same scenario object: `turn` is 1, `history` is empty, fleets and islands match the initial scenario, and `last_clash` is null.

## Violation strings

`validateGame` returns `violations` as an array of strings. Graded kinds use this exact form:

- `fuel:<fleet_id>` when fleet fuel is outside `0..fuel_cap`
- `readiness:<fleet_id>` when readiness is outside `0..100`
- `fleet-kingdom:<fleet_id>` when the fleet kingdom is missing
- `fleet-island:<fleet_id>` when the fleet island is missing
- `hull:<fleet_id>` when a hull id is unknown
- `stack:<island_id>` when more than three fleets of one kingdom share an island
- `tech:<tech_id>` when a researched tech is unknown
- `prereq:<kingdom_id>:<tech_id>` when a researched tech is missing its prerequisite

An empty violations array is required when `legal` is true (JSON `[]`, not null).

## STATUS render format

Exact lines (trailing newline at end of string):

```text
Turn <t> [<state>] Player=<id>
Treasury aetherium=<n> crystal=<n> timber=<n> fuel=<n>
Islands owned=<n> Fleets=<n>
Researched: <comma-separated or (none)>
```
