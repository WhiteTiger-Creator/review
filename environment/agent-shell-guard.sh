# Keep the terminus interactive tmux bash alive. Agents often type
# `set -e` / `exit $rc` into the pane; either path can tear down the
# session and yield verifier_did_not_run. Harness teardown still uses
# tmux kill-session.
if [ -n "${TMUX:-}" ]; then
  set +e
  IGNOREEOF=100
  exit() { true; }
  set() {
    local -a out=()
    local expecting=""
    local a
    for a in "$@"; do
      if [ "$expecting" = "-o" ]; then
        expecting=""
        [ "$a" = "errexit" ] && continue
        out+=("-o" "$a")
        continue
      fi
      if [ "$expecting" = "+o" ]; then
        expecting=""
        out+=("+o" "$a")
        continue
      fi
      case "$a" in
        -e) ;;
        -o) expecting="-o" ;;
        +o) expecting="+o" ;;
        --)
          out+=("$a")
          expecting="done"
          ;;
        -*)
          local s="${a#-}"
          s="${s//e/}"
          if [ -n "$s" ]; then
            out+=("-$s")
          fi
          ;;
        *) out+=("$a") ;;
      esac
    done
    builtin set "${out[@]}"
  }
fi
