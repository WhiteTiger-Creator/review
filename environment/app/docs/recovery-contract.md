# Recovery contract

`/app/bin/token-exposure-analyze` uses the file passed by `--state` as the durable analysis state. The state file is part of the public recovery interface, not a private cache. A run may resume from it only when the recorded evidence still matches the current event corpus and relevant configuration.

A checkpoint is valid only after a shard has been committed into the logical analysis state. A failed or interrupted run must not publish partial output. A later compatible run must validate the checkpoint, reuse already committed shards without dropping or duplicating evidence, and record that recovery happened.

The state file must use these public fields when applicable:

- `status`: one of `EMPTY`, `VALIDATING`, `CORRELATING`, `CHECKPOINTED`, `READY_TO_PUBLISH`, or `PUBLISHED`;
- `checkpoint_id`: stable nonempty identifier for a committed checkpoint;
- `committed_shards`: ordered list of committed shard identities;
- `evidence_fingerprint`: fingerprint of committed event evidence;
- `relevant_fingerprint`: fingerprint of relevant event/config/publication inputs;
- `resumed_from_checkpoint`: boolean, true on a successful run that resumed from a prior compatible checkpoint;
- `published`: boolean, true only after the final report and DOT have been atomically published.

Relevant invalidation is based only on inputs that can affect the report: event shard content, collector offsets, trust-boundary configuration, policy revisions, scope catalog, signing-key/keyset material used by observed events, and publication revision. A relevant change invalidates stale completed output or cached state before publishing. Irrelevant unused key material must not by itself change report bytes.

For recovery testing, the analyzer honors `TOKEN_EXPOSURE_FAILPOINT`. `TOKEN_EXPOSURE_FAILPOINT=after_checkpoint` exits nonzero after writing a valid checkpoint and before publication. It must leave no published `token_exposure_report.json` or `token_exposure_graph.dot`. `TOKEN_EXPOSURE_FAILPOINT=after_stage` exits nonzero after staging the report/DOT bytes and before replacing the published pair. Both failpoints are deterministic and are checked after the corresponding state transition on every normal run.

A successful resumed run after `after_checkpoint` must publish byte-identical report and DOT output to a clean uninterrupted run over the same inputs. A successful run after `after_stage` must preserve any previous complete published pair during the failing attempt, remove or ignore staging artifacts, and then publish the new complete pair on the next run.
