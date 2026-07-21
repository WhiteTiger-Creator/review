#include "emit_pipeline.h"
#include "lane_bridge.h"
#include "scan_bridge.h"
#include "store_bridge.h"
#include "constants.h"
#include "types.h"
#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace forge {

constexpr const char *kCheckpointPath = "/app/output/forge_checkpoint.json";

namespace {

std::string read_file(const fs::path &path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw std::runtime_error("could not open fixture");
    }
    std::ostringstream ss;
    ss << in.rdbuf();
    return ss.str();
}

std::string pick_string(const std::string &block, const std::string &key) {
    std::string needle = "\"" + key + "\"";
    size_t k = block.find(needle);
    if (k == std::string::npos) {
        return "";
    }
    size_t q = block.find('"', block.find(':', k) + 1);
    size_t e = block.find('"', q + 1);
    if (q == std::string::npos || e == std::string::npos) {
        return "";
    }
    return block.substr(q + 1, e - q - 1);
}

int pick_int(const std::string &block, const std::string &key) {
    std::string needle = "\"" + key + "\"";
    size_t k = block.find(needle);
    if (k == std::string::npos) {
        return 0;
    }
    size_t colon = block.find(':', k);
    if (colon == std::string::npos) {
        return 0;
    }
    size_t start = colon + 1;
    while (start < block.size() && std::isspace(static_cast<unsigned char>(block[start]))) {
        ++start;
    }
    return std::stoi(block.substr(start));
}

std::string extract_array(const std::string &doc, const std::string &key) {
    std::string needle = "\"" + key + "\"";
    size_t k = doc.find(needle);
    if (k == std::string::npos) {
        return "";
    }
    size_t p = doc.find('[', k);
    if (p == std::string::npos) {
        return "";
    }
    int depth = 0;
    size_t start = p;
    for (size_t i = p; i < doc.size(); ++i) {
        if (doc[i] == '[') {
            ++depth;
        }
        if (doc[i] == ']') {
            --depth;
            if (depth == 0) {
                return doc.substr(start, i - start + 1);
            }
        }
    }
    return "";
}

std::vector<std::string> split_object_blocks(const std::string &array_text) {
    std::vector<std::string> out;
    int depth = 0;
    size_t start = std::string::npos;
    for (size_t i = 0; i < array_text.size(); ++i) {
        if (array_text[i] == '{') {
            if (depth == 0) {
                start = i;
            }
            ++depth;
        } else if (array_text[i] == '}') {
            --depth;
            if (depth == 0 && start != std::string::npos) {
                out.push_back(array_text.substr(start, i - start + 1));
                start = std::string::npos;
            }
        }
    }
    return out;
}

int64_t read_record_bytes(const fs::path &path) {
    std::string blob = read_file(path);
    size_t offset = 0;
    while (offset < blob.size()) {
        size_t end = blob.find('\n', offset);
        if (end == std::string::npos) {
            end = blob.size();
        }
        if (end > offset) {
            const char *line = blob.data() + offset;
            size_t len = end - offset;
            if (forge_scan_has_key(line, len, "size_bytes=")) {
                return forge_scan_record_bytes(line, len);
            }
        }
        if (end >= blob.size()) {
            break;
        }
        offset = end + 1;
    }
    return 0;
}

std::uint64_t digest_update(std::uint64_t h, const std::string &text) {
    for (unsigned char ch : text) {
        h ^= static_cast<std::uint64_t>(ch);
        h = (h * kDigestStep) & kDigestMask;
    }
    return h;
}

std::string json_escape(const std::string &s) {
    std::string out;
    for (char c : s) {
        if (c == '"' || c == '\\') {
            out.push_back('\\');
        }
        out.push_back(c);
    }
    return out;
}

}  // namespace

std::vector<std::string> split_units_csv(const std::string &text) {
    std::vector<std::string> out;
    std::string cur;
    for (char ch : text) {
        if (ch == ',') {
            if (!cur.empty()) {
                out.push_back(cur);
            }
            cur.clear();
        } else if (!std::isspace(static_cast<unsigned char>(ch))) {
            cur.push_back(ch);
        }
    }
    if (!cur.empty()) {
        out.push_back(cur);
    }
    return out;
}

int read_pass_epoch(const fs::path &checkpoint_path) {
    std::ifstream in(checkpoint_path);
    if (!in) {
        return 0;
    }
    std::ostringstream buffer;
    buffer << in.rdbuf();
    const std::string doc = buffer.str();
    size_t pos = doc.find("\"pass_epoch\"");
    if (pos == std::string::npos) {
        return 0;
    }
    return pick_int(doc, "pass_epoch");
}

Manifest load_manifest(const fs::path &path) {
    std::string doc = read_file(path);
    Manifest manifest{};
    manifest.release_id = pick_string(doc, "release_id");
    manifest.order_weight_base = pick_int(doc, "order_weight_base");
    std::string arr = extract_array(doc, "units");
    for (const auto &block : split_object_blocks(arr)) {
        UnitSpec spec;
        spec.name = pick_string(block, "name");
        spec.mode = pick_string(block, "mode");
        spec.record = pick_string(block, "record");
        spec.manifest_bytes = pick_int(block, "manifest_bytes");
        spec.start_pass = pick_int(block, "start_pass");
        if (!spec.name.empty()) {
            manifest.units.push_back(spec);
        }
    }
    return manifest;
}

std::string digest_hex(const std::string &text) {
    std::uint64_t h = digest_update(kDigestSeed, text);
    std::ostringstream os;
    os << std::hex << std::nouppercase << std::setfill('0') << std::setw(16) << h;
    return os.str();
}

UnitRun analyze_unit(const UnitSpec &spec, int order_rank, int order_weight_base, int pass_epoch,
                     const fs::path &manifest_dir, const char *const *names, size_t name_count,
                     const LaneCheckpoint *checkpoint, int64_t carry_weight) {
    fs::path record_path = manifest_dir / spec.record;
    UnitRun run{};
    run.name = spec.name;
    run.mode = forge_lane_mode(spec.mode.c_str(), spec.name.c_str(), pass_epoch);
    run.manifest_bytes = spec.manifest_bytes;
    run.record_bytes = read_record_bytes(record_path);
    run.drift_bytes = run.record_bytes - static_cast<int64_t>(run.manifest_bytes);
    run.order_rank = order_rank;

    int pass_index = spec.start_pass;
    int64_t seeded_weight = 0;
    if (run.mode == "resume" && checkpoint != nullptr && checkpoint->valid) {
        auto it = checkpoint->units.find(spec.name);
        if (it != checkpoint->units.end()) {
            pass_index = it->second.next_pass;
            seeded_weight = it->second.carry_weight;
        }
    }

    if (run.mode == "resume" && seeded_weight != 0) {
        run.order_weight = seeded_weight + static_cast<int64_t>(order_weight_base) + run.record_bytes;
    } else {
        run.order_weight =
            forge_lane_weight(spec.name.c_str(), names, name_count, order_weight_base, run.record_bytes);
    }
    (void)carry_weight;
    run.pass_index = pass_index;
    run.row_serial = forge_lane_row_text(run);
    run.row_digest = digest_hex(run.row_serial);

    std::ostringstream js;
    js << "{\"name\":\"" << json_escape(run.name) << "\",\"mode\":\"" << json_escape(run.mode)
       << "\",\"pass_index\":" << run.pass_index << ",\"manifest_bytes\":" << run.manifest_bytes
       << ",\"record_bytes\":" << run.record_bytes << ",\"drift_bytes\":" << run.drift_bytes
       << ",\"order_rank\":" << run.order_rank << ",\"order_weight\":" << run.order_weight
       << ",\"row_digest\":\"" << run.row_digest << "\"}";
    run.json = js.str();
    return run;
}

}  // namespace forge

int forge_run_emit(int argc, char **argv) {
    if (argc != 4) {
        std::cerr << "usage: forge_emit <manifest-json> <output-json> <units-csv>\n";
        return 2;
    }
    fs::path manifest_path = argv[1];
    fs::path output_path = argv[2];
    std::vector<std::string> requested = forge::split_units_csv(argv[3]);
    forge::Manifest manifest = forge::load_manifest(manifest_path);
    fs::path manifest_dir = manifest_path.parent_path();

    const char *lane_token = forge_lane_fingerprint(manifest.units.data(), manifest.units.size());
    fs::path checkpoint_path = forge::kCheckpointPath;
    int pass_epoch = forge::read_pass_epoch(checkpoint_path);
    forge::LaneCheckpoint checkpoint = forge_lane_load_checkpoint(checkpoint_path, lane_token);

    std::vector<const char *> name_ptrs;
    for (const auto &unit : manifest.units) {
        name_ptrs.push_back(unit.name.c_str());
    }

    std::map<std::string, forge::UnitSpec> spec_by_name;
    for (const auto &unit : manifest.units) {
        spec_by_name[unit.name] = unit;
    }

    std::vector<forge::UnitRun> units;
    std::vector<forge::UnitCheckpoint> updated_entries;
    std::vector<std::string> requested_resume;
    for (const auto &name : requested) {
        auto it = spec_by_name.find(name);
        if (it == spec_by_name.end()) {
            continue;
        }
        int order_rank = static_cast<int>(std::distance(
            manifest.units.begin(),
            std::find_if(manifest.units.begin(), manifest.units.end(),
                         [&](const forge::UnitSpec &u) { return u.name == name; })));
        int64_t carry_weight = 0;
        if (checkpoint.valid) {
            auto cp = checkpoint.units.find(name);
            if (cp != checkpoint.units.end()) {
                carry_weight = cp->second.carry_weight;
            }
        }
        forge::UnitRun run = forge::analyze_unit(it->second, order_rank, manifest.order_weight_base,
                                                 pass_epoch, manifest_dir, name_ptrs.data(),
                                                 name_ptrs.size(), &checkpoint, carry_weight);
        units.push_back(run);
        if (run.mode == "resume") {
            requested_resume.push_back(name);
            forge::UnitCheckpoint entry;
            entry.name = run.name;
            entry.next_pass = run.pass_index + 1;
            entry.carry_weight = run.order_weight;
            entry.carry_drift = run.drift_bytes;
            updated_entries.push_back(entry);
        }
    }

    int64_t drift_total = forge_lane_drift_total(units.data(), units.size());
    int64_t weight_total = forge_lane_score_total(units.data(), units.size());

    std::ostringstream serial;
    serial << forge_lane_header_text(forge::kSchemaVersion, manifest.release_id,
                                     manifest.order_weight_base, pass_epoch, drift_total,
                                     weight_total);
    for (const auto &unit : units) {
        serial << '\n' << unit.row_serial;
    }
    std::string top_digest = forge::digest_hex(serial.str());

    fs::create_directories(output_path.parent_path());
    std::ostringstream out;
    out << "{\"schema_version\":" << forge::kSchemaVersion << ",\"release_id\":\""
        << manifest.release_id << "\",\"order_weight_base\":" << manifest.order_weight_base
        << ",\"pass_epoch\":" << pass_epoch << ",\"units\":[";
    for (std::size_t i = 0; i < units.size(); ++i) {
        if (i) {
            out << ',';
        }
        out << units[i].json;
    }
    out << "],\"total_drift_bytes\":" << drift_total << ",\"order_score\":" << weight_total
        << ",\"digest\":\"" << top_digest << "\"}\n";
    std::ofstream file(output_path, std::ios::binary);
    file << out.str();

    std::vector<forge::UnitCheckpoint> merged =
        forge_lane_merge_checkpoint(checkpoint, updated_entries, requested_resume);
    forge_lane_save_checkpoint(checkpoint_path, lane_token, merged);

    std::ostringstream cp_patch;
    cp_patch << "{\"schema_version\":" << forge::kSchemaVersion << ",\"lane_token\":\"" << lane_token
             << "\",\"pass_epoch\":" << (pass_epoch + 1) << ",\"units\":[";
    for (size_t i = 0; i < merged.size(); ++i) {
        if (i) {
            cp_patch << ',';
        }
        cp_patch << "{\"name\":\"" << merged[i].name << "\",\"next_pass\":" << merged[i].next_pass
                 << ",\"carry_weight\":" << merged[i].carry_weight << ",\"carry_drift\":"
                 << merged[i].carry_drift << '}';
    }
    cp_patch << "]}\n";
    std::ofstream cp_file(checkpoint_path, std::ios::binary);
    cp_file << cp_patch.str();

    return 0;
}
