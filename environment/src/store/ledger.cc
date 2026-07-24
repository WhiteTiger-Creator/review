#include "store/ledger.h"

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
        if (candidate && (!selected || candidate->generation < selected->generation)) {
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
