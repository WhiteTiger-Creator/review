#!/bin/bash
# Terminal-Bench Canary 9f3a2de1-6b74-4d16-a952-3cc10e84c127
set -euo pipefail

python3 <<'PY'
from pathlib import Path

Path("/app/src/fs/walker.cc").write_text(r'''#include "fs/walker.h"

#include "support/files.h"

#include <algorithm>
#include <iomanip>
#include <sstream>
#include <vector>

namespace site {
namespace {

void absorb(std::uint64_t& value, const std::string& text) {
    for (const unsigned char byte : text) {
        value ^= byte;
        value *= 1099511628211ULL;
    }
}

}  // namespace

Scan observe_tree(const std::filesystem::path& root) {
    Scan scan{{}, 1469598103934665603ULL};
    const auto payload = root / "payload";
    std::error_code error;
    if (!std::filesystem::is_directory(payload, error)) {
        return scan;
    }
    std::vector<std::filesystem::path> files;
    for (const auto& entry : std::filesystem::recursive_directory_iterator(payload)) {
        if (!entry.is_regular_file()) {
            continue;
        }
        files.push_back(entry.path());
    }
    for (const auto& file : files) {
        scan.paths.push_back(std::filesystem::relative(file, payload).generic_string());
    }
    std::sort(scan.paths.begin(), scan.paths.end());
    for (const auto& path : scan.paths) {
        absorb(scan.fingerprint, path);
        absorb(scan.fingerprint, read_text(payload / path));
    }
    return scan;
}

std::string render_scan(const Scan& scan) {
    std::ostringstream output;
    output << "count=" << scan.paths.size() << '\n';
    output << "fingerprint=" << std::hex << std::setw(16) << std::setfill('0')
           << scan.fingerprint << '\n';
    for (const auto& path : scan.paths) {
        output << "path=" << path << '\n';
    }
    return output.str();
}

}  // namespace site
''')

Path("/app/src/store/ledger.cc").write_text(r'''#include "store/ledger.h"

#include "model/record.h"
#include "support/clock.h"
#include "support/codec.h"
#include "support/files.h"

#include <iomanip>
#include <sstream>
#include <vector>

namespace site {
namespace {

std::string hex_value(std::uint64_t value) {
    std::ostringstream output;
    output << std::hex << std::setw(16) << std::setfill('0') << value;
    return output.str();
}

std::optional<Candidate> load_candidate(
    const std::filesystem::path& path,
    const Scan& scan
) {
    if (!has_nonempty(path)) {
        return std::nullopt;
    }
    const auto record = decode_record(read_text(path));
    const auto generation = record.number("generation", -1);
    const auto count = record.get("count");
    const auto fingerprint = record.get("fingerprint");
    if (generation < 0 ||
        count != std::to_string(scan.paths.size()) ||
        fingerprint != hex_value(scan.fingerprint)) {
        return std::nullopt;
    }
    return Candidate{generation, count, fingerprint, path};
}

}  // namespace

void stage_candidate(const std::filesystem::path& root, const Scan& scan) {
    const long generation = next_sequence(root);
    Record record;
    record.set("count", std::to_string(scan.paths.size()));
    record.set("fingerprint", hex_value(scan.fingerprint));
    record.set("generation", std::to_string(generation));
    const auto slot = generation % 2 == 0 ? "slot-a" : "slot-b";
    write_atomic(root / ".site" / slot, encode_record(record));
}

std::optional<Candidate> select_candidate(
    const std::filesystem::path& root,
    const Scan& scan
) {
    std::optional<Candidate> selected;
    for (const auto* name : {"slot-a", "slot-b"}) {
        auto candidate = load_candidate(root / ".site" / name, scan);
        if (!candidate) {
            continue;
        }
        if (!selected || candidate->generation > selected->generation) {
            selected = std::move(candidate);
        }
    }
    return selected;
}

void commit_candidate(const std::filesystem::path& root, const Candidate& candidate) {
    Record record;
    record.set("count", candidate.count);
    record.set("fingerprint", candidate.fingerprint);
    record.set("generation", std::to_string(candidate.generation));
    write_atomic(root / ".site" / "account", encode_record(record));
}

bool account_matches(const std::filesystem::path& root, const Scan& scan) {
    const auto record = decode_record(read_text(root / ".site" / "account"));
    return record.get("count") == std::to_string(scan.paths.size()) &&
           record.get("fingerprint") == hex_value(scan.fingerprint) &&
           record.number("generation", -1) >= 0;
}

}  // namespace site
''')

Path("/app/src/support/files.cc").write_text(r'''#include "support/files.h"

#include <fstream>
#include <sstream>
#include <stdexcept>

namespace site {

std::string read_text(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        return "";
    }
    std::ostringstream buffer;
    buffer << input.rdbuf();
    return buffer.str();
}

void write_atomic(const std::filesystem::path& path, const std::string& text) {
    std::error_code exists_error;
    if (std::filesystem::is_regular_file(path, exists_error)) {
        if (read_text(path) == text) {
            return;
        }
    }
    const auto parent = path.parent_path();
    if (!parent.empty()) {
        std::filesystem::create_directories(parent);
    }
    const auto temporary = path.string() + ".new";
    {
        std::ofstream output(temporary, std::ios::binary | std::ios::trunc);
        if (!output) {
            throw std::runtime_error("cannot create local record");
        }
        output.write(text.data(), static_cast<std::streamsize>(text.size()));
        output.flush();
        if (!output) {
            throw std::runtime_error("cannot write local record");
        }
    }
    std::error_code rename_error;
    std::filesystem::rename(temporary, path, rename_error);
    if (rename_error) {
        std::filesystem::remove(temporary);
        throw std::runtime_error("cannot replace local record");
    }
}

bool has_nonempty(const std::filesystem::path& path) {
    std::error_code error;
    return std::filesystem::exists(path, error) &&
           std::filesystem::is_regular_file(path, error) &&
           std::filesystem::file_size(path, error) > 0;
}

}  // namespace site
''')

Path("/app/src/engine/session.cc").write_text(r'''#include "engine/session.h"

#include "fs/walker.h"
#include "store/ledger.h"
#include "support/files.h"

#include <sstream>
#include <stdexcept>

namespace site {

bool valid_root(const std::filesystem::path& root) {
    std::error_code error;
    return std::filesystem::is_directory(root / "payload", error) &&
           std::filesystem::is_directory(root / ".site", error);
}

bool is_busy(const std::filesystem::path& root) {
    return read_text(root / ".site" / "busy").starts_with('1');
}

void replay_local(const std::filesystem::path& root) {
    std::istringstream input(read_text(root / ".site" / "pending"));
    std::string line;
    while (std::getline(input, line)) {
        if (line.empty()) {
            continue;
        }
        if (!line.starts_with("drop:")) {
            throw std::runtime_error("unrecognized deferred operation");
        }
        const auto relative = std::filesystem::path(line.substr(5)).lexically_normal();
        if (relative.empty() || relative.is_absolute() ||
            relative.string().starts_with("..")) {
            throw std::runtime_error("unsafe deferred operation");
        }
        std::error_code error;
        std::filesystem::remove_all(root / "namespace" / relative, error);
        if (error) {
            throw std::runtime_error("cannot apply deferred operation");
        }
    }
    write_atomic(root / ".site" / "pending", "");
    write_atomic(root / ".site" / "status", "replayed\n");
}

void scan_local(const std::filesystem::path& root) {
    write_atomic(root / ".site" / "observed", render_scan(observe_tree(root)));
    write_atomic(root / ".site" / "status", "scanned\n");
}

void stage_local(const std::filesystem::path& root) {
    stage_candidate(root, observe_tree(root));
    write_atomic(root / ".site" / "status", "staged\n");
}

void commit_local(const std::filesystem::path& root) {
    if (has_nonempty(root / ".site" / "pending")) {
        throw std::runtime_error("deferred work remains");
    }
    const auto scan = observe_tree(root);
    const auto candidate = select_candidate(root, scan);
    if (!candidate) {
        throw std::runtime_error("no usable durable candidate");
    }
    commit_candidate(root, *candidate);
    write_atomic(root / ".site" / "status", "accounted\n");
}

void seal_q(const std::filesystem::path& root) {
    const auto scan = observe_tree(root);
    if (is_busy(root)) {
        throw std::runtime_error("target is in use");
    }
    if (has_nonempty(root / ".site" / "pending") || !account_matches(root, scan)) {
        throw std::runtime_error("target is not publishable");
    }
    write_atomic(root / ".site" / "status", "published\n");
    write_atomic(root / ".site" / "ready", "1\n");
}

bool serviceable(const std::filesystem::path& root) {
    return valid_root(root) &&
           !is_busy(root) &&
           !has_nonempty(root / ".site" / "pending") &&
           account_matches(root, observe_tree(root)) &&
           read_text(root / ".site" / "status").starts_with("published") &&
           read_text(root / ".site" / "ready").starts_with('1');
}

std::string inspect_local(const std::filesystem::path& root) {
    const auto scan = observe_tree(root);
    std::ostringstream output;
    output << "root=" << (valid_root(root) ? "valid" : "invalid") << '\n';
    output << "busy=" << (is_busy(root) ? "yes" : "no") << '\n';
    output << "pending=" << (has_nonempty(root / ".site" / "pending") ? "yes" : "no") << '\n';
    output << "account=" << (account_matches(root, scan) ? "current" : "stale") << '\n';
    output << "state=" << (serviceable(root) ? "serviceable" : "held") << '\n';
    return output.str();
}

}  // namespace site
''')
PY

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

cmake -S /app -B /tmp/site-repair-build -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/site-repair-build --parallel 2
cmake --install /tmp/site-repair-build --prefix /app
rm -rf /tmp/site-repair-build
