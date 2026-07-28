#!/bin/bash
# Terminal-Bench Canary 9f3a2de1-6b74-4d16-a952-3cc10e84c127
set -euo pipefail

cat > /app/usr/libexec/a1/q1.sh <<'EOF'
#!/bin/bash
set -euo pipefail

source /app/etc/site/phase.conf

op_a() {
    local target=$1
    local resolved
    local lock_path
    local rc

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
    if "$CORE_PATH" check "$target" >/dev/null 2>&1; then
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

    if [ -s "$target/.site/pending" ]; then
        if ! "$CORE_PATH" replay "$target"; then
            : > "$target/.site/ready"
            return 70
        fi
    fi
    if [ -s "$target/.site/pending" ]; then
        if ! "$CORE_PATH" recover "$target"; then
            : > "$target/.site/ready"
            return 70
        fi
    fi
    if "$CORE_PATH" busy "$target"; then
        : > "$target/.site/ready"
        return 73
    fi
    if [ -s "$target/.site/pending" ]; then
        : > "$target/.site/ready"
        return 70
    fi

    "$SECOND_PATH" "$target" || {
        rc=$?
        : > "$target/.site/ready"
        return "$rc"
    }
    if ! "$CORE_PATH" check "$target" >/dev/null; then
        : > "$target/.site/ready"
        return 70
    fi
}

if [ "$#" -ne 1 ]; then
    exit 64
fi
op_a "$1"
EOF

cat > /app/usr/lib/b2/q2.sh <<'EOF'
#!/bin/bash
set -euo pipefail

source /app/etc/site/phase.conf

op_b() {
    local target=$1
    local resolved
    local rc

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
    if [ -s "$target/.site/pending" ]; then
        return 70
    fi

    if ! "$CORE_PATH" scan "$target"; then
        return 70
    fi

    if "$CORE_PATH" publish "$target" >/dev/null 2>&1; then
        "$CORE_PATH" check "$target" >/dev/null
        return $?
    fi

    if ! "$CORE_PATH" commit "$target"; then
        if ! "$CORE_PATH" stage "$target"; then
            return 70
        fi
        if ! "$CORE_PATH" commit "$target"; then
            : > "$target/.site/ready"
            return 70
        fi
    fi
    if [ -s "$target/.site/pending" ]; then
        : > "$target/.site/ready"
        return 70
    fi
    if "$CORE_PATH" busy "$target"; then
        : > "$target/.site/ready"
        return 73
    fi

    "$THIRD_PATH" "$target" || {
        rc=$?
        : > "$target/.site/ready"
        return "$rc"
    }
    if ! "$CORE_PATH" check "$target" >/dev/null; then
        : > "$target/.site/ready"
        return 70
    fi
}

if [ "$#" -ne 1 ]; then
    exit 64
fi
op_b "$1"
EOF

cat > /app/opt/c3/exec/q3.sh <<'EOF'
#!/bin/bash
set -euo pipefail

source /app/etc/site/phase.conf

op_c() {
    local target=$1
    local resolved
    local rc

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
    if "$CORE_PATH" check "$target" >/dev/null 2>&1; then
        return 0
    fi

    if [ -s "$target/.site/pending" ]; then
        "$FIRST_PATH" "$target" || {
            rc=$?
            return "$rc"
        }
        if ! "$CORE_PATH" check "$target" >/dev/null; then
            : > "$target/.site/ready"
            return 70
        fi
        return 0
    fi

    if "$CORE_PATH" publish "$target" >/dev/null 2>&1; then
        "$CORE_PATH" check "$target" >/dev/null
        return $?
    fi

    "$FIRST_PATH" "$target" || {
        rc=$?
        return "$rc"
    }
    if ! "$CORE_PATH" check "$target" >/dev/null; then
        : > "$target/.site/ready"
        return 70
    fi
}

if [ "$#" -ne 1 ]; then
    exit 64
fi
op_c "$1"
EOF

chmod 0755 \
    /app/usr/libexec/a1/q1.sh \
    /app/usr/lib/b2/q2.sh \
    /app/opt/c3/exec/q3.sh
