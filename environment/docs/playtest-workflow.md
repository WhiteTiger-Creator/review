# Playtest workflow

The undercroft fairness planner is a terminal simulation game tool. Each playtest tick loads every `*.json` campaign in the campaigns directory (lexicographic order by filename), searches for a fair seed, writes a staging snapshot, re-validates that snapshot, then publishes ledger, route atlas, fairness seal, and a JSONL journal.

Stock fixtures under /app/fixtures/campaigns use campaign_id values crypt_alpha, crypt_beta, and crypt_gamma. Tests may load these ids from disk rather than inventing alternate campaign names.

Required CLI:

```
undercroft-fairness playtest \
  --campaigns <dir> \
  --ledger <path> \
  --atlas <path> \
  --seal <path> \
  --journal <path>
```

Staging is written beside the journal as `seed-hunt-staging.json` (see staging-export-contract.md). Exit code 0 only when every campaign yields a fair seed, staging re-validation succeeds, and all artifacts are written. Parent directories for outputs must be created when missing.

Wrap helpers under cartograph and decoy biome labels are not part of the fairness authority path.
