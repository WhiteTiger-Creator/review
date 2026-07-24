# interleave order contract

The transmission stream for a symbol is built from its blocks strictly
round-robin, column by column:

1. Data codewords: for i = 0, 1, 2, ... take the i-th data codeword of every
   block (in global block order) that still has an i-th data codeword. When
   group 2 blocks are one codeword longer than group 1 blocks, the final
   column visits only the group 2 blocks, still in block order and still
   interleaved as a column. Appending leftover tail codewords block-major
   (all of block k, then all of block k+1) is a contract violation.
2. ECC codewords: same column-wise round-robin over the per-block ECC
   vectors, which all share the same length.

The stream length equals total data plus total ECC codewords. streams.tsv
records the stream hex and its SHA-256; the digest column must equal the
SHA-256 of the decoded hex bytes.
