# Shortest routes

A winning route is a move sequence that occupies the exit. Among all winning routes, keep only those with the minimum number of moves.

Two routes are distinct when their move sequences differ, even if they later share the same complete state.

The shortest-route count is the exact number of distinct minimum-length winning sequences, written as an unsigned decimal string without leading zeros. Values may exceed sixty-four bits.

The canonical route is the lexicographically smallest shortest sequence under the fixed order Up < Right < Down < Left. Its trace records every move with complete post-move key and collapse sets.
