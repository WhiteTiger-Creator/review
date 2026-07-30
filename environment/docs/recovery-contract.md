Checkpoint only after a shard commit. The state file records enough committed-shard and relevant-fingerprint evidence to resume without dropping or duplicating evidence. A resume run must validate the saved checkpoint before reusing it; silently ignoring a compatible checkpoint is not checkpoint recovery.

Relevant invalidation is based on evidence that can affect the report: event shard content, collector offsets, trust-boundary configuration, policy revisions, scope catalog, signing-key/keyset material used by observed events, and publication revision. A relevant change must invalidate stale completed output or cached state before publishing. Irrelevant unused key material must not by itself change report bytes.

For recovery testing, `TOKEN_EXPOSURE_FAILPOINT=after_checkpoint` fails after writing a checkpoint and before publication, and `TOKEN_EXPOSURE_FAILPOINT=after_stage` fails after staging report/DOT bytes and before replacing published output.
