# matrix placement contract

Symbol size is 17 + 4 * version modules. Function patterns: three finder
patterns with separators, timing row and column at index 6, alignment
patterns per the version's center list (skipping the three finder corners),
the dark module at (size - 8, 8), reserved format areas, and for versions 7
and up the two 3x6 version information blocks.

## data placement

The interleaved stream is placed in two-module columns from the right edge
moving left, skipping column 6 entirely, alternating upward and downward,
right cell before left cell, function modules skipped. Remainder bits (7 for
versions 2 through 6, otherwise 0 in versions 1..12) are placed as light
modules after the stream.

## masking

Mask conditions 0..7 follow ISO/IEC 18004 clause 8.8.1 and apply to
non-function modules only.

## format information

The 5-bit field is ecc bits (L=01, M=00, Q=11, H=10) followed by the 3-bit
mask id. Ten BCH(15,5) remainder bits are appended using generator
x^10+x^8+x^5+x^4+x^2+x+1 (0x537), and the resulting 15 bits are XORed with
the fixed mask 101010000010010 (0x5412) before placement. Skipping the XOR
step produces symbols that no conforming reader accepts. The 15 bits are
written to both fixed format areas in the standard order, and the dark
module stays dark.

## version information

For versions 7 and up, the 6-bit version number is extended with 12 BCH
remainder bits using generator 0x1F25 and written to both version blocks,
bit i at (i div 3, size - 11 + i mod 3) and its transpose.
