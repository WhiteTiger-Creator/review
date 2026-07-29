# Hanabi Firework Ruleset — Championship Cycle 2025

This document is the sole normative ruleset for championship table play. Where any club-night handbook, table profile, comment, or docstring disagrees, this firework ruleset controls.

## 1. Table geometry

1.1 Colors are exactly `R`, `Y`, `G`, `B`, `W`. Each color has one firework stack whose height is an integer in `0..5`.

1.2 A card is a pair `(c, r)` with `c` one of the five colors and `r` an integer rank in `1..5`.

1.3 Each scenario declares `players` (≥2), `hands` (one array per player), `deck` (draw pile, index 0 is the top), `info_tokens`, `fuse_tokens`, `fireworks`, `start_player`, and an ordered `moves` list.

1.4 Hand indices are zero-based within the current player's hand. Removing a card shifts later indices down immediately.

## 2. Tokens

2.1 Information tokens start at the scenario value and never exceed the championship maximum of `8`.

2.2 Fuse tokens start at the scenario value. Reaching `0` ends the match with `end_reason = "fuse_out"`.

2.3 A legal hint costs exactly `1` information token and requires `info_tokens ≥ 1` before the hint.

2.4 A legal discard restores exactly `1` information token when `info_tokens < 8`. When already at `8`, discard is still legal but restores nothing.

2.5 Successfully playing a rank-`5` card restores exactly `1` information token when `info_tokens < 8`.

## 3. Hints

3.1 A hint targets another player (`to` ≠ current player) and states either `kind = "color"` with `value` in `{R,Y,G,B,W}` or `kind = "rank"` with `value` equal to the decimal string of a rank `1..5`.

3.2 The hint must match at least one card in the target hand. Empty hints are illegal and must be rejected without changing tokens or turn ownership.

3.3 Self-hints (`to == current`) are illegal.

3.4 After a legal hint, turn ownership advances to the next player (`(current + 1) mod players`). Hints never grant an extra turn.

## 4. Play

4.1 Playing selects one card from the current player's hand by index. Out-of-range indices are rejected without mutation.

4.2 Let `expected = fireworks[c] + 1`. The play succeeds if and only if the card's rank equals `expected` and `expected ≤ 5`.

4.3 On success, set `fireworks[c] = rank`. Successful plays never consume fuse tokens.

4.4 On failure, decrement fuse tokens by one. The card is removed from hand and is not added to any firework stack.

4.5 After a resolved play (success or failure), if the match is not over and the deck is non-empty, draw the top deck card into the acting player's hand.

4.6 If every firework equals `5` after a successful play, the match ends immediately with `end_reason = "perfect"` and `score = 25`.

4.7 Skip-ahead plays (rank strictly greater than `expected`) are illegal failures under §4.2, not successes.

## 5. Discard

5.1 Discarding selects one card from the current player's hand by index. Out-of-range indices are rejected.

5.2 Apply §2.4 token restoration, then draw the top deck card when the deck is non-empty and the match is not over.

5.3 Discard is legal at maximum information tokens; only the restoration is suppressed (§2.4).

## 6. Turn order and final round

6.1 After every legal action, ownership advances to `(current + 1) mod players` unless the match has already ended.

6.2 When a draw removes the last deck card, arm the final round: each player, including the player who drew the last card, receives exactly one additional turn after that emptying action completes. A scenario whose deck is already empty before any move does not arm the final round until (and unless) a later draw empties a non-empty deck; an initially empty deck alone never starts the final-round counter.

6.3 Operationally: set an internal counter to `players + 1` when the deck first becomes empty via a draw, and decrement the counter by one at the end of every subsequent turn advance (including the advance of the emptying action). Each such advance rotates ownership first, then decrements. When the counter reaches `0`, end with `end_reason = "deck_end"` unless a higher-priority end already occurred (`fuse_out` or `perfect`). Ending reasons `fuse_out` and `perfect` always outrank `deck_end` when they fire on the same resolved action or while the final-round counter is still positive. The recorded `final_player` for a `deck_end` close is the seat after that final rotation.

6.4 Illegal actions never advance the turn and never decrement the final-round counter.

## 7. Scoring and end reasons

7.1 Championship `score` is the sum of the five firework heights. It is never the count of non-zero stacks and never `5 × (number of completed fives)` except insofar as that coincides with the sum.

7.2 `end_reason` is one of `"none"`, `"fuse_out"`, `"perfect"`, or `"deck_end"`.

7.3 `game_over` is true exactly when an ending condition in §2.2, §4.6, or §6.3 has fired.

7.4 `ply_count` equals `len(moves_applied)`. Rejected move indices appear only in `moves_rejected`.

## 8. Output contract

8.1 For each scenario name `S` in `/app/config/engine.json` `scenario_order`, write `/app/output/S/session_log.json` with keys:
`scenario`, `moves_applied`, `moves_rejected`, `final_info_tokens`, `final_fuse_tokens`, `fireworks`, `score`, `game_over`, `end_reason`, `hints_given`, `cards_played`, `cards_discarded`, `ply_count`, `final_player`.

8.2 Write `/app/output/summary.json` with keys:
`scenario_count`, `total_score`, `total_hints`, `total_plays`, `total_discards`, `total_plies`, `end_reasons` (counts for `none`, `fuse_out`, `perfect`, `deck_end`).

8.3 `fireworks` must include all five color keys. After a legal action that does not end the match, `final_player` is the next player (`(acting + 1) mod players`). For `fuse_out` and `perfect`, the match ends before turn advance runs, so `final_player` remains the acting player. For `deck_end`, the ending advance still rotates ownership first and then expires the final-round counter; `final_player` is the seat after that rotation (the player who would have acted next). Do not apply an extra rotation after the match has already ended.

## 9. Integrity of fixtures

9.1 Scenario files under `/app/scenarios/` and configuration under `/app/config/` are immutable adjudication fixtures.
