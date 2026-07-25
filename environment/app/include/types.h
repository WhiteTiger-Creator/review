#pragma once
#include <string>
#include <vector>
#include <cstdint>

struct SymlinkEntry {
    std::string path;
    std::string target;
    uint16_t permissions;
    bool target_exists;
    int segment_group;
    int priority;
};

struct HealthResult {
    std::string path;
    std::string status;       // fault class
    int chain_depth;
    std::string final_target;
    std::string detail;
    int segment_group;
    double health_score;
    std::vector<std::string> taints;
    int priority;
};

struct SegmentSummary {
    int id;
    std::string name;
    int total;
    int healthy;
    int unhealthy;
    double aggregate_score;
    std::string verdict;
};

struct HealthConfig {
    int max_chain_depth;
    bool check_permissions;
    bool detect_cycles;
    bool propagation_enabled;
    std::string config_source;
    uint16_t permission_mask;
    double score_threshold;
    std::string scoring_mode;
};

struct HealthSummary {
    int total;
    int healthy;
    int dangling;
    int cycles;
    int excessive_depth;
    int permission_fault;
    double fleet_score;
};

struct HealthReport {
    HealthSummary summary;
    std::string overall_status;
    std::vector<HealthResult> entries;
    std::vector<SegmentSummary> segments;
    HealthConfig config;
};
