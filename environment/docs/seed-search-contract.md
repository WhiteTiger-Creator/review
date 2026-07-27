# Seed search

For each campaign, scan seeds in half-open range:

`[search_origin, search_origin + search_limit)`

Select the **first** seed whose generated dungeon passes reachability, pacing, treasure, and threat checks simultaneously. Do not prefer a later fair seed once an earlier one qualifies.

If no seed passes, the playtest must fail (non-zero exit) and must not write a successful seal claiming fairness.

Journal lines (JSONL) record at least: campaign_id, candidate_seed, accepted (bool). Accepted seed lines must appear once per campaign on success and must match the staging `candidate_seed` values.

Hidden verifier-fixtures may include an eval_pool of candidate seeds for randomized checks and additional hold-out campaign profiles.
