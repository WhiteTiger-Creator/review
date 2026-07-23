#!/bin/bash
# Terminal-Bench Canary 9f3a2de1-6b74-4d16-a952-3cc10e84c127
set -euo pipefail

cat > /app/usr/libexec/a1/q1.sh <<'EOF'
#!/bin/bash
set -euo pipefail

source /app/etc/site/phase.conf

op_a() {
    local target=$1
    local lock_path
    local rc

    "$CORE_PATH" probe "$target" || return 66
    if "$CORE_PATH" busy "$target"; then
        return 73
    fi
    if "$CORE_PATH" check "$target" >/dev/null 2>&1; then
        return 0
    fi

    lock_path="$target/.site/run.lock"
    if ! mkdir "$lock_path" 2>/dev/null; then
        return 75
    fi
    trap 'rmdir "$lock_path" 2>/dev/null || true' RETURN

    : > "$target/.site/ready"
    if ! "$CORE_PATH" replay "$target"; then
        return 70
    fi
    if "$CORE_PATH" busy "$target"; then
        return 73
    fi

    "$SECOND_PATH" "$target" || {
        rc=$?
        : > "$target/.site/ready"
        return "$rc"
    }
    "$CORE_PATH" check "$target" >/dev/null
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
    local rc

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
    if ! "$CORE_PATH" stage "$target"; then
        return 70
    fi
    if ! "$CORE_PATH" commit "$target"; then
        : > "$target/.site/ready"
        return 70
    fi
    if [ -s "$target/.site/pending" ]; then
        : > "$target/.site/ready"
        return 70
    fi

    "$THIRD_PATH" "$target" || {
        rc=$?
        : > "$target/.site/ready"
        return "$rc"
    }
    "$CORE_PATH" check "$target" >/dev/null
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
    local rc

    "$CORE_PATH" probe "$target" || return 66
    if "$CORE_PATH" busy "$target"; then
        return 73
    fi
    if "$CORE_PATH" check "$target" >/dev/null 2>&1; then
        return 0
    fi

    if [ ! -d "$target/.site/run.lock" ]; then
        "$FIRST_PATH" "$target" || {
            rc=$?
            return "$rc"
        }
        "$CORE_PATH" check "$target" >/dev/null
        return $?
    fi

    if [ -s "$target/.site/pending" ]; then
        : > "$target/.site/ready"
        return 70
    fi
    if ! "$CORE_PATH" publish "$target"; then
        : > "$target/.site/ready"
        return 70
    fi
    if "$CORE_PATH" busy "$target"; then
        : > "$target/.site/ready"
        return 73
    fi
    "$CORE_PATH" check "$target" >/dev/null
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
