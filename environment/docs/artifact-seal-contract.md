# Artifacts and seal

## seed-hunt-staging.json

See staging-export-contract.md. Staging is mandatory and is the publish source of truth after re-read.

## seed-ledger.json

```json
{
  "schema": "undercroft-seed-ledger-v1",
  "campaigns": [
    {
      "campaign_id": "...",
      "selected_seed": 0,
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

Campaigns array order matches lexicographic campaign filename order.

mean_gap: when only one monster is on the path, emit `mean_gap_min` from the campaign profile. When multiple, emit the arithmetic mean of pairwise gaps. When zero monsters (should not appear in a fair ledger), emit 0.0.

Ledger rows always set fair to true on success. selected_seed is the first passing candidate in the search window and must equal the staging candidate_seed for that campaign.

## route-atlas.json

```json
{
  "schema": "undercroft-route-atlas-v1",
  "routes": [
    {
      "campaign_id": "...",
      "seed": 0,
      "start": 0,
      "exit": 0,
      "critical_path": [0, 1, 2]
    }
  ]
}
```

## fairness-seal.json

```json
{
  "schema": "undercroft-fairness-seal-v1",
  "seal_version": 1,
  "campaign_count": 0,
  "ledger_digest": "<64 hex>",
  "atlas_digest": "<64 hex>",
  "staging_digest": "<64 hex>"
}
```

Digests are SHA-256 hex of the exact UTF-8 file bytes of the ledger, atlas, and staging files respectively (full file, not a subset).

## playtest-journal.jsonl

Each accepted line includes campaign_id, candidate_seed, and accepted=true. Values must agree with staging and ledger selected seeds.
