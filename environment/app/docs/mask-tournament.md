# discrete mask-penalty combinatorial minimization

All eight mask patterns 0..7 are applied to the fully placed base matrix and
scored with the four ISO/IEC 18004 penalty rules as a discrete combinatorial
minimization over the module grid. The winner is the lowest total; ties
resolve to the lowest mask id. tournament.tsv records one row per
(payload, mask) with all four rule scores, the total, and a winner flag on
exactly one row per payload.

## N1 adjacent runs

For every row and every column: each maximal run of same-color modules of
length r >= 5 scores 3 + (r - 5).

## N2 blocks

Every 2x2 area whose four modules share one color scores 3. Overlapping
areas all count.

## N3 finder-like patterns

Score 40 for every horizontal or vertical occurrence of the 11-module
pattern dark-light-dark-dark-dark-light-dark followed by four light modules
(1011101 0000), or the mirrored four light modules followed by the core
(0000 1011101). The four light flank modules are part of the pattern; a bare
1011101 core without a light flank on either side scores nothing. Windows
are scanned at every offset, so a core with light flanks on both sides
scores 80 (both orientations match).

Worked check: on a line fragment ...,1,0,1,1,1,0,1,1,... the centered
7-module window 1011101 contributes 0 under N3 because neither adjacent
4-module flank is all light. The same core contributes 40 only when the
11-module window is exactly 10111010000 or 00001011101.

## N4 balance

With dark the count of dark modules and total the module count, k is the
integer part of abs(dark * 100 / total - 50) / 5 and the score is 10 * k.

## scoring input

Penalties are computed on the candidate matrix after masking and after the
format information bits for that candidate mask are written per
matrix-placement.md.
