# Output record

`/app/output/culvert_rank.yaml` uses profile `culvert-inv-1`.

The `profile` field is set to `culvert-inv-1`.

The `partition_count` field reports the selected cluster count after window-bucket adjustment.

The `rank_order` field reports node ids in priority order.

The `spectral_span` field reports the maximizing eigen gap before bucket adjustment, rounded by the emitter.

The `group_digest` field is the 16-character lowercase hex digest defined in `/app/environment/docs/replay_contract.md`.

Across the anchor fixture and the bundled `0417` metamorphic fixtures, `partition_count`, `rank_order`, `group_digest`, and `spectral_span` must agree when replay is healthy.
