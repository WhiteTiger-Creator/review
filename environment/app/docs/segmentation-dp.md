# mixed-mode segmentation dynamic program and version fixpoint

## modes

Three encoding modes are supported, in canonical order numeric (0),
alphanumeric (1), byte (2). A character is numeric-capable for ASCII digits
0-9, alphanumeric-capable for the 45-character set
0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ space $%*+-./:, and byte-capable always.

## data bit counts

- numeric: 10 bits per full group of 3 digits; a trailing group of 1 digit
  costs 4 bits and a trailing group of 2 digits costs 7 bits.
- alphanumeric: 11 bits per pair; a trailing single character costs 6 bits.
- byte: 8 bits per character.

## headers and character count indicator

Each segment costs a 4-bit mode indicator plus a character count indicator
whose width depends on the mode and the version class:

| mode | versions 1-9 (class 0) | versions 10-26 (class 1) |
|------|------------------------|--------------------------|
| numeric | 10 | 12 |
| alphanumeric | 9 | 11 |
| byte | 8 | 16 |

## optimal segmentation

For a fixed version class, the segmentation must minimize total bit count
(header plus data bits over all segments). Ties on bit count resolve to the
fewest segments; remaining ties resolve to the earlier mode in canonical
order. The published dynamic program tracks, per character position, the best
state for each (mode, open segment length modulo group size) pair, where
group size is 3 for numeric, 2 for alphanumeric, 1 for byte.

## version fixpoint

The chosen version is the smallest version 1..12 whose data capacity (in
bits, per the ECC block table) is at least the optimal bit count computed
with that version's class. Because the character count indicator widths
change at the class boundary, the bit count for class 0 must not be reused
when testing class 1 versions; the dynamic program must be evaluated per
class. The recorded plan row carries the winning class, total bits, and
segment count; segments.tsv carries the ordered segment list with per-segment
bit counts (header plus data bits).
