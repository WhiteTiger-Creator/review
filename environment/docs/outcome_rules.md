# Outcome rules

## CLI

`/app/admit-repo --repo <path> --release-ref <ref> --policy /app/policy/signer_matrix.toml`

- `--rules /app/policy/release_rules.toml`
- `--report /app/output/object_trust_report.json`
- `--key-home /app/environment/fixtures/keys/gnupg`

On success the tool exits 0; on policy rejection 2 (report still written); on usage errors 1.

When exit code is `0`, `admitted` must be true. When exit code is `2`, `admitted` must be false.

## Report schema

The report at `/app/output/object_trust_report.json` contains

- `schema_version` (integer, must be 1)
- `repo_path` (string)
- `release_ref` (string)
- `admitted` (boolean)
- `walk_records` (array of objects with `ordinal`, `kind`, `object_id`)
- `rejection` (object with `code`, `detail` when not admitted)
- `walk_digest` (64 lowercase hex chars)

## Walk digest

`walk_digest` is SHA-256 over UTF-8 lines built as ordinal, kind, and object_id separated by single colons, joined with newlines in walk order (computed by the tool on write).

## Rejection codes

| Code | Meaning |
|------|---------|
| RPL_MAP | Replace ref mapping present but walk closure does not cover rewritten objects; when this applies, rejection code must be RPL_MAP. |
| SHLW_GAP | Shallow boundary leaves ancestry incomplete under release policy; when this applies, rejection code must be SHLW_GAP. |
| TAG_ANCHOR | Annotated tag or commit anchor does not cover required closure; when this applies, rejection code must be TAG_ANCHOR. |
| FMT_LANE | Signature format lane does not match signer matrix for observed principal |

## Policy

Signer matrix at `/app/policy/signer_matrix.toml` lists principals, fingerprints, and format lanes. Release rules at `/app/policy/release_rules.toml` toggle `require_commit_coverage`, `reject_shallow_gap`, and `honor_replace`.

## Threat outcomes

Admission succeeds only when every security-relevant commit in the release closure is signed by an allowed principal lane. Replace refs, shallow files, tag indirection, and format transitions must not hide unsigned objects. HEAD-only success is insufficient.

Fixture ids are listed in `case_ids.txt` under `/app/environment/docs/`.

## Held-out replay (verifier)

`ship_line` must match the `alt_branch` value in ref_matrix when replay runs. `git_trust_replay_perm` must refer to the scratch directory `/tmp/git_trust_replay_perm` where the mutator writes its copy. The `replay_mutator` script must copy a fixture repo tree to that path and rename the release branch to `ship_line`. `arm_rpl_a7` must be the first entry in case_ids.txt (replace-ref fixture arm under fixtures/repos).

`python3 /app/environment/fixtures/gen/replay_mutator.py /app/environment/fixtures/repos/arm_rpl_a7 /tmp/git_trust_replay_perm --release-ref release --alt-name ship_line`
