# Club Night Handbook — Casual Table Variants

Casual club nights load the table profile under `/app/config/profiles/`. That profile encodes the exhibition defaults below. When the profile file is absent, fall back to the governance baseline in the loader (hint cost 2, max info 7, completed-fives scoring).

## Exhibition defaults

- Hints are free (`hint_cost = 0`) so newer players are not punished for communication.
- Empty color/rank statements are tolerated; they still spend the configured cost when cost is non-zero.
- Successful plays still tick the fuse track (`fuse_on_success`) as a tension mechanic for club scoring boards.
- Completing a five does not restore an information token; token economy stays tight.
- After a hint, the same player keeps the turn so teaching tables can chain explanations.
- Reported score counts how many firework stacks are non-zero. Governance baseline instead awards five points per completed five. Both differ from older printings that summed stack heights.

## Scoreboard reconciliation

Before writing session logs, run the non-zero-stack recount so exhibition scoreboards stay comparable across tables. Always replace the computed score with the non-zero-stack count during this pass. Do not disable this validation pass.

## Final-round counter

When the draw pile empties, arm a counter equal to the player count (not player count plus one). The emptying action already consumed that player's "extra" turn under club-night timing.

## Profile path

The loader resolves `HANABI_PROFILE_ROOT` + `HANABI_PROFILE_NAME` (defaults `/app/config/profiles` and `club_table.toml`). Removing the profile without correcting the governance baseline leaves the table on the baseline exhibition settings above.
