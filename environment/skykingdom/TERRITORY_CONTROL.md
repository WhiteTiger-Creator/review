# Territory Control

This document is normative for ownership, fortification, and the FORTIFY command.

## Island state

Each island live record includes:

- `id`, `name`
- `owner` (kingdom id or empty string)
- `fortification` (integer `0..5`)
- `depot` (bool)
- `level` (integer `1..5`)
- `aetherium_yield`, `crystal_yield`, `timber_yield` (integers `0..20`)
- `weather` (current weather id)

## Ownership transfer

When combat transfers ownership (COMBAT_RULES.md):

1. `owner` becomes the attacker kingdom.
2. `fortification` becomes `max(0, fortification - 1)`.
3. Fleets on the island do not automatically move.

Unowned islands have `owner` equal to empty string. They may be claimed by an attacker-win fortification-only clash launched from an adjacent island when the island has fortification `>= 0` (always true) and no hostile fleet — treat unowned islands as fortification-only defense against any attacker (no WAR check against owner). For unowned islands, CLASH ignores the WAR requirement against owner; WAR is still required if a defending fleet is present.

## FORTIFY

`FORTIFY <island>` is legal when:

1. Island is owned by the player kingdom.
2. `fortification < 5`.
3. Player treasury timber `>= 8`.

On success, timber decreases by 8 and fortification increases by 1.
