#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <string>

namespace fs = std::filesystem;

static std::map<std::string, std::string> load(const fs::path& path) {
    std::ifstream input(path);
    std::map<std::string, std::string> values;
    std::string line;
    while (std::getline(input, line)) {
        const auto split = line.find('=');
        if (split != std::string::npos) {
            values[line.substr(0, split)] = line.substr(split + 1);
        }
    }
    return values;
}

static std::set<std::string> split(const std::string& text) {
    std::set<std::string> values;
    std::stringstream stream(text);
    std::string value;
    while (std::getline(stream, value, ',')) {
        if (!value.empty()) {
            values.insert(value);
        }
    }
    return values;
}

static bool contains(const std::string& text, const std::string& value) {
    return split(text).contains(value);
}

int main(int argc, char** argv) {
    if (argc != 2) {
        return 64;
    }
    const auto state = load(argv[1]);
    const fs::path root = fs::weakly_canonical(argv[0]).parent_path().parent_path();
    const auto fullness = load(root / "etc/fullness.conf");
    const auto flags = load(root / "etc/flags.conf");
    const auto recovery = load(root / "etc/recovery.conf");
    const auto reweight = load(root / "etc/reweight.conf");
    const std::string maintenance_flag = flags.at("maintenance_flag");
    const long long observed = std::stoll(state.at("observed_epoch"));
    std::cout << "epoch " << observed << '\n';
    const auto pause = [](const std::string& reason) {
        std::cout << "hold " << reason << '\n';
        std::cout << "publish paused\n";
    };
    if (observed != std::stoll(state.at("epoch"))) {
        pause("stale-epoch");
        return 0;
    }
    const auto owned = split(state.at("owned_flags"));
    if (flags.at("clear_only_owned") != "true") {
        pause("flag-policy");
        return 0;
    }
    const std::string stage = state.at("journal_stage");
    if (stage == "migrated") {
        if (owned.contains(maintenance_flag)) {
            std::cout << "clear " << maintenance_flag << '\n';
        }
        std::cout << "publish complete\n";
        return 0;
    }
    if (state.at("health") != "clean") {
        pause("degraded-health");
        return 0;
    }
    if (contains(state.at("external_flags"), maintenance_flag) &&
        !owned.contains(maintenance_flag)) {
        pause("foreign-flag");
        return 0;
    }
    const double target_weight = std::stod(state.at("target_weight"));
    if (target_weight < std::stod(reweight.at("minimum_weight"))) {
        pause("minimum-weight");
        return 0;
    }
    const long long projected = std::stoll(state.at("dest_used")) +
                                std::stoll(state.at("move_bytes"));
    const double current_ratio =
        static_cast<double>(std::stoll(state.at("dest_used"))) /
        std::stoll(state.at("dest_capacity"));
    const double projected_ratio =
        static_cast<double>(projected) / std::stoll(state.at("dest_capacity"));
    double fullness_limit = std::stod(state.at("backfillfull"));
    if (current_ratio >= std::stod(state.at("nearfull"))) {
        const double configured_headroom = std::max(
            std::stod(fullness.at("backfill_headroom_ratio")),
            std::stod(fullness.at("nearfull_margin_ratio"))
        );
        fullness_limit -= configured_headroom;
    }
    if (projected_ratio >= fullness_limit) {
        pause("fullness-gate");
        return 0;
    }
    if (split(state.at("replica_racks")).contains(state.at("dest_rack"))) {
        pause("failure-domain");
        return 0;
    }
    if (stage == "none" && !owned.contains(maintenance_flag)) {
        std::cout << "flag " << maintenance_flag << " owned\n";
    }
    const bool busy =
        std::stoll(state.at("client_iops")) >=
            std::stoll(recovery.at("high_client_iops")) ||
        std::stoll(state.at("recovery_queue")) >=
            std::stoll(recovery.at("high_queue"));
    std::cout << "tune max_backfills "
              << recovery.at(busy ? "busy_max_backfills" : "quiet_max_backfills")
              << '\n';
    std::cout << "tune recovery_priority "
              << recovery.at(busy ? "busy_recovery_priority"
                                  : "quiet_recovery_priority")
              << '\n';
    if (stage != "reweighted") {
        const double current = std::stod(state.at("current_weight"));
        const double target = target_weight;
        const double configured_step = std::stod(reweight.at("maximum_step"));
        const double supplied_step = std::stod(state.at("max_step"));
        const double step = std::min(configured_step, supplied_step);
        const double next =
            current > target ? std::max(target, current - step)
                             : std::min(target, current + step);
        std::cout << "reweight " << state.at("source_osd") << ' ' << next << '\n';
        std::cout << "checkpoint reweighted\n";
        if (std::fabs(next - target) > 0.000001) {
            std::cout << "publish staged\n";
            return 0;
        }
    }
    std::cout << "move " << state.at("move_bytes") << '\n';
    std::cout << "checkpoint migrated\n";
    std::cout << "clear " << maintenance_flag << '\n';
    std::cout << "publish complete\n";
    return 0;
}
