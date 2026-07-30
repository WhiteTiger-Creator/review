#!/bin/bash
set -euo pipefail

source /app/etc/site/phase.conf

op_c() {
    local target=$1
    local resolved
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

    if [ -s "$target/.site/pending" ]; then
        "$FIRST_PATH" "$target" || return $?
    fi

    if [ -d "$target/.site/run.lock" ]; then
        "$CORE_PATH" sync "$target" || true
        "$CORE_PATH" finalize "$target"
        "$CORE_PATH" check "$target" >/dev/null 2>&1 || true
        return 0
    fi

    "$CORE_PATH" finalize "$target"
    "$CORE_PATH" check "$target" >/dev/null 2>&1 || true
}

if [ "$#" -ne 1 ]; then
    exit 64
fi
op_c "$1"
