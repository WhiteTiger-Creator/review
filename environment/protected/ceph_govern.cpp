#include <algorithm>
#include <array>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <sys/wait.h>
#include <unistd.h>
#include <vector>

namespace fs = std::filesystem;

static std::map<std::string, std::string> load(const fs::path& path) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("cannot read cluster file");
    }
    std::map<std::string, std::string> values;
    std::string line;
    while (std::getline(input, line)) {
        if (line.empty()) {
            continue;
        }
        const auto split = line.find('=');
        if (split == std::string::npos || split == 0 ||
            line.find('=', split + 1) != std::string::npos) {
            throw std::runtime_error("malformed cluster field");
        }
        const std::string key = line.substr(0, split);
        if (values.contains(key)) {
            throw std::runtime_error("duplicate cluster field");
        }
        values.emplace(key, line.substr(split + 1));
    }
    return values;
}

static void require_keys(const std::map<std::string, std::string>& values,
                         const std::set<std::string>& required,
                         const std::set<std::string>& empty_allowed = {}) {
    std::set<std::string> actual;
    for (const auto& [key, value] : values) {
        actual.insert(key);
        if (value.empty() && !empty_allowed.contains(key)) {
            throw std::runtime_error("empty required field");
        }
    }
    if (actual != required) {
        throw std::runtime_error("cluster field set mismatch");
    }
}

static bool safe_identifier(const std::string& value) {
    return !value.empty() &&
           std::all_of(value.begin(), value.end(), [](unsigned char character) {
               return std::isalnum(character) != 0 || character == '.' ||
                      character == '_' || character == '-';
           });
}

static long long unsigned_value(const std::map<std::string, std::string>& values,
                                const std::string& key, bool positive = false) {
    const std::string& text = values.at(key);
    if (text.empty() ||
        !std::all_of(text.begin(), text.end(), [](unsigned char character) {
            return std::isdigit(character) != 0;
        })) {
        throw std::runtime_error("invalid unsigned value");
    }
    std::size_t consumed = 0;
    const long long value = std::stoll(text, &consumed);
    if (consumed != text.size() || value < 0 || (positive && value == 0)) {
        throw std::runtime_error("invalid unsigned value");
    }
    return value;
}

static double decimal_value(const std::map<std::string, std::string>& values,
                            const std::string& key, bool positive = false) {
    const std::string& text = values.at(key);
    std::size_t consumed = 0;
    const double value = std::stod(text, &consumed);
    if (consumed != text.size() || !std::isfinite(value) || value < 0.0 ||
        value > 1.0 || (positive && value == 0.0)) {
        throw std::runtime_error("invalid decimal value");
    }
    return value;
}

static std::vector<std::string> split_list(const std::string& text,
                                           bool empty_allowed = false) {
    if (text.empty()) {
        if (empty_allowed) {
            return {};
        }
        throw std::runtime_error("empty list");
    }
    std::vector<std::string> values;
    std::stringstream stream(text);
    std::string value;
    while (std::getline(stream, value, ',')) {
        if (!safe_identifier(value) ||
            std::find(values.begin(), values.end(), value) != values.end()) {
            throw std::runtime_error("invalid list");
        }
        values.push_back(value);
    }
    if (values.empty() || text.ends_with(',')) {
        throw std::runtime_error("invalid list");
    }
    return values;
}

static void validate_cluster(const std::map<std::string, std::string>& state) {
    const std::set<std::string> required = {
        "id",             "epoch",          "observed_epoch",
        "health",         "nearfull",       "backfillfull",
        "dest_used",      "dest_capacity",  "move_bytes",
        "source_osd",     "dest_osd",       "source_host",
        "dest_host",      "source_rack",    "dest_rack",
        "replica_hosts",  "replica_racks",  "current_weight",
        "target_weight",  "max_step",       "external_flags",
        "owned_flags",    "journal_stage",  "recovery_queue",
        "client_iops",
    };
    require_keys(state, required, {"external_flags", "owned_flags"});
    for (const std::string key : {
             "id", "source_osd", "dest_osd", "source_host", "dest_host",
             "source_rack", "dest_rack",
         }) {
        if (!safe_identifier(state.at(key))) {
            throw std::runtime_error("invalid cluster identifier");
        }
    }
    if (state.at("health") != "clean" && state.at("health") != "degraded") {
        throw std::runtime_error("invalid health");
    }
    if (state.at("journal_stage") != "none" &&
        state.at("journal_stage") != "flagged" &&
        state.at("journal_stage") != "reweighted" &&
        state.at("journal_stage") != "migrated") {
        throw std::runtime_error("invalid journal stage");
    }
    for (const std::string key : {
             "epoch", "observed_epoch", "dest_used", "recovery_queue",
             "client_iops",
         }) {
        (void)unsigned_value(state, key);
    }
    const long long capacity = unsigned_value(state, "dest_capacity", true);
    (void)unsigned_value(state, "move_bytes", true);
    if (unsigned_value(state, "dest_used") > capacity) {
        throw std::runtime_error("destination use exceeds capacity");
    }
    const double nearfull = decimal_value(state, "nearfull");
    const double backfillfull = decimal_value(state, "backfillfull");
    (void)decimal_value(state, "current_weight");
    (void)decimal_value(state, "target_weight");
    (void)decimal_value(state, "max_step", true);
    if (nearfull >= backfillfull) {
        throw std::runtime_error("invalid fullness ordering");
    }
    const auto replica_hosts = split_list(state.at("replica_hosts"));
    const auto replica_racks = split_list(state.at("replica_racks"));
    if (replica_hosts.size() != replica_racks.size()) {
        throw std::runtime_error("replica topology length mismatch");
    }
    (void)split_list(state.at("external_flags"), true);
    (void)split_list(state.at("owned_flags"), true);
}

static std::set<std::string> split_set(const std::string& text) {
    std::set<std::string> result;
    std::stringstream stream(text);
    std::string item;
    while (std::getline(stream, item, ',')) {
        if (!item.empty()) {
            result.insert(item);
        }
    }
    return result;
}

static std::vector<std::string> expected_plan(
    const std::map<std::string, std::string>& state,
    const fs::path& policy) {
    validate_cluster(state);
    const fs::path root = fs::weakly_canonical(policy).parent_path().parent_path();
    const auto fullness = load(root / "etc/fullness.conf");
    const auto flags = load(root / "etc/flags.conf");
    const auto recovery = load(root / "etc/recovery.conf");
    const auto reweight = load(root / "etc/reweight.conf");
    require_keys(
        fullness,
        {"backfill_headroom_ratio", "nearfull_margin_ratio"}
    );
    require_keys(flags, {"maintenance_flag", "clear_only_owned"});
    require_keys(
        recovery,
        {
            "high_client_iops", "high_queue", "busy_max_backfills",
            "busy_recovery_priority", "quiet_max_backfills",
            "quiet_recovery_priority",
        }
    );
    require_keys(reweight, {"maximum_step", "minimum_weight"});
    if (!safe_identifier(flags.at("maintenance_flag")) ||
        (flags.at("clear_only_owned") != "true" &&
         flags.at("clear_only_owned") != "false")) {
        throw std::runtime_error("invalid flag policy");
    }
    for (const std::string key : {
             "high_client_iops", "high_queue", "busy_max_backfills",
             "busy_recovery_priority", "quiet_max_backfills",
             "quiet_recovery_priority",
         }) {
        (void)unsigned_value(recovery, key);
    }
    (void)decimal_value(fullness, "backfill_headroom_ratio");
    (void)decimal_value(fullness, "nearfull_margin_ratio");
    (void)decimal_value(reweight, "maximum_step", true);
    (void)decimal_value(reweight, "minimum_weight");

    const std::string maintenance_flag = flags.at("maintenance_flag");
    const long long observed = unsigned_value(state, "observed_epoch");
    std::vector<std::string> lines = {"epoch " + std::to_string(observed)};
    const auto pause = [&lines](const std::string& reason) {
        lines.push_back("hold " + reason);
        lines.push_back("publish paused");
    };
    if (observed != unsigned_value(state, "epoch")) {
        pause("stale-epoch");
        return lines;
    }
    if (flags.at("clear_only_owned") != "true") {
        pause("flag-policy");
        return lines;
    }
    const std::set<std::string> owned = split_set(state.at("owned_flags"));
    const std::string stage = state.at("journal_stage");
    if (stage == "migrated") {
        if (owned.contains(maintenance_flag)) {
            lines.push_back("clear " + maintenance_flag);
        }
        lines.push_back("publish complete");
        return lines;
    }
    if (state.at("health") != "clean") {
        pause("degraded-health");
        return lines;
    }
    if (split_set(state.at("external_flags")).contains(maintenance_flag) &&
        !owned.contains(maintenance_flag)) {
        pause("foreign-flag");
        return lines;
    }
    const double target_weight = decimal_value(state, "target_weight");
    if (target_weight < decimal_value(reweight, "minimum_weight")) {
        pause("minimum-weight");
        return lines;
    }
    const long long destination_used = unsigned_value(state, "dest_used");
    const long long movement = unsigned_value(state, "move_bytes", true);
    const long long capacity = unsigned_value(state, "dest_capacity", true);
    const double current_ratio =
        static_cast<double>(destination_used) / static_cast<double>(capacity);
    const double projected_ratio =
        static_cast<double>(destination_used + movement) /
        static_cast<double>(capacity);
    double fullness_limit = decimal_value(state, "backfillfull");
    if (current_ratio >= decimal_value(state, "nearfull")) {
        fullness_limit -= std::max(
            decimal_value(fullness, "backfill_headroom_ratio"),
            decimal_value(fullness, "nearfull_margin_ratio")
        );
    }
    if (projected_ratio >= fullness_limit) {
        pause("fullness-gate");
        return lines;
    }
    if (split_set(state.at("replica_racks")).contains(state.at("dest_rack"))) {
        pause("failure-domain");
        return lines;
    }
    if (stage == "none" && !owned.contains(maintenance_flag)) {
        lines.push_back("flag " + maintenance_flag + " owned");
    }
    const bool busy =
        unsigned_value(state, "client_iops") >=
            unsigned_value(recovery, "high_client_iops") ||
        unsigned_value(state, "recovery_queue") >=
            unsigned_value(recovery, "high_queue");
    lines.push_back(
        "tune max_backfills " +
        recovery.at(busy ? "busy_max_backfills" : "quiet_max_backfills")
    );
    lines.push_back(
        "tune recovery_priority " +
        recovery.at(
            busy ? "busy_recovery_priority" : "quiet_recovery_priority"
        )
    );
    if (stage != "reweighted") {
        const double current = decimal_value(state, "current_weight");
        const double step = std::min(
            decimal_value(reweight, "maximum_step", true),
            decimal_value(state, "max_step", true)
        );
        const double next =
            current > target_weight
                ? std::max(target_weight, current - step)
                : std::min(target_weight, current + step);
        std::ostringstream reweight_line;
        reweight_line << "reweight " << state.at("source_osd") << ' ' << next;
        lines.push_back(reweight_line.str());
        lines.push_back("checkpoint reweighted");
        if (std::fabs(next - target_weight) > 0.000001) {
            lines.push_back("publish staged");
            return lines;
        }
    }
    lines.push_back("move " + std::to_string(movement));
    lines.push_back("checkpoint migrated");
    lines.push_back("clear " + maintenance_flag);
    lines.push_back("publish complete");
    return lines;
}

static std::string join(const std::set<std::string>& values) {
    std::ostringstream output;
    bool first = true;
    for (const auto& value : values) {
        if (!first) {
            output << ',';
        }
        first = false;
        output << value;
    }
    return output.str();
}

static std::string quote(const std::string& value) {
    std::string result = "'";
    for (char character : value) {
        result += character == '\'' ? "'\\''" : std::string(1, character);
    }
    return result + "'";
}

static std::vector<std::string> invoke(const fs::path& policy,
                                       const fs::path& cluster) {
    const char* timeout_mode = std::getenv("CEPH_POLICY_TIMEOUT");
    const std::string timeout_prefix =
        timeout_mode != nullptr && std::string(timeout_mode) == "off"
            ? ""
            : "timeout 3 ";
    const std::string command =
        timeout_prefix + quote(policy.string()) + " " + quote(cluster.string());
    std::array<char, 4096> buffer{};
    std::string text;
    FILE* pipe = popen(command.c_str(), "r");
    if (pipe == nullptr) {
        throw std::runtime_error("cannot start policy");
    }
    while (fgets(buffer.data(), static_cast<int>(buffer.size()), pipe) != nullptr) {
        text += buffer.data();
        if (text.size() > 32768) {
            break;
        }
    }
    const int status = pclose(pipe);
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        throw std::runtime_error("policy failed or timed out");
    }
    std::vector<std::string> lines;
    std::stringstream stream(text);
    std::string line;
    while (std::getline(stream, line)) {
        if (!line.empty()) {
            lines.push_back(line);
        }
    }
    return lines;
}

struct Applied {
    bool valid = true;
    std::string error;
    std::string status = "unpublished";
    long long asserted_epoch = -1;
    double weight = 0.0;
    long long dest_used = 0;
    int moves = 0;
    std::string checkpoint;
    std::set<std::string> flags;
    std::set<std::string> owned;
    std::map<std::string, int> tuning;
    std::vector<std::string> trace;
};

static Applied apply_plan(const std::map<std::string, std::string>& state,
                          const std::vector<std::string>& lines,
                          const std::vector<std::string>& expected) {
    const std::set<std::string> hold_reasons = {
        "stale-epoch", "degraded-health", "foreign-flag", "fullness-gate",
        "failure-domain", "flag-policy", "minimum-weight",
    };
    Applied result;
    result.weight = std::stod(state.at("current_weight"));
    result.dest_used = std::stoll(state.at("dest_used"));
    result.checkpoint = state.at("journal_stage");
    result.flags = split_set(state.at("external_flags"));
    const auto preowned = split_set(state.at("owned_flags"));
    result.flags.insert(preowned.begin(), preowned.end());
    result.owned = preowned;
    if (lines != expected) {
        result.valid = false;
        result.error = "plan does not match cluster contract";
        return result;
    }
    if (lines.size() < 2 || lines.size() > 14) {
        result.valid = false;
        result.error = "plan length";
        return result;
    }
    bool published = false;
    bool held = false;
    for (std::size_t index = 0; index < lines.size(); ++index) {
        std::stringstream command(lines[index]);
        std::string verb;
        command >> verb;
        if (published) {
            result.valid = false;
            result.error = "command after publication";
            break;
        }
        if (verb == "epoch") {
            long long value = -1;
            command >> value;
            if (index != 0 || !command.eof()) {
                result.valid = false;
                result.error = "epoch position";
                break;
            }
            result.asserted_epoch = value;
        } else if (verb == "flag") {
            std::string name;
            std::string ownership;
            command >> name >> ownership;
            if (name.empty() || ownership != "owned" || !command.eof()) {
                result.valid = false;
                result.error = "flag syntax";
                break;
            }
            if (!result.flags.contains(name)) {
                result.flags.insert(name);
                result.owned.insert(name);
            }
        } else if (verb == "tune") {
            std::string name;
            int value = -1;
            command >> name >> value;
            if ((name != "max_backfills" && name != "recovery_priority") ||
                value < 0 || !command.eof()) {
                result.valid = false;
                result.error = "tune syntax";
                break;
            }
            result.tuning[name] = value;
        } else if (verb == "reweight") {
            std::string osd;
            double value = -1.0;
            command >> osd >> value;
            if (osd != state.at("source_osd") || value < 0.0 || value > 1.0 ||
                !command.eof()) {
                result.valid = false;
                result.error = "reweight syntax";
                break;
            }
            result.weight = value;
        } else if (verb == "move") {
            long long bytes = -1;
            command >> bytes;
            if (bytes <= 0 || !command.eof()) {
                result.valid = false;
                result.error = "move syntax";
                break;
            }
            result.dest_used += bytes;
            ++result.moves;
        } else if (verb == "checkpoint") {
            std::string stage;
            command >> stage;
            if ((stage != "reweighted" && stage != "migrated") ||
                !command.eof()) {
                result.valid = false;
                result.error = "checkpoint syntax";
                break;
            }
            result.checkpoint = stage;
        } else if (verb == "clear") {
            std::string name;
            command >> name;
            if (name.empty() || !command.eof() || !result.owned.contains(name)) {
                result.valid = false;
                result.error = "clear ownership";
                break;
            }
            result.flags.erase(name);
            result.owned.erase(name);
        } else if (verb == "hold") {
            std::string reason;
            command >> reason;
            if (!hold_reasons.contains(reason) || !command.eof() || index != 1) {
                result.valid = false;
                result.error = "hold syntax";
                break;
            }
            held = true;
        } else if (verb == "publish") {
            command >> result.status;
            if ((result.status != "paused" && result.status != "staged" &&
                 result.status != "complete") ||
                !command.eof() || index + 1 != lines.size() ||
                (held && result.status != "paused") ||
                (!held && result.status == "paused")) {
                result.valid = false;
                result.error = "publication syntax";
                break;
            }
            published = true;
        } else {
            result.valid = false;
            result.error = "unknown command";
            break;
        }
        result.trace.push_back(lines[index]);
    }
    if (!published) {
        result.valid = false;
        if (result.error.empty()) {
            result.error = "missing publication";
        }
    }
    return result;
}

static void write_state(const fs::path& path,
                        const std::map<std::string, std::string>& state,
                        const Applied& applied) {
    fs::create_directories(path.parent_path());
    std::ofstream output(path);
    output << "id=" << state.at("id") << '\n';
    output << "valid=" << (applied.valid ? "true" : "false") << '\n';
    output << "error=" << applied.error << '\n';
    output << "status=" << applied.status << '\n';
    output << "epoch=" << state.at("epoch") << '\n';
    output << "asserted_epoch=" << applied.asserted_epoch << '\n';
    output << std::fixed << std::setprecision(6);
    output << "weight=" << applied.weight << '\n';
    output << "dest_used=" << applied.dest_used << '\n';
    output << "moves=" << applied.moves << '\n';
    output << "checkpoint=" << applied.checkpoint << '\n';
    output << "flags=" << join(applied.flags) << '\n';
    output << "owned_flags=" << join(applied.owned) << '\n';
    output << "max_backfills="
           << (applied.tuning.contains("max_backfills")
                   ? applied.tuning.at("max_backfills")
                   : -1)
           << '\n';
    output << "recovery_priority="
           << (applied.tuning.contains("recovery_priority")
                   ? applied.tuning.at("recovery_priority")
                   : -1)
           << '\n';
    output << "trace=";
    for (std::size_t index = 0; index < applied.trace.size(); ++index) {
        if (index != 0) {
            output << ';';
        }
        output << applied.trace[index];
    }
    output << '\n';
}

static int run_one(const fs::path& cluster, const fs::path& policy,
                   const fs::path& output) {
    const auto state = load(cluster);
    Applied applied;
    try {
        const auto lines = invoke(policy, cluster);
        applied = apply_plan(state, lines, expected_plan(state, policy));
    } catch (const std::exception& error) {
        applied.valid = false;
        applied.error = error.what();
    }
    write_state(output, state, applied);
    return applied.valid ? 0 : 3;
}

static std::string fnv(const std::string& text) {
    unsigned long long value = 1469598103934665603ULL;
    for (unsigned char character : text) {
        value ^= character;
        value *= 1099511628211ULL;
    }
    std::ostringstream output;
    output << std::hex << value;
    return output.str();
}

static int sweep(const fs::path& policy, const fs::path& catalog,
                 const fs::path& root) {
    std::ifstream input(catalog);
    std::vector<fs::path> clusters;
    std::string line;
    while (std::getline(input, line)) {
        if (!line.empty()) {
            clusters.push_back(catalog.parent_path() / line);
        }
    }
    const fs::path generations = root / "generations";
    const fs::path temporary = generations / (".tmp-" + std::to_string(getpid()));
    fs::remove_all(temporary);
    fs::create_directories(temporary / "states");
    std::ostringstream digest_input;
    int valid_count = 0;
    for (const auto& cluster : clusters) {
        const auto state = load(cluster);
        Applied applied;
        try {
            const auto lines = invoke(policy, cluster);
            applied = apply_plan(state, lines, expected_plan(state, policy));
        } catch (const std::exception& error) {
            applied.valid = false;
            applied.error = error.what();
        }
        const fs::path result = temporary / "states" /
                                (cluster.stem().string() + ".state");
        write_state(result, state, applied);
        std::ifstream recorded(result);
        digest_input << recorded.rdbuf();
        valid_count += applied.valid ? 1 : 0;
    }
    const std::string generation = "ceph-" + fnv(digest_input.str());
    {
        std::ofstream summary(temporary / "summary.state");
        summary << "generation=" << generation << '\n';
        summary << "clusters=" << clusters.size() << '\n';
        summary << "valid=" << valid_count << '\n';
    }
    if (valid_count != static_cast<int>(clusters.size())) {
        fs::remove_all(temporary);
        std::cout << "generation=" << generation << '\n';
        std::cout << "clusters=" << clusters.size() << '\n';
        std::cout << "valid=" << valid_count << '\n';
        return 3;
    }
    if (std::getenv("CEPH_FAILPOINT") != nullptr) {
        fs::remove_all(temporary);
        return 4;
    }
    const fs::path final = generations / generation;
    if (fs::exists(final)) {
        fs::remove_all(temporary);
    } else {
        fs::rename(temporary, final);
    }
    const fs::path next = root / ".current-next";
    fs::remove(next);
    fs::create_symlink(fs::path("generations") / generation, next);
    fs::rename(next, root / "current");
    std::cout << "generation=" << generation << '\n';
    std::cout << "clusters=" << clusters.size() << '\n';
    std::cout << "valid=" << valid_count << '\n';
    return 0;
}

int main(int argc, char** argv) {
    try {
        if (argc == 5 && std::string(argv[1]) == "apply") {
            return run_one(argv[2], argv[3], argv[4]);
        }
        if (argc == 5 && std::string(argv[1]) == "sweep") {
            return sweep(argv[2], argv[3], argv[4]);
        }
        std::cerr << "usage: ceph-govern apply cluster policy output\n";
        std::cerr << "       ceph-govern sweep policy catalog output\n";
        return 64;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 65;
    }
}
