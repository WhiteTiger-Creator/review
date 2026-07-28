# Diplomacy Rules

This document is normative for pairwise kingdom stances and command effects.

## Stances

Exact set: `PEACE`, `ALLIED`, `EMBARGO`, `WAR`

Stance is undirected: the pair `(A,B)` shares one stance. Scenario `diplomacy` lists unique unordered pairs with a stance. At runtime the campaign stores a map keyed by `min(idA,idB) + "|" + max(idA,idB)` (lexicographic min/max of the two kingdom ids).

Default for any kingdom pair not listed is `PEACE`.

## TREATY command

`TREATY <kingdom> <stance>` sets the stance between the player kingdom and `<kingdom>`.

Legal when:

1. Target kingdom exists and is not the player kingdom.
2. Stance is one of the four catalog values.
3. Transition is allowed:

| from \ to | PEACE | ALLIED | EMBARGO | WAR |
| --- | --- | --- | --- | --- |
| PEACE | no-op illegal | yes | yes | yes |
| ALLIED | yes | no-op illegal | yes | no |
| EMBARGO | yes | no | no-op illegal | yes |
| WAR | yes | no | yes | no-op illegal |

"no-op illegal" means requesting the current stance is rejected. ALLIED cannot jump directly to WAR (must pass EMBARGO or PEACE). WAR cannot jump directly to ALLIED.

On success, update the pairwise stance and record history.

## Combat and movement gates

- MOVE onto an island owned by a WAR opponent is illegal (FLEET_RULES.md).
- CLASH requires the opposing kingdom (defender fleet kingdom or island owner) to be WAR with the attacker.
- Supply transit may cross ALLIED ownership (SUPPLY_LOGISTICS.md).
- EMBARGO has no extra movement effect beyond default ownership rules; it blocks future ALLIED upgrades until changed and is used by scoring as a tension flag.
