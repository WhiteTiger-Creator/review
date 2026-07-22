The offline lockfile tool under `/app/environment` is drifting in CI.

Repair those Go sources.

Rebuild `/app/bin/depctrl` from `/app/environment` after edits.

Use the build recipe in `/app/environment/docs/phase_contract.md`.

Run `/app/bin/depctrl reconcile --all-mirrors`.

Checks rebuild the binary and rerun that path.

Traces land in `/app/output/traces/`.

`last_run.json` carries `row_n`, `frame_n`, and `cache_hit`.

Journal files live under `/app/output/journal/`.

Seeds live under `/app/environment/data/`.

Seal `/app/output/constraint_report.json`.

It must be a JSON object with a `rows` array.

Each row needs pkg, dep, lo, hi, pre_tok, lift, and row_digest.

Digest construction follows the sha256 rules in the phase contract.

Journal must seal without torn or CRC-mismatched frames in the fold.

Warm cache blobs must stay coherent with the live peer fingerprint and activation map.

Staging output is not the sealed report.

`depctrl status` printing steady is not enough.

Hand-written reports will not pass.
