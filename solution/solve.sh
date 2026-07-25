#!/bin/bash
set -euo pipefail
cd /app

# The engine.cpp contains all simulation logic in a single file.
# Multiple sections need correction to comply with the topology contract.

python3 << 'PYEOF'
import re

path = "/app/src/engine.cpp"
with open(path) as f:
    src = f.read()

# Correction 1: Ring size computation.
# Current code sets ring_size = depth (total traversal length).
# Contract Rule R3 says ring_size = number of unique nodes in the cycle ring.
# For watcher->a->b->c->a, depth=4 but ring is {a,b,c} so ring_size=3.
# Need to compute actual ring size by counting nodes from the back-edge target
# forward until we loop back.
old = """    while (link_map.count(current)) {
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
    }"""
new = """    std::vector<std::string> order;
    while (link_map.count(current)) {
        if (visited.count(current)) {
            // Cycle detected. Compute actual ring size by counting nodes
            // from the back-edge target to where it loops.
            int ring_size = 0;
            bool in_ring = false;
            for (const auto& node : order) {
                if (node == current) in_ring = true;
                if (in_ring) ring_size++;
            }
            return {ring_size, true, current, ring_size};
        }
        visited.insert(current);
        order.push_back(current);
        current = link_map.at(current);
        depth++;

        if (depth > max_depth) {
            return {max_depth + 1, false, current, 0};
        }
    }"""
assert old in src, "Ring size patch target not found"
src = src.replace(old, new, 1)

# Correction 2: Propagation segment boundary enforcement.
# Current code propagates taints across ALL zone boundaries.
# Contract Rule P4 says taints must NOT cross segment boundaries.
old = """    // Forward propagation — crosses all zone boundaries to ensure
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
    }"""
new = """    // Forward propagation — bounded by zone (segment) isolation.
    for (auto& r : results) {
        if (r.status == "cycle" || r.status == "dangling") continue;

        int my_segment = r.segment_group;
        std::unordered_set<std::string> visited;
        std::string current = r.path;
        bool has_cycle_taint = false;
        bool has_dangling_taint = false;

        while (link_map.count(current)) {
            if (visited.count(current)) break;
            visited.insert(current);
            std::string next = link_map[current];

            // Only propagate within same segment boundary
            if (segment_map.count(next) && segment_map[next] == my_segment) {
                if (status_map.count(next)) {
                    if (status_map[next] == "cycle") has_cycle_taint = true;
                    if (status_map[next] == "dangling") has_dangling_taint = true;
                }
            }

            current = next;
        }

        if (has_cycle_taint) r.taints.push_back("taint_cycle");
        if (has_dangling_taint) r.taints.push_back("taint_dangling");
    }"""
assert old in src, "Propagation boundary patch target not found"
src = src.replace(old, new, 1)

# Correction 3: Scoring penalty application order.
# Current: (base * weight) - penalties
# Contract Rule S3: max(0, base - penalties) * weight
old = """        // Apply priority weighting first, then deduct penalties from the
        // weighted score per the fleet scoring model.
        double weighted_base = base * weight;

        double penalties = 0.0;
        for (const auto& t : r.taints) {
            if (t == "taint_cycle") penalties += 1.5;
            if (t == "taint_dangling") penalties += 1.0;
        }

        r.health_score = std::round(std::max(0.0, weighted_base - penalties) * 100.0) / 100.0;"""
new = """        // Deduct taint penalties from base score BEFORE applying
        // priority weighting per contract Rule S3.
        double penalties = 0.0;
        for (const auto& t : r.taints) {
            if (t == "taint_cycle") penalties += 1.5;
            if (t == "taint_dangling") penalties += 1.0;
        }

        r.health_score = std::round(std::max(0.0, base - penalties) * weight * 100.0) / 100.0;"""
assert old in src, "Scoring order patch target not found"
src = src.replace(old, new, 1)

# Correction 4: Segment normalization denominator.
# Current: sum_max += 10.0 (uniform)
# Contract Rule S4: sum_max += 10.0 * priority_weight
old = """            // Normalization: each entry contributes at most the base healthy
            // score (10.0) regardless of priority, per zone scoring rules.
            sum_max += 10.0;"""
new = """            // Normalization: max possible is base score * priority weight
            sum_max += 10.0 * get_priority_weight(e->priority);"""
assert old in src, "Denominator patch target not found"
src = src.replace(old, new, 1)

# Correction 5: Fleet score computation.
# Current: simple average of segment scores
# Contract Rule S5: entry-count-weighted average
old = """double compute_fleet_score(const std::vector<SegmentSummary>& segments) {
    if (segments.empty()) return 0.0;
    // Fleet score: uniform average of zone scores.
    double total = 0.0;
    for (const auto& seg : segments) total += seg.aggregate_score;
    return std::round((total / segments.size()) * 10000.0) / 10000.0;
}"""
new = """double compute_fleet_score(const std::vector<SegmentSummary>& segments) {
    if (segments.empty()) return 0.0;
    // Fleet score: entry-count-weighted average per contract Rule S5.
    double numerator = 0.0;
    double denominator = 0.0;
    for (const auto& seg : segments) {
        numerator += seg.aggregate_score * seg.total;
        denominator += seg.total;
    }
    if (denominator == 0) return 0.0;
    return std::round((numerator / denominator) * 10000.0) / 10000.0;
}"""
assert old in src, "Fleet score patch target not found"
src = src.replace(old, new, 1)

# Correction 6: Verdict determination.
# Current: only uses fleet_score (healthy if >= threshold, else degraded)
# Contract requires: V2 (worst segment), V3 (all-healthy override), V4 (critical count)
old = """    // Verdict: healthy if fleet score meets threshold, else degraded.
    if (report.summary.fleet_score >= config.score_threshold) {
        report.overall_status = "healthy";
    } else {
        report.overall_status = "degraded";
    }"""
new = """    // V2: overall = worst segment verdict
    bool has_critical = false;
    bool has_degraded = false;
    bool all_healthy = true;
    for (const auto& seg : report.segments) {
        if (seg.verdict == "critical") { has_critical = true; all_healthy = false; }
        else if (seg.verdict == "degraded") { has_degraded = true; all_healthy = false; }
    }
    if (has_critical) report.overall_status = "critical";
    else if (has_degraded) report.overall_status = "degraded";
    else report.overall_status = "healthy";

    // V3: healthy override only if fleet >= threshold AND all segments healthy
    if (report.summary.fleet_score >= config.score_threshold && all_healthy) {
        report.overall_status = "healthy";
    }

    // V4: critical count escalation (dangling + cycles > 4)
    int critical_count = report.summary.dangling + report.summary.cycles;
    if (critical_count > 4) {
        report.overall_status = "critical";
    }"""
assert old in src, "Verdict patch target not found"
src = src.replace(old, new, 1)

with open(path, "w") as f:
    f.write(src)

print("All 6 corrections applied successfully.")
PYEOF

# Rebuild and run
make clean && make
mkdir -p /app/output
./bin/symlink-health --manifest /app/data/manifest.json --config /app/config --output /app/output/health_report.json
