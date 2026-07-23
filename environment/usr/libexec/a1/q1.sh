#!/bin/bash
set -euo pipefail

source /app/etc/site/phase.conf

op_a() {
    local target=$1
    local resolved

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
    "$CORE_PATH" probe "$target"
    "$CORE_PATH" scan "$target"
}

if [ "$#" -ne 1 ]; then
    exit 64
fi
op_a "$1"
