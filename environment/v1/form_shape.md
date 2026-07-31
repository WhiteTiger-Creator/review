# Terminal artifact shapes

## `/app/output/adv_report.json`

The driver writes a top-level object with `seed` and `runs`. Each `runs[]` entry reports these fields.

- `fixture_id` means the record `id` field from the fixture that was run (`case_a` is the demo fixture; `h1`, `h2`, and `h3` are held-out fixtures under `k2/xtra/`)
- `flip_hit` means `1` when the chosen candidate label equals `flip_target` from the policy and the base label did not, else `0`
- `octet_spend` means the encoded wiresize of the selected candidate delta in octets
- `base_label` means the label of the original record after defense preprocessing
- `adv_label` means the label of the selected candidate after defense preprocessing
- `cand_digest` means a 16-character lowercase hex digest of the selected candidate JSON (canonical key order)
- `walk_digest` means a 16-character lowercase hex digest of the visitation order string for that fixture
- `side_hex` means a 16-character lowercase hex of `fixture_id|octet_spend|cand_digest`
- `seed` means the RNG seed copied from the policy file

The shipped CLI processes every `*.json` under the `--cases` directory, then every `k2/xtra/*.json` listed by the policy `xtra_dir`. The top-level object shape is a `seed` integer plus a `runs` array of per-fixture objects.

## Caps

For every `runs[]` entry, `flip_hit` must be `1` and `octet_spend` must be less than or equal to `octet_budget` from the policy. Perturbed records must remain schema-valid (every column present, `mut` marks respected, numeric `v` values).

## Wiresize accounting

Encoded wiresize for a candidate is the sum, over columns whose `v` differs from the base record, of `(2 + w)` where `w` is that column's width integer. Unchanged columns contribute `0`.

## Record input shape

Fixtures under `/app/environment/k2/` are JSON objects with `id`, `cols`, and `meta`.
`cols` maps column names (`f0`, `f1`, `f2`, `f3`) to objects with numeric `v`, integer width `w`, and boolean `mut`.
When `mut` is false, that column must keep its base `v` in any successful candidate.
`meta.mutable` lists column names that may be edited.

`cand_digest` hashes the candidate JSON after compact sorted-key canonicalization (equivalent to `jq -c -S .`) with a trailing newline, then takes the first 16 lowercase hex characters of sha256.

## Digests

`cand_digest`, `walk_digest`, and `side_hex` are the first 16 lowercase hex characters of the sha256 digest over the UTF-8 input string. `walk_digest` hashes the comma-joined candidate file basenames in visitation order. Digests must be stable across wipe-and-rerun for the same policy seed.

## Visitation order

Candidate visitation is not filesystem glob order. For each candidate file basename under the fixture candidate directory, compute the UTF-8 string `seed:basename` where `seed` is the policy seed printed as decimal text (for example `42`), then take the full lowercase hex sha256 of that string. Sort candidate basenames by that hex key ascending (`LC_ALL=C` byte order). Emit basenames in that sorted order. `order_csv` is those basenames joined with commas, and `walk_digest` is the 16-hex digest of that `order_csv` string.

## `/app/output/spend_trace.jsonl`

One JSON object per line. Field meanings follow.

- `t` means monotonic tick within the fixture walk
- `fixture_id` means the fixture id for the tick
- `cand_name` means the candidate basename considered at that tick
- `spend` means encoded wiresize for that candidate
- `picked` means `1` when this candidate was selected for the report, else `0`

For each `fixture_id`, exactly one trace line has `picked` equal to `1`, and that line's `spend` must equal `octet_spend` in the matching `runs[]` entry.

## `/app/output/walk_side.jsonl`

One JSON object per fixture. Field meanings follow.

- `fixture_id` means the fixture id
- `order_csv` means the comma-joined visitation order of candidate basenames
- `walk_digest` means the digest of `order_csv` using the same rule as the report field

For each fixture, `walk_digest` in `walk_side.jsonl` must equal `walk_digest` in the matching `runs[]` entry.

## Advisory probes

Files under `/app/output/probe/` are not authoritative.
