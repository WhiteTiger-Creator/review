# Campaign Rules

This document is normative for campaign lifecycle, ENDTURN phases, NPC doctrine, victory, and scoring hooks.

## Create

`createGame(scenario)` validates the scenario, deep-copies it, and returns a mutable campaign:

```text
{
  scenario,                    # validated copy
  state: "running",            # later "won" or "lost"
  turn: 1,
  player: scenario.player_kingdom,
  kingdoms: {id: KingdomState, ...},
  islands: {id: IslandState, ...},
  fleets: {id: FleetState, ...},
  captains: {id: CaptainState, ...},
  diplomacy: {pairKey: stance, ...},
  history: [],
  last_clash: null,
  score_breakdown: null
}
```

KingdomState treasury fields: `aetherium`, `crystal`, `timber`, `fuel`, plus `researched` (list of tech ids). Initial values come from scenario kingdom records.

## Command processing

`executeCommand(game, line)` trims outer whitespace, splits on ASCII spaces, and uppercases only the verb. Arguments preserve case. Empty lines are rejected.

Information commands (MAP, STATUS, FLEET, ISLAND) never mutate state and never append history.

Mutating commands append the normalized line (verb uppercased, arguments joined with single spaces) to `history` on success.

When `state` is `won` or `lost`, all mutating commands except REBOOT are rejected. Information commands and EXIT remain legal.

REBOOT replaces the live game in place with a fresh createGame of the same scenario: empty history, turn 1, initial fleets/islands/treasuries, and null last_clash. Success acknowledgement is defined in API_SPEC.md.

## ENDTURN phases

On successful `ENDTURN`, run phases in this exact order:

1. **Upkeep and supply effects** for all fleets (SUPPLY_LOGISTICS.md), kingdoms processed in lexicographic kingdom id order; within a kingdom, fleets in lexicographic fleet id order.
2. **Economy production** for all islands with nonempty owner, islands in lexicographic id order.
3. **CROWN_DOCKS bonus**: for each kingdom that researched CROWN_DOCKS, add `2` fuel treasury for each depot it owns (after ordinary depot income in step 2 — ordinary income already applied per SUPPLY_LOGISTICS.md; CROWN_DOCKS adds the extra `+2` per owned depot here).
4. **NPC doctrine**: for each non-player kingdom in lexicographic order, apply doctrine from CAMPAIGN_RULES.md §NPC doctrine.
5. **Weather advance**: `turn += 1`; assign weather from schedule.
6. **Victory check**: apply victory / loss rules; may set `state` to `won` or `lost` and compute `score_breakdown`.

If `turn` would exceed `max_turns` after increment, set `state` to `lost` unless victory already triggered in the same ENDTURN before weather advance… Victory is checked after weather advance. If after increment `turn > max_turns` and state still `running`, set `lost`.

Clarification: schedule indexing uses `min(turn-1, len-1)` after the increment. Loss due to turn limit triggers when `turn > max_turns` after the increment.

## NPC doctrine

Each non-player kingdom performs at most one action per ENDTURN. Build candidate lists explicitly, then sort; do not rely on map iteration order.

1. **CLASH candidates:** For every fleet of the acting kingdom, for every graph neighbor island of that fleet's island, if `CLASH <fleet> <island>` would be legal under COMBAT_RULES.md (including unowned islands that host a WAR-hostile fleet, and islands owned by a WAR opponent), add the pair `(fleet_id, island_id)`. If the candidate list is nonempty, execute the clash for the pair with the lexicographically smallest `fleet_id`; ties break on the lexicographically smallest `island_id`. Ownership alone is not the filter — legality of CLASH is the filter.
2. Else if it can legally MOVE some fleet toward the nearest island it does not own (fewest edges; tie smallest destination id; tie smallest fleet id), MOVE one step along the lexicographically smallest shortest path (first hop only: destination is the second node of that path).
3. Else if it can legally RESEARCH the first catalog tech it can afford and unlock, do so.
4. Else do nothing.

NPC actions do not append to player `history`. They may update `last_clash`.

## Victory conditions

Scenario `victory` has `kind` and `threshold`:

- `islands`: player wins when owned island count `>= threshold`.
- `crystal`: player wins when treasury crystal `>= threshold`.
- `elimination`: player wins when every non-player kingdom has zero fleets and owns zero islands.

Loss: player has zero fleets and zero islands at victory check, or turn limit exceeded as above.

## Score breakdown

When state becomes `won` or `lost`, set:

```text
score_breakdown = {
  objective: 100 if won else 0,
  territory: 5 * player_owned_islands,
  resources: floor((aetherium + crystal + timber + fuel) / 10),
  survival: 3 * player_fleet_count + sum(floor(readiness/10) across player fleets),
  dominance: 4 * (player_owned_islands - max_enemy_owned_islands),
  violations: 0,
  mission: threshold_progress_points,
  total: sum of the above
}
```

`threshold_progress_points`: for `islands`, `2 * owned`; for `crystal`, `floor(crystal/5)`; for `elimination`, `10 * (defeated_kingdoms)`.
`dominance` may be negative. `violations` remains 0 for legal engines (validator-detected illegal states may set it in scoring helpers, but a correct engine never needs it).
