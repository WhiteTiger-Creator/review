#!/bin/bash
set -euo pipefail

op_e() {
    local target=$1
    local source_file="$target/.site/events"
    local archive_file="$target/.site/events.previous"
    if [ -s "$source_file" ]; then
        cp --preserve=mode "$source_file" "$archive_file"
        : > "$source_file"
    fi
}

if [ "$#" -ne 1 ]; then
    exit 64
fi
op_e "$1"
