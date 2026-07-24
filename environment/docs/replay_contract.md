# Replay contract

## Window coupling

For each input row, compute the Euclidean (L2) feature norm.

Use a zero shift on every feature dimension.

Set every dimension's scale factor to the mean of those row norms. If the mean is below `1e-9`, use `1.0`.

Let `median` be the median of the row norms (upper middle element after sorting ascending). Count how many norms are strictly greater than `median`. The window bucket is that count modulo `3`.

Windowed features are `(raw - shift) / scale` per dimension.

## Partition selection

Build the RBF affinity graph on windowed features with the configured sigma, form the Laplacian, and take the smallest eigenvalues (at most four, or fewer when the case has fewer nodes).

Choose the eigengap index `k` that maximizes `spectrum[k] - spectrum[k-1]` for `k` in `1 .. n-1`.

Adjust with the window bucket: `k_adj = clamp(k + bucket, 1, n-1)` where `n` is the spectrum length. Emit `partition_count = k_adj` and `spectral_span` equal to the maximizing gap before the bucket adjustment.

## Rank binding

Score each node by the L2 norm of its original (unwindowed) features.

Order node ids by descending score, breaking ties by ascending id string.

Case marks and partition labels must not change scores, order, or the digest. In particular, marks that contain `0417` must not rewrite `rank_order`.

## Digest

`group_digest` is the first 16 lowercase hex characters of SHA-256 over the UTF-8 bytes of each `rank_order` id, concatenated in listed order.

## Metamorphic stability

Cases whose marks include `0417-rot` or `0417-scale` must preserve `partition_count`, `rank_order`, `group_digest`, and `spectral_span` relative to a geometrically equivalent untransformed sibling that shares the same node ids.

Isotropic feature scaling and planar rotation (and their composition) are similarity transforms that must not change those fields after correct window coupling.

## Live regeneration

`scripts/replay.sh` must rebuild `/app/output/culvert_rank.yaml` from the Java pipeline. Static copies of prior YAML do not satisfy the contract.
