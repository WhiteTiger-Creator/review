#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/go/bin:/opt/verifier/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

test -f "$ROOT_DIR/reference/n7/scr_n.go"
test -f "$ROOT_DIR/reference/p3/lat_p.go"
test -f "$ROOT_DIR/reference/w9/jw_w.go"
test -f "$ROOT_DIR/reference/r2/prf_h.go"
test -f "$ROOT_DIR/reference/internal/persist.go"
test -f "$ROOT_DIR/reference/ocnfix/stab_a.go"
test -f "$ROOT_DIR/reference/ocnfix/stab_b.go"
test -f "$ROOT_DIR/reference/ocnfix/stab_c.go"
test -f "$ROOT_DIR/reference/ocneval/boot.go"

install -m 0644 "$ROOT_DIR/reference/n7/scr_n.go" /app/environment/n7/scr_n.go
install -m 0644 "$ROOT_DIR/reference/p3/lat_p.go" /app/environment/p3/lat_p.go
install -m 0644 "$ROOT_DIR/reference/w9/jw_w.go" /app/environment/w9/jw_w.go
install -m 0644 "$ROOT_DIR/reference/r2/prf_h.go" /app/environment/r2/prf_h.go
install -m 0644 "$ROOT_DIR/reference/internal/persist.go" /app/environment/internal/persist.go
install -m 0644 "$ROOT_DIR/reference/ocnfix/stab_a.go" /app/environment/ocnfix/stab_a.go
install -m 0644 "$ROOT_DIR/reference/ocnfix/stab_b.go" /app/environment/ocnfix/stab_b.go
install -m 0644 "$ROOT_DIR/reference/ocnfix/stab_c.go" /app/environment/ocnfix/stab_c.go
install -m 0644 "$ROOT_DIR/reference/ocneval/boot.go" /app/environment/ocneval/boot.go

go build -C /app/environment -o /tmp/bn_run /app/environment/cmd/bn_run
test -x /tmp/bn_run
mkdir -p /app/output
/tmp/bn_run -root /app/environment -out /app/output/invariant_proof_log.json
test -f /app/output/invariant_proof_log.json
