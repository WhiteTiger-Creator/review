#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_ROOT="/app/environment"

require_nonempty() {
  local path="$1"
  if [[ ! -s "$path" ]]; then
    echo "preflight: empty frontier file $path" >&2
    exit 1
  fi
}

require_pattern() {
  local path="$1"
  local pattern="$2"
  if ! grep -q "$pattern" "$path"; then
    echo "preflight: $path missing pattern $pattern" >&2
    exit 1
  fi
}

check_reference_bundle() {
  require_nonempty "$ROOT_DIR/reference/q2_w3.cpp"
  require_nonempty "$ROOT_DIR/reference/m5_norm.cpp"
  require_nonempty "$ROOT_DIR/reference/reloc_fold.cpp"
  require_nonempty "$ROOT_DIR/reference/v8_emit.cpp"
  require_nonempty "$ROOT_DIR/reference/bank_cache.cpp"
  require_nonempty "$ROOT_DIR/reference/main.cpp"
  require_nonempty "$ROOT_DIR/reference/verify_ob9_d9.sh"
  require_nonempty "$ROOT_DIR/reference/g09_chk.sh"
  require_pattern "$ROOT_DIR/reference/q2_w3.cpp" "key_text"
  require_pattern "$ROOT_DIR/reference/reloc_fold.cpp" "reloc_xor"
  require_pattern "$ROOT_DIR/reference/v8_emit.cpp" "cross_weight"
  require_pattern "$ROOT_DIR/reference/bank_cache.cpp" "active_epoch"
  require_pattern "$ROOT_DIR/reference/main.cpp" "apply_od_margins"
}

check_installed_frontier() {
  local q2="$ENV_ROOT/r3k/src/q2_w3.cpp"
  local reloc="$ENV_ROOT/w7p/src/reloc_fold.cpp"
  local v8="$ENV_ROOT/j2n/src/v8_emit.cpp"
  local bank="$ENV_ROOT/s4d/src/bank_cache.cpp"
  local main="$ENV_ROOT/hs_driver/src/main.cpp"
  require_nonempty "$q2"
  require_nonempty "$reloc"
  require_nonempty "$v8"
  require_nonempty "$bank"
  require_nonempty "$main"
  require_pattern "$q2" "key_text"
  require_pattern "$reloc" "reloc_xor"
  require_pattern "$v8" "cross_weight"
  require_pattern "$bank" "active_epoch"
  require_pattern "$main" "apply_od_margins"
}

check_output_contract() {
  local doc="/app/output/proof_certificate_bundle.tar.json"
  require_nonempty "$doc"
  "$ENV_ROOT/tooling/verify_ob9_d9.sh" --from "$doc"
}

case "${1:-reference}" in
  reference)
    check_reference_bundle
    ;;
  installed)
    check_installed_frontier
    ;;
  output)
    check_output_contract
    ;;
  *)
    echo "preflight: unknown stage $1" >&2
    exit 2
    ;;
esac
