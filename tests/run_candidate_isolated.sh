#!/usr/bin/env bash
# Restricted candidate runner for the PostgreSQL bootstrap policy planner.
#
# Usage: run_candidate_isolated.sh <binary> -- [args...]
#
# The native candidate binary is executed as an unprivileged user
# (pgcandidate, uid 9001) with cleared supplementary groups. Every local
# input file argument (--yaml, --toml, --extension-catalog,
# --setting-catalog) is remapped into a world-readable, root-owned input
# jail (a private copy of the requested file); --sql-out and --plan-out are
# remapped into a candidate-owned output jail whose produced files are
# copied back to the host paths afterwards. --policy-url is left untouched
# since it names a localhost HTTP endpoint, not a filesystem path. This
# guarantees the candidate never reads /tests or /solution and never writes
# outside its jail.
set -euo pipefail

if [[ "${1:-}" == "" || "${2:-}" != "--" ]]; then
  echo "usage: run_candidate_isolated.sh <binary> -- [args...]" >&2
  exit 2
fi

CANDIDATE_BIN="$1"
shift 2

if [[ ! -x "$CANDIDATE_BIN" ]]; then
  echo "candidate binary is missing or not executable: $CANDIDATE_BIN" >&2
  exit 2
fi

CANDIDATE_UID="${CANDIDATE_UID:-9001}"
CANDIDATE_USER="${CANDIDATE_USER:-pgcandidate}"
WORK_ROOT="$(mktemp -d /var/tmp/pg-candidate/work.XXXXXX 2>/dev/null || mktemp -d /tmp/pg-candidate-work.XXXXXX)"
OUTPUT_DIR="$WORK_ROOT/output"
INPUT_DIR="$WORK_ROOT/input"
WRITABLE_DIR="$WORK_ROOT/writable"
mkdir -p "$OUTPUT_DIR" "$INPUT_DIR" "$WRITABLE_DIR"
chmod 755 "$WORK_ROOT" "$INPUT_DIR" "$OUTPUT_DIR" "$WRITABLE_DIR"

declare -a HOST_OUTPUT_MAP=()

cleanup() {
  local entry host jail
  for entry in "${HOST_OUTPUT_MAP[@]:-}"; do
    [[ -z "$entry" ]] && continue
    host="${entry%%=*}"
    jail="${entry#*=}"
    if [[ -f "$jail" ]]; then
      mkdir -p "$(dirname "$host")"
      cp -f "$jail" "$host" 2>/dev/null || true
    else
      rm -f "$host" 2>/dev/null || true
    fi
  done
  rm -rf "$WORK_ROOT"
}
trap cleanup EXIT

ensure_candidate_user() {
  if id -u "$CANDIDATE_USER" >/dev/null 2>&1; then
    return 0
  fi
  if command -v useradd >/dev/null 2>&1; then
    useradd --system --no-create-home --uid "$CANDIDATE_UID" --shell /usr/sbin/nologin "$CANDIDATE_USER" 2>/dev/null || true
  fi
}

INPUT_FLAGS=("--yaml" "--toml" "--extension-catalog" "--setting-catalog")
OUTPUT_FLAGS=("--sql-out" "--plan-out")
INPUT_COUNT=0

declare -a JAIL_ARGS=()
prev=""
for arg in "$@"; do
  matched_input=0
  for flag in "${INPUT_FLAGS[@]}"; do
    if [[ "$prev" == "$flag" ]]; then
      matched_input=1
      break
    fi
  done
  if [[ "$matched_input" == "1" ]]; then
    if [[ -f "$arg" ]]; then
      INPUT_COUNT=$((INPUT_COUNT + 1))
      base="$(basename "$arg")"
      jail_path="$INPUT_DIR/in-$INPUT_COUNT-$base"
      cp -a "$arg" "$jail_path"
      chmod a+r "$jail_path"
      JAIL_ARGS+=("$jail_path")
    else
      JAIL_ARGS+=("$arg")
    fi
    prev=""
    continue
  fi

  matched_output=0
  for flag in "${OUTPUT_FLAGS[@]}"; do
    if [[ "$prev" == "$flag" ]]; then
      matched_output=1
      break
    fi
  done
  if [[ "$matched_output" == "1" ]]; then
    base="$(basename "$arg")"
    jail_path="$OUTPUT_DIR/$base"
    HOST_OUTPUT_MAP+=("$arg=$jail_path")
    mkdir -p "$(dirname "$arg")"
    rm -f "$arg"
    JAIL_ARGS+=("$jail_path")
    prev=""
    continue
  fi

  is_flag=0
  for flag in "${INPUT_FLAGS[@]}" "${OUTPUT_FLAGS[@]}"; do
    if [[ "$arg" == "$flag" ]]; then
      is_flag=1
      break
    fi
  done
  if [[ "$is_flag" == "1" ]]; then
    JAIL_ARGS+=("$arg")
    prev="$arg"
    continue
  fi
  JAIL_ARGS+=("$arg")
  prev=""
done

ensure_candidate_user
chown -R "$CANDIDATE_UID:$CANDIDATE_UID" "$OUTPUT_DIR" "$WRITABLE_DIR" 2>/dev/null || true
# Input jail stays root-owned but world-readable.
chmod -R a+rX "$INPUT_DIR" 2>/dev/null || true
chmod a+rx "$CANDIDATE_BIN" 2>/dev/null || true

# Soft-deny other-read on verifier trees.
for deny in /tests /solution /logs/verifier; do
  if [[ -e "$deny" ]]; then
    chmod o-rwx "$deny" 2>/dev/null || true
  fi
done

run_as_candidate() {
  if command -v setpriv >/dev/null 2>&1; then
    setpriv \
      --reuid="$CANDIDATE_UID" \
      --regid="$CANDIDATE_UID" \
      --clear-groups \
      --inh-caps=-all \
      --ambient-caps=-all \
      --nnp \
      -- "$@"
    return $?
  fi
  if command -v runuser >/dev/null 2>&1 && id -u "$CANDIDATE_USER" >/dev/null 2>&1; then
    runuser -u "$CANDIDATE_USER" -- "$@"
    return $?
  fi
  "$@"
  return $?
}

# Isolation self-check (author-only; not a pytest item).
if [[ "${CANDIDATE_ISOLATION_SELFCHECK:-}" == "1" ]]; then
  set +e
  run_as_candidate bash -c '
    uid=$(id -u)
    test "$uid" -ne 0 || exit 11
    test ! -r /tests/test_outputs.py || exit 12
    test ! -r /tests/helpers/projections.py || exit 13
    test ! -r /solution/solve.sh || exit 15
    test ! -r /solution/reference_model/planner.py || exit 16
    test ! -r /logs/verifier/reward.txt || exit 17
    echo ISOLATION_OK
  '
  rc=$?
  set -e
  exit "$rc"
fi

cd "$WRITABLE_DIR"
unset PYTHONPATH
export HOME="$WRITABLE_DIR"
export TMPDIR="$WRITABLE_DIR"
set +e
run_as_candidate "$CANDIDATE_BIN" "${JAIL_ARGS[@]}"
rc=$?
set -e
exit "$rc"

