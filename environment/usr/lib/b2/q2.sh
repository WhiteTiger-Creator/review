#!/bin/bash
set -euo pipefail

source /app/etc/site/phase.conf

op_b() {
    local target=$1
    local resolved

    if [ ! -x "$CORE_PATH" ]; then
        return 69
    fi
    if [ ! -d "$target" ] || [ -L "$target" ]; then
        return 66
    fi
    resolved=$(readlink -f -- "$target")
    if [ ! -d "$resolved/.site" ] || [ ! -d "$resolved/payload" ]; then
        return 66
    fi
    umask 077
    target=$resolved
    "$CORE_PATH" scan "$target"
    "$CORE_PATH" stage "$target"
    "$CORE_PATH" commit "$target"
    "$CORE_PATH" replay "$target"
}

if [ "$#" -ne 1 ]; then
    exit 64
fi
op_b "$1"
