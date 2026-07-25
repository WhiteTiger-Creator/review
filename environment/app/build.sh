#!/usr/bin/env bash
set -euo pipefail

/opt/julia/bin/julia --startup-file=no -e '
include("/app/src/peak_load.jl")
include("/app/src/policy_load.jl")
include("/app/src/instrument_geom.jl")
include("/app/src/lattice_metric.jl")
include("/app/src/refine_ls.jl")
include("/app/src/report_emit.jl")
'

mkdir -p /app/bin
cat > /app/bin/ndref <<'EOF'
#!/usr/bin/env bash
exec /opt/julia/bin/julia --startup-file=no /app/ndref.jl "$@"
EOF
chmod +x /app/bin/ndref

cat > /app/ndref <<'EOF'
#!/usr/bin/env bash
exec /app/bin/ndref "$@"
EOF
chmod +x /app/ndref
