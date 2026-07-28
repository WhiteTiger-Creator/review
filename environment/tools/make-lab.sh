#!/bin/bash
set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "usage: make-lab.sh TARGET PROFILE [LAYOUT]" >&2
    exit 64
fi

target=$1
profile=$2
layout=${3:-a}

rm -rf "$target"
mkdir -p "$target/payload/nested" "$target/namespace/retired" "$target/.site"
printf 'alpha payload\n' > "$target/payload/alpha.txt"
printf 'nested payload\n' > "$target/payload/nested/beta.txt"
printf 'old namespace entry\n' > "$target/namespace/retired/link"
printf '0\n' > "$target/.site/busy"
printf '0\n' > "$target/.site/sequence"
: > "$target/.site/events"
: > "$target/.site/ready"

if [ "$layout" = "b" ]; then
    mkdir -p "$target/payload/archive"
    printf 'archived payload\n' > "$target/payload/archive/gamma.txt"
fi

write_clean_markers() {
    local count fingerprint
    /app/bin/site-core scan "$target" >/dev/null
    count=$(awk -F= '/^count=/{print $2; exit}' "$target/.site/observed")
    fingerprint=$(awk -F= '/^fingerprint=/{print $2; exit}' "$target/.site/observed")
    printf 'count=%s\nfingerprint=%s\ngeneration=1\n' "$count" "$fingerprint" \
        > "$target/.site/account"
    printf 'count=%s\nfingerprint=%s\ngeneration=1\n' "$count" "$fingerprint" \
        > "$target/.site/slot-a"
    : > "$target/.site/events"
    printf 'published\n' > "$target/.site/status"
    printf '1\n' > "$target/.site/ready"
}

case "$profile" in
    clean)
        : > "$target/.site/pending"
        rm -f "$target/namespace/retired/link"
        write_clean_markers
        ;;
    deferred|residue)
        printf 'drop:retired/link\n' > "$target/.site/pending"
        printf 'count=99\nfingerprint=stale\ngeneration=1\n' > "$target/.site/account"
        printf 'scanned\n' > "$target/.site/status"
        if [ "$profile" = "residue" ]; then
            printf '1\n' > "$target/.site/ready"
        fi
        ;;
    mixed)
        printf 'note:audit/trail\ndrop:retired/link\n' > "$target/.site/pending"
        printf 'count=99\nfingerprint=stale\ngeneration=1\n' > "$target/.site/account"
        printf 'scanned\n' > "$target/.site/status"
        ;;
    stale)
        : > "$target/.site/pending"
        printf 'count=99\nfingerprint=stale\ngeneration=1\n' > "$target/.site/account"
        printf 'accounted\n' > "$target/.site/status"
        ;;
    early)
        printf 'drop:retired/link\n' > "$target/.site/pending"
        printf 'prepared\n' > "$target/.site/status"
        ;;
    malformed)
        : > "$target/.site/pending"
        printf 'unparseable\n' > "$target/.site/slot-a"
        printf 'staged\n' > "$target/.site/status"
        ;;
    busy)
        printf '1\n' > "$target/.site/busy"
        printf 'drop:retired/link\n' > "$target/.site/pending"
        printf 'held\n' > "$target/.site/status"
        ;;
    drift)
        : > "$target/.site/pending"
        rm -f "$target/namespace/retired/link"
        write_clean_markers
        printf 'count=99\nfingerprint=stale\ngeneration=1\n' > "$target/.site/account"
        ;;
    *)
        echo "unknown profile: $profile" >&2
        exit 64
        ;;
esac
