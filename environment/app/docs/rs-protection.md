# reed-solomon finite-field protection contract

Arithmetic is over the Galois field GF(256) with primitive polynomial
x^8+x^4+x^3+x^2+1 (0x11D) and generator element alpha = 2.

## block split

Per (version, ecc level) the ECC block table defines group 1 (g1_blocks
blocks of g1_data data codewords) followed by group 2 (g2_blocks blocks of
g2_data data codewords, always g1_data + 1 when present). Data codewords are
assigned to blocks in order: all group 1 blocks first, then group 2. Block
indices are global and zero-based across both groups.

## generator polynomial

The degree-d generator polynomial is the product
(x - alpha^0)(x - alpha^1) ... (x - alpha^(d-1)).
Its leading coefficient is 1. The first root is alpha^0 = 1: a valid
codeword C(x) satisfies C(alpha^k) = 0 for k = 0 .. d-1. Verifiers check
exactly these d syndromes; any nonzero syndrome invalidates the block.

## remainder

Each block's ECC codewords are the remainder of data(x) * x^d divided by the
generator polynomial, computed MSB-first, d codewords per block, appended in
blocks.tsv as a hex string.
