#include "engine/session.h"

#include "fs/walker.h"
#include "store/ledger.h"
#include "support/files.h"

#include <sstream>
#include <stdexcept>
#include <vector>

namespace site {
namespace {

bool noted_residue(const std::filesystem::path& root) {
    const auto text = read_text(root / ".site" / "events");
    std::istringstream input(text);
    std::string line;
    while (std::getline(input, line)) {
        if (!line.starts_with("noted=")) {
            continue;
        }
        const auto relative = std::filesystem::path(line.substr(6)).lexically_normal();
        if (relative.empty() || relative.is_absolute() ||
            relative.string().starts_with("..")) {
            continue;
        }
        std::error_code error;
        if (std::filesystem::exists(root / "namespace" / relative, error)) {
            return true;
        }
    }
    return false;
}

bool unsafe_relative(const std::filesystem::path& relative) {
    return relative.empty() || relative.is_absolute() ||
           relative.string().starts_with("..");
}

}  // namespace

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
    std::vector<std::string> remaining;
    bool applied = false;
    while (std::getline(input, line)) {
        if (line.empty()) {
            continue;
        }
        if (line.starts_with("note:")) {
            remaining.push_back(line);
            continue;
        }
        if (!line.starts_with("drop:")) {
            throw std::runtime_error("unrecognized deferred operation");
        }
        const auto relative = std::filesystem::path(line.substr(5)).lexically_normal();
        if (unsafe_relative(relative)) {
            throw std::runtime_error("unsafe deferred operation");
        }
        std::error_code error;
        std::filesystem::remove_all(root / "namespace" / relative, error);
        if (error) {
            throw std::runtime_error("cannot apply deferred operation");
        }
        applied = true;
    }
    std::ostringstream pending;
    for (const auto& entry : remaining) {
        pending << entry << '\n';
    }
    write_atomic(root / ".site" / "pending", pending.str());
    if (applied || remaining.empty()) {
        write_atomic(root / ".site" / "status", "replayed\n");
    }
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
    if (noted_residue(root)) {
        throw std::runtime_error("deferred work remains");
    }
    const auto scan = observe_tree(root);
    assert_no_stale_slots(root, scan);
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
    if (has_nonempty(root / ".site" / "pending") || noted_residue(root) ||
        !account_matches(root, scan)) {
        throw std::runtime_error("target is not publishable");
    }
    const auto observed_path = root / ".site" / "observed";
    if (!has_nonempty(observed_path) ||
        read_text(observed_path) != render_scan(scan)) {
        throw std::runtime_error("observed inventory is not current");
    }
    write_atomic(root / ".site" / "status", "published\n");
    write_atomic(root / ".site" / "ready", "1\n");
}

void recover_local(const std::filesystem::path& root) {
    std::istringstream input(read_text(root / ".site" / "pending"));
    std::string line;
    std::ostringstream ledger;
    while (std::getline(input, line)) {
        if (line.empty()) {
            continue;
        }
        if (line.starts_with("drop:")) {
            throw std::runtime_error("deferred drops remain");
        }
        if (!line.starts_with("note:")) {
            throw std::runtime_error("unrecognized deferred operation");
        }
        const auto relative = std::filesystem::path(line.substr(5)).lexically_normal();
        if (unsafe_relative(relative)) {
            throw std::runtime_error("unsafe deferred operation");
        }
        ledger << "kept=" << relative.generic_string() << '\n';
    }
    if (!ledger.str().empty()) {
        const auto prior = read_text(root / ".site" / "events");
        write_atomic(root / ".site" / "events", prior + ledger.str());
    }
    write_atomic(root / ".site" / "pending", "");
    write_atomic(root / ".site" / "status", "replayed\n");
}

void sync_local(const std::filesystem::path& root) {
    scan_local(root);
}

void finalize_local(const std::filesystem::path& root) {
    write_atomic(root / ".site" / "ready", "1\n");
}

bool serviceable(const std::filesystem::path& root) {
    return valid_root(root) &&
           !is_busy(root) &&
           !has_nonempty(root / ".site" / "pending") &&
           !noted_residue(root) &&
           account_matches(root, observe_tree(root)) &&
           read_text(root / ".site" / "status").starts_with("published") &&
           read_text(root / ".site" / "ready").starts_with('1');
}

std::string inspect_local(const std::filesystem::path& root) {
    const auto scan = observe_tree(root);
    std::ostringstream output;
    output << "root=" << (valid_root(root) ? "valid" : "invalid") << '\n';
    output << "busy=" << (is_busy(root) ? "yes" : "no") << '\n';
    output << "pending=" << (has_nonempty(root / ".site" / "pending") || noted_residue(root)
                                 ? "yes"
                                 : "no")
           << '\n';
    output << "account=" << (account_matches(root, scan) ? "current" : "stale") << '\n';
    output << "state=" << (serviceable(root) ? "serviceable" : "held") << '\n';
    return output.str();
}

}  // namespace site
