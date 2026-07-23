Produce a sealed thermal-regime certificate for a compost pile heat-balance model under pathogen-kill and combustion-risk limits.

Training schedules can look settled while the stress schedule and aeration-order permutations still violate the probabilistic model-checking algebra. Stage gauges under `/app/output/stage` (files named like train_a.ok) may turn green even when independent certificate replay fails.

train_a is the training arm under the baseline microbial heat schedule. host_b is the stress arm under hostile schedule pressure at host scale. Every aeration-order id in `/app/environment/data/perm_tbl.toml` must also satisfy the closed algebra. Corpus inputs live under `/app/environment/data/pack_c`.

Numeric policy covers residual tolerances, digests, ranking multipliers, journal stitch behavior, and YAML packing. That policy lives in `/app/environment/docs/t_policy.md` with normative detail in `/app/environment/docs/t_policy.rst` (mirrored by `/app/environment/tools/digest_pack.py`). Layer roles are in `/app/environment/docs/module_map.md`. Emit notes are in `/app/environment/docs/hv7_usage.md`.

Update the numerical thermal kernels under `/app/environment` that feed the hv7 certificate sealer so ranking, interlayer mass fold, and seal stitch match the policy. Helpers outside that emit path are not substitutes for those kernels.

Success is `/app/output/invariant_bundle.yaml` with schema_ver, rows (each with arm_id, digest_hex, viol_n, eps_used, seal_mark, stage_mark), plus top-level util_max, seal_hex, and closed_n, matching t_policy.rst. util_max must match the policy-computed peak of joint_use over effective capacity.

Hand-written or static YAML is not sufficient. Regenerate the sealed certificate only through the hv7 path after refreshing the kernels; details are in `/app/environment/docs/hv7_usage.md`. Digests must match independent certificate replay against the live kernels.
