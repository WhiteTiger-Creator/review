# Path Length Security Bound

Basic Constraints determine whether a certificate can act as a Certificate Authority (CA) and limit the depth of the admitted validation chain.

## 1. CA Validation
For any constructed chain `[C_0, C_1, C_2, ..., C_k]` (where `C_0` is the target leaf and `C_k` is a trusted root):
- The leaf certificate `C_0` is not required to be a CA.
- Every intermediate certificate `C_i` (where `0 < i < k`) MUST have `is_ca: true` in its `basic_constraints`.
- The root certificate `C_k` MUST have `is_ca: true` in its `basic_constraints`.

## 2. Path Length Constraints
A CA certificate may assert a `path_len_constraint` value (an integer `>= 0`). This constraint limits the number of non-self-issued intermediate certificates that can appear between this certificate and the target leaf certificate.

In a chain `[C_0, C_1, ..., C_k]` (where `C_0` is the leaf, `C_k` is the root):
- For each certificate `C_j` (where `j > 0`) that specifies a `path_len_constraint` (say `L`):
  - The number of intermediate certificates below `C_j` in the path (i.e. certificates `C_i` for `0 < i < j`) must be at most `L`.
  - Mathematically: `j - 1 <= L`.
- If `path_len_constraint` is omitted or null, no path length limit is imposed by that certificate.
- Root certificates are subject to their own path length constraints if specified.
