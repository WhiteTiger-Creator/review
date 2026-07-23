# T Policy

Thermal DTMC workflow for pile-layer certification. Covers microbial heat-balance residuals under floating-point tolerances, schedule ranking, independent seal replay, and closed-algebra YAML seals.

Residual and packing obligations are normative in `/app/environment/docs/t_policy.rst` and mirrored in `/app/environment/tools/digest_pack.py`. Capacity and reclaim tables live in `/app/environment/data/pack_c/nrg.toml`. Ranking multipliers live in the same energy table. The sealed bundle is a YAML object whose rows field is a list of row objects; each digest_hex and the top-level seal_hex are 64-character lowercase hex strings. The aeration-order list in `/app/environment/data/perm_tbl.toml` contributes 5 entries, which together with the training and stress arms form the closed fixture set.
