#include "store/ledger.h"

#include "model/record.h"
#include "support/clock.h"
#include "support/codec.h"
#include "support/files.h"

#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace site {
namespace {

std::string hex_value(std::uint64_t value) {
    std::ostringstream output;
    output << std::hex << std::setw(16) << std::setfill('0') << value;
    return output.str();
}

bool record_matches_scan(const Record& record, const Scan& scan) {
    return record.get("count") == std::to_string(scan.paths.size()) &&
           record.get("fingerprint") == hex_value(scan.fingerprint) &&
           record.number("generation", -1) >= 0;
}

std::optional<Candidate> load_candidate(
    const std::filesystem::path& path,
    const Scan& scan
) {
    if (!has_nonempty(path)) {
        return std::nullopt;
    }
    const auto record = decode_record(read_text(path));
    if (!record_matches_scan(record, scan)) {
        return std::nullopt;
    }
    return Candidate{
        record.number("generation", -1),
        record.get("count"),
        record.get("fingerprint"),
        path};
}

bool slot_is_stale(const std::filesystem::path& path, const Scan& scan) {
    if (!has_nonempty(path)) {
        return false;
    }
    const auto record = decode_record(read_text(path));
    return !record_matches_scan(record, scan);
}

void remove_path(const std::filesystem::path& path) {
    std::error_code error;
    std::filesystem::remove(path, error);
    if (error) {
        throw std::runtime_error("cannot clear durable candidate");
    }
}

}  // namespace

void stage_candidate(const std::filesystem::path& root, const Scan& scan) {
    bool have_match = false;
    bool purged_stale = false;
    for (const auto* name : {"slot-a", "slot-b"}) {
        const auto path = root / ".site" / name;
        if (!has_nonempty(path)) {
            continue;
        }
        const auto record = decode_record(read_text(path));
        if (record_matches_scan(record, scan)) {
            have_match = true;
            continue;
        }
        remove_path(path);
        purged_stale = true;
    }
    if (have_match) {
        if (purged_stale) {
            return;
        }
        throw std::runtime_error("usable durable candidate exists");
    }

    const long generation = next_sequence(root);
    Record record;
    record.set("count", std::to_string(scan.paths.size()));
    record.set("fingerprint", hex_value(scan.fingerprint));
    record.set("generation", std::to_string(generation));
    const auto slot = generation % 2 == 0 ? "slot-a" : "slot-b";
    const auto other = generation % 2 == 0 ? "slot-b" : "slot-a";
    write_atomic(root / ".site" / slot, encode_record(record));
    if (has_nonempty(root / ".site" / other)) {
        remove_path(root / ".site" / other);
    }
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

void assert_no_stale_slots(const std::filesystem::path& root, const Scan& scan) {
    for (const auto* name : {"slot-a", "slot-b"}) {
        if (slot_is_stale(root / ".site" / name, scan)) {
            throw std::runtime_error("stale durable candidate");
        }
    }
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
