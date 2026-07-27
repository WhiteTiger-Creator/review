# Staging then export

Playtest is a two-stage pipeline. Hunt must materialize an on-disk staging snapshot before any final artifact is trusted.

## Staging path

Place the staging file beside the journal:

`dirname(journal) / seed-hunt-staging.json`

For the stock CLI invocation that uses `/app/state/playtest-journal.jsonl`, staging is:

`/app/state/seed-hunt-staging.json`

## Staging schema

```json
{
  "schema": "undercroft-seed-staging-v1",
  "campaigns": [
    {
      "campaign_id": "...",
      "candidate_seed": 0,
      "path_len": 0,
      "mean_gap": 0.0,
      "gold_density_early": 0.0,
      "gold_density_mid": 0.0,
      "gold_density_late": 0.0,
      "total_gold": 0,
      "cum_threat_end": 0,
      "max_room_threat": 0,
      "fair": true
    }
  ]
}
```

Campaign order matches lexicographic campaign filename order. `candidate_seed` is the first fair seed in the search window under the reachability, pacing, treasure, and threat contracts.

## Export rules

1. After the hunt loop finishes, write the staging file bytes.
2. Re-read staging from disk (do not keep using only in-memory hunt structs for publish).
3. For each staging row, regenerate the dungeon for `candidate_seed` and re-evaluate all four invariant families. If any row fails re-validation, exit non-zero and do not publish a successful seal.
4. Journal lines, ledger rows, and atlas routes must use the re-read staging seeds (and recomputed metrics that match regeneration).
5. Biome wrap helpers and decoy biome labels are non-authoritative: final artifacts must not embed decoy biome strings.

## Seal binding

`fairness-seal.json` must include `staging_digest`: SHA-256 hex of the exact staging file bytes, in addition to ledger and atlas digests.
