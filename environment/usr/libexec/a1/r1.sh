#!/bin/bash
set -euo pipefail

source /app/etc/site/phase.conf

op_d() {
    local target=$1
    "$CORE_PATH" inspect "$target"
    if [ -f "$target/.site/events" ]; then
        wc -l < "$target/.site/events"
    else
        printf '0\n'
    fi
}

if [ "$#" -ne 1 ]; then
    exit 64
fi
op_d "$1"
