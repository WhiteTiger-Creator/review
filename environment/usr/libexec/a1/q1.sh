#!/bin/bash
set -euo pipefail

source /app/etc/site/phase.conf

op_a() {
    local target=$1
    local resolved
    local lock_path
    local marker

    if [ ! -x "$CORE_PATH" ]; then
        return 69
    fi
    if [ ! -d "$target" ] || [ -L "$target" ]; then
        return 66
    fi
    resolved=$(readlink -f -- "$target")
    if [ "$resolved" = "/" ]; then
        return 66
    fi
    if [ ! -d "$resolved/.site" ] || [ ! -d "$resolved/payload" ]; then
        return 66
    fi
    umask 077
    target=$resolved

    "$CORE_PATH" probe "$target" || return 66
    if "$CORE_PATH" busy "$target"; then
        return 73
    fi

    marker=$(tr -d '\n' < "$target/.site/ready" 2>/dev/null || true)
    if [ "$marker" = "1" ]; then
        return 0
    fi

    lock_path="$target/.site/run.lock"
    if ! mkdir "$lock_path" 2>/dev/null; then
        if "$CORE_PATH" check "$target" >/dev/null 2>&1; then
            return 0
        fi
        return 75
    fi
    trap 'rmdir "$lock_path" 2>/dev/null || true' RETURN

    "$CORE_PATH" recover "$target"
    "$SECOND_PATH" "$target"
    "$CORE_PATH" finalize "$target"
}

if [ "$#" -ne 1 ]; then
    exit 64
fi
op_a "$1"
