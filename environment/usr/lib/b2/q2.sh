#!/bin/bash
set -euo pipefail

source /app/etc/site/phase.conf

op_b() {
    local target=$1
    local resolved
    local attempts

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

    "$CORE_PATH" probe "$target" || return 66
    if "$CORE_PATH" busy "$target"; then
        return 73
    fi

    attempts=0
    while [ "$attempts" -lt 2 ]; do
        "$CORE_PATH" sync "$target"
        if [ -s "$target/.site/slot-a" ] || [ -s "$target/.site/slot-b" ]; then
            :
        else
            "$CORE_PATH" stage "$target" || true
        fi
        if "$CORE_PATH" commit "$target"; then
            "$THIRD_PATH" "$target"
            return $?
        fi
        attempts=$((attempts + 1))
    done
    return 70
}

if [ "$#" -ne 1 ]; then
    exit 64
fi
op_b "$1"
