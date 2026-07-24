# codeword assembly contract

The assemble stage converts the planned segments into the final data
codeword vector for the chosen (version, ecc level).

1. For each segment in order: 4-bit mode indicator (numeric 0001,
   alphanumeric 0010, byte 0100), character count indicator at the width for
   the plan's version class, then the segment data bits per
   segmentation-dp.md. A trailing group of 2 digits in a numeric segment is
   encoded in exactly 7 bits; a trailing single digit in exactly 4 bits.
2. Terminator: up to four zero bits, truncated so the stream never exceeds
   the data capacity of the symbol.
3. Zero bits pad the stream to the next codeword boundary.
4. Alternating pad codewords 11101100 (0xEC) then 00010001 (0x11) fill the
   remaining capacity, starting with 0xEC.

The assembled bit length before terminator must equal the plan's total_bits;
the final vector length must equal the symbol's data capacity in codewords.
