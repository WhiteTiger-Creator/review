An indie dungeon crawl studio runs terminal playtest campaigns over procedurally generated undercroft levels. The working simulator under /app already builds deterministic maps from seeds and exposes a playfield graph for route inspection. The studio still needs a fairness playtest planner that searches candidate seeds until simultaneous reachability, pacing, treasure-balance, and threat-curve invariants hold for each campaign, then publishes durable playtest artifacts through a staging snapshot.

Implement the undercroft-fairness CLI capability so operators can run a multi-campaign playtest tick that materializes:

- /app/state/seed-hunt-staging.json
- /app/output/seed-ledger.json
- /app/output/route-atlas.json
- /app/output/fairness-seal.json
- /app/state/playtest-journal.jsonl

Invoke the planner as:

/app/bin/undercroft-fairness playtest --campaigns /app/fixtures/campaigns --ledger /app/output/seed-ledger.json --atlas /app/output/route-atlas.json --seal /app/output/fairness-seal.json --journal /app/state/playtest-journal.jsonl

Contracts governing map generation, win-condition style route checks, pacing gaps along the critical path, treasure density bands, threat budgets, seed search windows, staging-then-export publish rules, and seal digests live under:

- /app/docs/playtest-workflow.md
- /app/docs/cartograph-contract.md
- /app/docs/reachability-pacing-contract.md
- /app/docs/treasure-threat-contract.md
- /app/docs/seed-search-contract.md
- /app/docs/staging-export-contract.md
- /app/docs/artifact-seal-contract.md

Campaign JSON profiles under /app/fixtures/campaigns define board size, entity counts, invariant thresholds, and each campaign search_origin plus search_limit. Outputs must be deterministic for identical campaign inputs. Rebuild with /app/scripts/build.sh before grading runs.
