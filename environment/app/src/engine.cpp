/*
 * Fleet Defense Simulation Engine
 * ================================
 * Simulates supply route topology health across fleet sectors.
 * Routes are symlink chains; the engine resolves chains, classifies
 * faults, propagates damage, scores zones, and determines verdicts.
 *
 * Configuration: /app/config/health_config.json
 * Ruleset:       /app/docs/topology-contract.md
 */

#include "../include/types.h"
#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <unordered_set>
#include <unordered_map>
#include <algorithm>
#include <cmath>
#include <filesystem>
#include <nlohmann/json.hpp>

namespace fs = std::filesystem;
using json = nlohmann::json;

// ============================================================
// Configuration Loading
// ============================================================

HealthConfig load_config(const std::string& config_dir) {
    HealthConfig cfg;
    cfg.max_chain_depth = 16;
    cfg.check_permissions = true;
    cfg.detect_cycles = true;
    cfg.propagation_enabled = false;
    cfg.config_source = "defaults";
    cfg.permission_mask = 0x1FF;
    cfg.score_threshold = 0.75;
    cfg.scoring_mode = "simple";

    std::string base_path = config_dir + "/health_config.json";
    if (fs::exists(base_path)) {
        std::ifstream f(base_path);
        json j = json::parse(f);
        if (j.contains("max_chain_depth")) cfg.max_chain_depth = j["max_chain_depth"];
        if (j.contains("check_permissions")) cfg.check_permissions = j["check_permissions"];
        if (j.contains("detect_cycles")) cfg.detect_cycles = j["detect_cycles"];
        if (j.contains("propagation_enabled")) cfg.propagation_enabled = j["propagation_enabled"];
        if (j.contains("permission_mask")) cfg.permission_mask = j["permission_mask"];
        if (j.contains("score_threshold")) cfg.score_threshold = j["score_threshold"];
        if (j.contains("scoring_mode")) cfg.scoring_mode = j["scoring_mode"];
        cfg.config_source = "health_config.json";
    }

    return cfg;
}

// ============================================================
// Route Resolution and Fault Classification
// ============================================================

struct ChainResult {
    int depth;
    bool cycle;
    std::string final_target;
    int ring_size;
};

ChainResult resolve_chain(const std::string& start,
                          const std::unordered_map<std::string, std::string>& link_map,
                          int max_depth) {
    std::unordered_set<std::string> visited;
    std::string current = start;
    int depth = 0;

    while (link_map.count(current)) {
        if (visited.count(current)) {
            // Cycle detected. Ring size is the traversal length to the
            // back-edge, capturing the full route depth per simulation rules.
            return {depth, true, current, depth};
        }
        visited.insert(current);
        current = link_map.at(current);
        depth++;

        if (depth > max_depth) {
            return {max_depth + 1, false, current, 0};
        }
    }

    return {depth, false, current, 0};
}

std::vector<HealthResult> resolve_and_classify(
    const std::vector<SymlinkEntry>& links,
    const HealthConfig& config) {

    std::unordered_map<std::string, std::string> link_map;
    for (const auto& l : links) link_map[l.path] = l.target;

    std::unordered_set<std::string> tracked_paths;
    for (const auto& l : links) tracked_paths.insert(l.path);

    std::unordered_map<std::string, uint16_t> perm_map;
    for (const auto& l : links) perm_map[l.path] = l.permissions;

    std::vector<HealthResult> results;

    for (const auto& link : links) {
        HealthResult r;
        r.path = link.path;
        r.segment_group = link.segment_group;
        r.priority = link.priority;
        r.chain_depth = 0;
        r.final_target = link.target;
        r.status = "healthy";
        r.health_score = 0.0;
        r.detail = "";

        // Dangling check
        if (!link.target_exists && !tracked_paths.count(link.target)) {
            r.status = "dangling";
            r.chain_depth = 0;
            r.final_target = link.target;
            r.detail = "target does not exist";
            results.push_back(r);
            continue;
        }

        // Cycle and depth analysis
        if (config.detect_cycles) {
            auto chain = resolve_chain(link.path, link_map, config.max_chain_depth);

            if (chain.cycle) {
                r.status = "cycle";
                r.chain_depth = chain.ring_size;
                r.final_target = chain.final_target;
                r.detail = "circular reference detected at " + chain.final_target;
                results.push_back(r);
                continue;
            }

            if (chain.depth > config.max_chain_depth) {
                r.status = "excessive_depth";
                r.chain_depth = config.max_chain_depth + 1;
                r.final_target = chain.final_target;
                r.detail = "chain depth exceeds limit " +
                           std::to_string(config.max_chain_depth);
                results.push_back(r);
                continue;
            }

            r.chain_depth = chain.depth;
            r.final_target = chain.final_target;
        }

        // Permission comparison against direct target
        if (config.check_permissions && perm_map.count(link.target)) {
            uint16_t link_masked = link.permissions & config.permission_mask;
            uint16_t target_masked = perm_map[link.target] & config.permission_mask;
            if (link_masked != target_masked) {
                r.status = "permission_fault";
                r.detail = "permission mismatch under mask " +
                           std::to_string(config.permission_mask);
                results.push_back(r);
                continue;
            }
        }

        r.status = "healthy";
        r.detail = "";
        results.push_back(r);
    }

    return results;
}

// ============================================================
// Damage Propagation
// ============================================================

void propagate_taints(std::vector<HealthResult>& results,
                      const std::vector<SymlinkEntry>& links,
                      const HealthConfig& config) {
    if (!config.propagation_enabled) return;

    std::unordered_map<std::string, std::string> link_map;
    std::unordered_map<std::string, int> segment_map;
    for (const auto& l : links) {
        link_map[l.path] = l.target;
        segment_map[l.path] = l.segment_group;
    }

    std::unordered_map<std::string, std::string> status_map;
    for (const auto& r : results) status_map[r.path] = r.status;

    // Self-taint for faulted entries
    for (auto& r : results) {
        if (r.status == "cycle") r.taints.push_back("taint_cycle");
        else if (r.status == "dangling") r.taints.push_back("taint_dangling");
    }

    // Forward propagation — crosses all zone boundaries to ensure
    // complete damage visibility per the fleet observability model.
    for (auto& r : results) {
        if (r.status == "cycle" || r.status == "dangling") continue;

        std::unordered_set<std::string> visited;
        std::string current = r.path;
        bool has_cycle_taint = false;
        bool has_dangling_taint = false;

        while (link_map.count(current)) {
            if (visited.count(current)) break;
            visited.insert(current);
            std::string next = link_map[current];

            if (status_map.count(next)) {
                if (status_map[next] == "cycle") has_cycle_taint = true;
                if (status_map[next] == "dangling") has_dangling_taint = true;
            }

            current = next;
        }

        if (has_cycle_taint) r.taints.push_back("taint_cycle");
        if (has_dangling_taint) r.taints.push_back("taint_dangling");
    }
}

// ============================================================
// Zone Scoring and Fleet Aggregation
// ============================================================

double get_base_score(const std::string& status) {
    if (status == "healthy") return 10.0;
    if (status == "dangling") return 5.0;
    if (status == "cycle") return 2.0;
    if (status == "excessive_depth") return 7.0;
    if (status == "permission_fault") return 6.0;
    return 0.0;
}

double get_priority_weight(int priority) {
    if (priority == 1) return 1.0;
    if (priority == 2) return 0.8;
    if (priority == 3) return 0.5;
    return 1.0;
}

void compute_scores(std::vector<HealthResult>& results, const HealthConfig& config) {
    for (auto& r : results) {
        double base = get_base_score(r.status);
        double weight = get_priority_weight(r.priority);

        // Apply priority weighting first, then deduct penalties from the
        // weighted score per the fleet scoring model.
        double weighted_base = base * weight;

        double penalties = 0.0;
        for (const auto& t : r.taints) {
            if (t == "taint_cycle") penalties += 1.5;
            if (t == "taint_dangling") penalties += 1.0;
        }

        r.health_score = std::round(std::max(0.0, weighted_base - penalties) * 100.0) / 100.0;
    }
}

void compute_segments(HealthReport& report, const std::vector<SymlinkEntry>& links,
                      const HealthConfig& config) {
    std::unordered_map<int, std::vector<const HealthResult*>> by_segment;
    for (const auto& e : report.entries) by_segment[e.segment_group].push_back(&e);

    std::unordered_map<int, std::string> seg_names = {
        {1, "core-libs"}, {2, "config-chain"}, {3, "runtime"},
        {4, "shared"}, {5, "deep-resolve"}, {6, "transient"},
        {7, "circular-deps"}, {8, "permission-set"}
    };

    for (auto& [seg_id, entries] : by_segment) {
        SegmentSummary seg;
        seg.id = seg_id;
        seg.name = seg_names.count(seg_id) ? seg_names[seg_id] : "unknown";
        seg.total = static_cast<int>(entries.size());
        seg.healthy = 0;
        seg.unhealthy = 0;

        double sum_scores = 0.0;
        double sum_max = 0.0;

        for (const auto* e : entries) {
            if (e->status == "healthy") seg.healthy++;
            else seg.unhealthy++;
            sum_scores += e->health_score;
            // Normalization: each entry contributes at most the base healthy
            // score (10.0) regardless of priority, per zone scoring rules.
            sum_max += 10.0;
        }

        if (sum_max > 0) {
            seg.aggregate_score = std::round((sum_scores / sum_max) * 10000.0) / 10000.0;
        } else {
            seg.aggregate_score = 0.0;
        }

        if (seg.aggregate_score >= config.score_threshold) seg.verdict = "healthy";
        else if (seg.aggregate_score >= config.score_threshold * 0.5) seg.verdict = "degraded";
        else seg.verdict = "critical";

        report.segments.push_back(seg);
    }

    std::sort(report.segments.begin(), report.segments.end(),
              [](const SegmentSummary& a, const SegmentSummary& b) {
                  return a.id < b.id;
              });
}

double compute_fleet_score(const std::vector<SegmentSummary>& segments) {
    if (segments.empty()) return 0.0;
    // Fleet score: uniform average of zone scores.
    double total = 0.0;
    for (const auto& seg : segments) total += seg.aggregate_score;
    return std::round((total / segments.size()) * 10000.0) / 10000.0;
}

// ============================================================
// Report Generation and Verdict
// ============================================================

void write_report(HealthReport& report, const HealthConfig& config,
                  const std::string& timestamp, const std::string& output_path) {
    report.summary = {0, 0, 0, 0, 0, 0, 0.0};
    for (const auto& e : report.entries) {
        report.summary.total++;
        if (e.status == "healthy") report.summary.healthy++;
        else if (e.status == "dangling") report.summary.dangling++;
        else if (e.status == "cycle") report.summary.cycles++;
        else if (e.status == "excessive_depth") report.summary.excessive_depth++;
        else if (e.status == "permission_fault") report.summary.permission_fault++;
    }

    report.summary.fleet_score = compute_fleet_score(report.segments);

    // Verdict: healthy if fleet score meets threshold, else degraded.
    if (report.summary.fleet_score >= config.score_threshold) {
        report.overall_status = "healthy";
    } else {
        report.overall_status = "degraded";
    }

    json output;
    output["summary"] = {
        {"total", report.summary.total}, {"healthy", report.summary.healthy},
        {"dangling", report.summary.dangling}, {"cycles", report.summary.cycles},
        {"excessive_depth", report.summary.excessive_depth},
        {"permission_fault", report.summary.permission_fault},
        {"fleet_score", report.summary.fleet_score}
    };
    output["overall_status"] = report.overall_status;

    json entries_arr = json::array();
    for (const auto& e : report.entries) {
        json entry;
        entry["path"] = e.path;
        entry["status"] = e.status;
        entry["chain_depth"] = e.chain_depth;
        entry["final_target"] = e.final_target;
        entry["segment_group"] = e.segment_group;
        entry["health_score"] = e.health_score;
        entry["taints"] = e.taints;
        entry["detail"] = e.detail;
        entries_arr.push_back(entry);
    }
    output["entries"] = entries_arr;

    json segments_arr = json::array();
    for (const auto& s : report.segments) {
        json seg;
        seg["id"] = s.id; seg["name"] = s.name;
        seg["total"] = s.total; seg["healthy"] = s.healthy;
        seg["unhealthy"] = s.unhealthy;
        seg["aggregate_score"] = s.aggregate_score;
        seg["verdict"] = s.verdict;
        segments_arr.push_back(seg);
    }
    output["segments"] = segments_arr;

    output["metadata"] = {
        {"max_chain_depth", config.max_chain_depth},
        {"permission_mask", config.permission_mask},
        {"score_threshold", config.score_threshold},
        {"scoring_mode", config.scoring_mode},
        {"config_source", config.config_source},
        {"timestamp", timestamp}
    };

    fs::path out_dir = fs::path(output_path).parent_path();
    if (!out_dir.empty()) fs::create_directories(out_dir);

    std::ofstream out(output_path);
    out << output.dump(2) << std::endl;
}

// ============================================================
// Main — Simulation Entry Point
// ============================================================

std::vector<SymlinkEntry> load_manifest(const std::string& path, std::string& timestamp) {
    std::vector<SymlinkEntry> entries;
    std::ifstream f(path);
    json j = json::parse(f);
    timestamp = j.value("scan_timestamp", "");
    for (const auto& item : j["symlinks"]) {
        SymlinkEntry e;
        e.path = item["path"];
        e.target = item["target"];
        e.permissions = item.value("permissions", 0644);
        e.target_exists = item.value("target_exists", true);
        e.segment_group = item.value("segment_group", 0);
        e.priority = item.value("priority", 1);
        entries.push_back(e);
    }
    return entries;
}

int main(int argc, char* argv[]) {
    std::string manifest_path, config_dir, output_path;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--manifest" && i + 1 < argc) manifest_path = argv[++i];
        else if (arg == "--config" && i + 1 < argc) config_dir = argv[++i];
        else if (arg == "--output" && i + 1 < argc) output_path = argv[++i];
    }

    if (manifest_path.empty() || config_dir.empty() || output_path.empty()) {
        std::cerr << "Usage: symlink-health --manifest <path> --config <dir> --output <path>\n";
        return 1;
    }

    std::string timestamp;
    auto cfg = load_config(config_dir);
    auto links = load_manifest(manifest_path, timestamp);
    auto results = resolve_and_classify(links, cfg);

    propagate_taints(results, links, cfg);
    compute_scores(results, cfg);

    HealthReport report;
    report.entries = results;
    report.config = cfg;

    compute_segments(report, links, cfg);
    write_report(report, cfg, timestamp, output_path);

    return 0;
}
