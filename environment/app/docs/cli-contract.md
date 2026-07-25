# CLI contract — `/app/bin/ndref`

Powder neutron TOF lattice refinement entrypoint for the crystallography desk.

```
/app/bin/ndref [--peaks PATH] [--instrument PATH] [--structure PATH] [--config PATH] [--refined PATH] [--report PATH]
```

Order free. Pair each flag with a value.

Defaults:

| flag | default |
| --- | --- |
| `--peaks` | `/app/data/sample/peaks.csv` |
| `--instrument` | `/app/data/sample/instrument.json` |
| `--structure` | `/app/data/sample/reference_structure.json` |
| `--config` | `/app/config/refine_policy.toml` |
| `--refined` | `/app/refined_structure.json` |
| `--report` | `/app/refinement_report.json` |

| exit | meaning |
| --- | --- |
| `0` | valid pack, zero rejected peaks; write both artifacts; empty stdout |
| `1` | valid pack, ≥1 rejected peak; still write both; empty stdout |
| `2` | fatal CLI/input/policy/validation; non-empty stderr; do not create or clobber `--refined` / `--report` |

Fatal CLI: unknown flag, duplicate flag, missing value, path collision among the six roles.

Fatal input/policy (exit `2`, same no-clobber rule): live config keys invalid or `schema_version != 2`, live config not byte-equal to sealed production policy at `/app/data/sealed/production_policy.toml` when `--config` is the default live path `/app/config/refine_policy.toml`, peaks CSV header names/order wrong, duplicate `peak_id`, empty pack, non-finite numerics, instrument JSON missing/invalid fields, structure JSON missing/invalid fields, unsupported `crystal_system`, reference angles that violate the crystal-system locks in `structure-format.md`, unsupported `admit_mode` / `extinction_mode`, singular normal equations, fewer than `min_admitted_peaks` peaks remaining for a fit pass.

Atomic temp-then-rename writes. Create parent directories on successful emit only.
