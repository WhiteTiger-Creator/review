#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/go/bin:/opt/verifier/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

test -f "$ROOT_DIR/reference/a4p/zn_v.go"
test -f "$ROOT_DIR/reference/w3j/wj_r.go"
test -f "$ROOT_DIR/reference/b7k/rg_q.go"
test -f "$ROOT_DIR/reference/c2n/mt_s.go"
test -f "$ROOT_DIR/reference/d9w/yv_h.go"
test -d /app/environment/a4p
test -d /app/environment/w3j
test -d /app/environment/b7k
test -d /app/environment/c2n
test -d /app/environment/d9w

grep -q '^package a4p$' "$ROOT_DIR/reference/a4p/zn_v.go"
grep -q '^package w3j$' "$ROOT_DIR/reference/w3j/wj_r.go"
grep -q '^package b7k$' "$ROOT_DIR/reference/b7k/rg_q.go"
grep -q '^package c2n$' "$ROOT_DIR/reference/c2n/mt_s.go"
grep -q '^package d9w$' "$ROOT_DIR/reference/d9w/yv_h.go"
grep -q 'func zn_v' "$ROOT_DIR/reference/a4p/zn_v.go"
grep -q 'func wj_r' "$ROOT_DIR/reference/w3j/wj_r.go"
grep -q 'func rg_q' "$ROOT_DIR/reference/b7k/rg_q.go"
grep -q 'func mt_s' "$ROOT_DIR/reference/c2n/mt_s.go"
grep -q 'func yv_h' "$ROOT_DIR/reference/d9w/yv_h.go"
grep -q 'func Pack' "$ROOT_DIR/reference/a4p/zn_v.go"
grep -q 'func Replay' "$ROOT_DIR/reference/w3j/wj_r.go"
grep -q 'func Fold' "$ROOT_DIR/reference/b7k/rg_q.go"
grep -q 'func Digest' "$ROOT_DIR/reference/c2n/mt_s.go"
grep -q 'func Emit' "$ROOT_DIR/reference/d9w/yv_h.go"

install -m 0644 "$ROOT_DIR/reference/a4p/zn_v.go" /app/environment/a4p/zn_v.go
install -m 0644 "$ROOT_DIR/reference/w3j/wj_r.go" /app/environment/w3j/wj_r.go
install -m 0644 "$ROOT_DIR/reference/b7k/rg_q.go" /app/environment/b7k/rg_q.go
install -m 0644 "$ROOT_DIR/reference/c2n/mt_s.go" /app/environment/c2n/mt_s.go
install -m 0644 "$ROOT_DIR/reference/d9w/yv_h.go" /app/environment/d9w/yv_h.go

test -f /app/environment/a4p/zn_v.go
test -f /app/environment/w3j/wj_r.go
test -f /app/environment/b7k/rg_q.go
test -f /app/environment/c2n/mt_s.go
test -f /app/environment/d9w/yv_h.go

go build -C /app/environment -o /tmp/xdrv /app/environment/cmd/xdrv
test -x /tmp/xdrv
mkdir -p /app/output
/tmp/xdrv -root /app/environment -out /app/output/invariant.yaml -arm 1
test -f /app/output/invariant.yaml
