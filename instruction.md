Arm 0763 offline histopathology stain-robustness scoring is baking wrong certificates. Warm calibration looks fine on the scoreboard, but independent catalog-nine replay fails after adversarial stress against both KIDX corpora. Network stays off (`allow_internet = false`); everything needed is already in the image.

Repair the `/app/environment` C++ evaluation workspace so this regenerates a graded bundle with zero obligation-nine violations:

```bash
/app/environment/exec/run_hs_cycle.sh --arm 0763 --all-fixtures
```

Graded artifact: `/app/output/proof_certificate_bundle.tar.json` (must include `arm_id`, `replay_digest`, `bank_fingerprint`, `rows`, `obligation_violations`). `bank_fingerprint` is the eight lowercase hex token from the live stress-epoch OD bank binding and is part of `replay_digest` material. Hand-written bundle JSON is insufficient; fixture edits and stage-only patches also fail grading, which reruns the full HS cycle via `/app/tests/test.sh`. Independent replay (`verify_ob9_d9.sh`) recomputes the digest and obligation-nine count and must exit zero:

```bash
/app/environment/tooling/verify_ob9_d9.sh --from /app/output/proof_certificate_bundle.tar.json
```

Contracts for OD bank epochs, digests (including the bank fingerprint field published after the stress bank epoch), cross-track duties, holdout salt, reloc folds (`reloc_xor` in `/app/environment/schemas/ref_a763.kaitai`), journals, and recovery are in `/app/environment/docs/field_guide.md` and `/app/environment/schemas/contract_annex.yaml`, with `/app/environment/k8m/pair_v7.json`, `/app/environment/k8m/lim_a763.toml`, and `/app/environment/tooling/digest_util.py`. Stage journals under `/app/output/stage/` follow `/app/environment/logging/stage_format.txt`; lane publish tokens must be decimal digit strings (`str.isdigit()`). Playbooks and `/app/environment/docs/r5_link_notes.md` lose when they conflict with the annex.
