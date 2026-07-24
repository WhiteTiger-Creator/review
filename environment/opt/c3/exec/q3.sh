#!/bin/bash
set -euo pipefail

source /app/etc/site/phase.conf

op_c() {
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
    printf '1\n' > "$target/.site/ready"
}

if [ "$#" -ne 1 ]; then
    exit 64
fi
op_c "$1"
