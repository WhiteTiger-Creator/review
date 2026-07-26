#!/bin/bash
set -euo pipefail

solution_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

install -m 0644 "$solution_dir/reference/peak_load.jl" /app/src/peak_load.jl
install -m 0644 "$solution_dir/reference/policy_load.jl" /app/src/policy_load.jl
install -m 0644 "$solution_dir/reference/instrument_geom.jl" /app/src/instrument_geom.jl
install -m 0644 "$solution_dir/reference/lattice_metric.jl" /app/src/lattice_metric.jl
install -m 0644 "$solution_dir/reference/refine_ls.jl" /app/src/refine_ls.jl
install -m 0644 "$solution_dir/reference/report_emit.jl" /app/src/report_emit.jl
install -m 0644 "$solution_dir/reference/ndref.jl" /app/ndref.jl

install -m 0644 /app/data/sealed/production_policy.toml /app/config/refine_policy.toml

bash /app/build.sh
/app/bin/ndref --refined /tmp/oracle-refined.json --report /tmp/oracle-report.json
