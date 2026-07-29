#!/bin/bash
set -euo pipefail

mkdir -p /app/src /app/build

cat > /app/src/main.cpp <<'CPP'
#include <nlohmann/json.hpp>

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <map>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

using nlohmann::json;
using nlohmann::ordered_json;
namespace fs = std::filesystem;

// A position is heap sizes in non-increasing order, every entry > 0.
using Position = std::vector<int>;

static Position canonical(const std::vector<int>& v) {
    Position p;
    for (int x : v)
        if (x > 0) p.push_back(x);
    std::sort(p.begin(), p.end(), std::greater<int>());
    return p;
}

static Position redeal(const Position& p) {
    int s = static_cast<int>(p.size());
    Position out;
    for (int h : p)
        if (h - 1 > 0) out.push_back(h - 1);
    out.push_back(s);
    std::sort(out.begin(), out.end(), std::greater<int>());
    return out;
}

static std::string key_of(const Position& p) {
    std::string s;
    for (size_t i = 0; i < p.size(); ++i) {
        if (i) s.push_back(',');
        s += std::to_string(p[i]);
    }
    return s;
}

static void gen_parts(int rem, int mx, Position& cur, std::vector<Position>& out) {
    if (rem == 0) {
        out.push_back(cur);
        return;
    }
    int hi = std::min(rem, mx);
    for (int first = hi; first >= 1; --first) {
        cur.push_back(first);
        gen_parts(rem - first, first, cur, out);
        cur.pop_back();
    }
}

struct SizeAnalysis {
    std::vector<Position> nodes;
    std::unordered_map<std::string, int> idx;
    std::vector<int> succ;
    std::vector<long long> indeg;
    std::vector<int> preperiod;
    std::vector<int> cycle_id;
    std::vector<std::vector<Position>> cycles;  // per cycle id: ordered from smallest
    long long positions = 0;
    long long unreachable_positions = 0;
    int longest_settling = 0;
};

static SizeAnalysis analyze(int n) {
    SizeAnalysis a;
    Position cur;
    gen_parts(n, n, cur, a.nodes);
    int N = static_cast<int>(a.nodes.size());
    a.positions = N;
    a.idx.reserve(static_cast<size_t>(N) * 2);
    for (int i = 0; i < N; ++i) a.idx[key_of(a.nodes[i])] = i;
    a.succ.assign(N, -1);
    a.indeg.assign(N, 0);
    for (int i = 0; i < N; ++i) {
        int j = a.idx.at(key_of(redeal(a.nodes[i])));
        a.succ[i] = j;
        a.indeg[j] += 1;
    }
    std::vector<int> state(N, 0);
    a.preperiod.assign(N, -1);
    a.cycle_id.assign(N, -1);
    std::vector<int> path_pos(N, -1);
    std::vector<std::vector<int>> cycle_members;
    int next_cid = 0;
    for (int s0 = 0; s0 < N; ++s0) {
        if (state[s0] != 0) continue;
        std::vector<int> path;
        int u = s0;
        while (state[u] == 0) {
            state[u] = 1;
            path_pos[u] = static_cast<int>(path.size());
            path.push_back(u);
            u = a.succ[u];
        }
        if (state[u] == 1) {
            int pos = path_pos[u];
            int cid = next_cid++;
            std::vector<int> members;
            for (int k = pos; k < static_cast<int>(path.size()); ++k) {
                int w = path[k];
                a.cycle_id[w] = cid;
                a.preperiod[w] = 0;
                state[w] = 2;
                members.push_back(w);
            }
            cycle_members.push_back(members);
            for (int k = pos - 1; k >= 0; --k) {
                int w = path[k];
                int nx = a.succ[w];
                a.preperiod[w] = a.preperiod[nx] + 1;
                a.cycle_id[w] = a.cycle_id[nx];
                state[w] = 2;
            }
        } else {
            for (int k = static_cast<int>(path.size()) - 1; k >= 0; --k) {
                int w = path[k];
                int nx = a.succ[w];
                a.preperiod[w] = a.preperiod[nx] + 1;
                a.cycle_id[w] = a.cycle_id[nx];
                state[w] = 2;
            }
        }
        for (int w : path) path_pos[w] = -1;
    }
    a.cycles.assign(next_cid, {});
    for (int cid = 0; cid < next_cid; ++cid) {
        const std::vector<int>& members = cycle_members[cid];
        int best = members[0];
        for (int w : members)
            if (a.nodes[w] < a.nodes[best]) best = w;
        std::vector<Position> ordered;
        int c = best;
        do {
            ordered.push_back(a.nodes[c]);
            c = a.succ[c];
        } while (c != best);
        a.cycles[cid] = ordered;
    }
    int longest = 0;
    for (int i = 0; i < N; ++i) longest = std::max(longest, a.preperiod[i]);
    a.longest_settling = longest;
    long long unreach = 0;
    for (int i = 0; i < N; ++i)
        if (a.indeg[i] == 0) ++unreach;
    a.unreachable_positions = unreach;
    return a;
}

static ordered_json sort_recursive(const json& j) {
    if (j.is_object()) {
        std::vector<std::string> keys;
        for (auto it = j.begin(); it != j.end(); ++it) keys.push_back(it.key());
        std::sort(keys.begin(), keys.end());
        ordered_json out = ordered_json::object();
        for (const auto& k : keys) out[k] = sort_recursive(j[k]);
        return out;
    } else if (j.is_array()) {
        ordered_json out = ordered_json::array();
        for (const auto& e : j) out.push_back(sort_recursive(e));
        return out;
    }
    return ordered_json(j);
}

static void write_canonical(const fs::path& p, const ordered_json& payload) {
    std::string text = payload.dump(2, ' ', true);
    text.push_back('\n');
    std::ofstream f(p, std::ios::binary);
    if (!f.is_open()) throw std::runtime_error("cannot open output file: " + p.string());
    f.write(text.data(), static_cast<std::streamsize>(text.size()));
    if (!f.good()) throw std::runtime_error("write failed: " + p.string());
}

static ordered_json pos_to_json(const Position& p) {
    ordered_json arr = ordered_json::array();
    for (int x : p) arr.push_back(x);
    return arr;
}

struct Opening {
    std::string id;
    Position heaps;
    int counters;
};

int main(int argc, char** argv) try {
    if (argc != 3) {
        std::cerr << "usage: redeal <openings_dir> <out_dir>\n";
        return 1;
    }
    fs::path in_dir = argv[1];
    fs::path out_dir = argv[2];
    if (!fs::is_directory(in_dir)) {
        std::cerr << "redeal: openings directory not found: " << in_dir << "\n";
        return 2;
    }
    if (!fs::is_directory(out_dir)) {
        std::cerr << "redeal: output directory not found: " << out_dir << "\n";
        return 2;
    }

    std::vector<fs::path> files;
    for (const auto& e : fs::directory_iterator(in_dir))
        if (e.is_regular_file() && e.path().extension() == ".json")
            files.push_back(e.path());
    std::sort(files.begin(), files.end());

    std::vector<Opening> openings;
    std::map<std::string, int> seen;
    for (const auto& f : files) {
        std::ifstream ifs(f);
        if (!ifs) throw std::runtime_error("cannot open " + f.string());
        json j;
        ifs >> j;
        if (!j.is_object()) throw std::runtime_error("opening is not an object: " + f.string());
        if (!j.contains("id") || !j.at("id").is_string())
            throw std::runtime_error("opening missing string id: " + f.string());
        if (!j.contains("heaps") || !j.at("heaps").is_array())
            throw std::runtime_error("opening missing heaps array: " + f.string());
        std::string id = j.at("id").get<std::string>();
        if (id.empty()) throw std::runtime_error("empty id: " + f.string());
        if (seen.count(id)) throw std::runtime_error("duplicate id: " + id);
        seen[id] = 1;
        std::vector<int> raw;
        for (const auto& h : j.at("heaps")) {
            if (!h.is_number_integer()) throw std::runtime_error("heap not an integer in " + id);
            long long v = h.get<long long>();
            if (v < 1) throw std::runtime_error("heap below 1 in " + id);
            raw.push_back(static_cast<int>(v));
        }
        if (raw.empty()) throw std::runtime_error("empty heaps in " + id);
        Opening op;
        op.id = id;
        op.heaps = canonical(raw);
        op.counters = std::accumulate(op.heaps.begin(), op.heaps.end(), 0);
        openings.push_back(op);
    }

    std::map<int, SizeAnalysis> analyses;
    for (const auto& op : openings)
        if (!analyses.count(op.counters)) analyses.emplace(op.counters, analyze(op.counters));

    std::sort(openings.begin(), openings.end(),
              [](const Opening& x, const Opening& y) { return x.id < y.id; });

    ordered_json openings_arr = ordered_json::array();
    for (const auto& op : openings) {
        SizeAnalysis& A = analyses.at(op.counters);
        int i = A.idx.at(key_of(op.heaps));
        int cid = A.cycle_id[i];
        ordered_json rec;
        rec["arrivals"] = A.indeg[i];
        rec["counters"] = op.counters;
        ordered_json eg = ordered_json::array();
        for (const auto& pos : A.cycles[cid]) eg.push_back(pos_to_json(pos));
        rec["endgame"] = eg;
        rec["endgame_length"] = static_cast<long long>(A.cycles[cid].size());
        rec["heaps"] = pos_to_json(op.heaps);
        rec["id"] = op.id;
        rec["reachable"] = (A.indeg[i] > 0);
        rec["redeals_to_endgame"] = A.preperiod[i];
        openings_arr.push_back(rec);
    }
    ordered_json openings_doc;
    openings_doc["openings"] = openings_arr;

    ordered_json sizes_arr = ordered_json::array();
    for (auto& kv : analyses) {
        int n = kv.first;
        SizeAnalysis& A = kv.second;
        std::vector<const std::vector<Position>*> cyc;
        for (const auto& c : A.cycles) cyc.push_back(&c);
        std::sort(cyc.begin(), cyc.end(),
                  [](const std::vector<Position>* x, const std::vector<Position>* y) {
                      return (*x)[0] < (*y)[0];
                  });
        ordered_json egs = ordered_json::array();
        for (const auto* c : cyc) {
            ordered_json e;
            ordered_json members = ordered_json::array();
            for (const auto& pos : *c) members.push_back(pos_to_json(pos));
            e["cycle"] = members;
            e["length"] = static_cast<long long>(c->size());
            egs.push_back(e);
        }
        ordered_json rec;
        rec["endgames"] = egs;
        rec["longest_settling"] = static_cast<long long>(A.longest_settling);
        rec["positions"] = A.positions;
        rec["size"] = n;
        rec["unreachable_positions"] = A.unreachable_positions;
        sizes_arr.push_back(rec);
    }
    ordered_json sizes_doc;
    sizes_doc["sizes"] = sizes_arr;

    write_canonical(out_dir / "openings.json", sort_recursive(openings_doc));
    write_canonical(out_dir / "sizes.json", sort_recursive(sizes_doc));
    return 0;
} catch (const std::exception& ex) {
    std::cerr << "redeal: " << ex.what() << "\n";
    return 3;
}
CPP

g++ -std=c++17 -O2 -Wall -Wextra -I/usr/include \
    /app/src/main.cpp -o /app/build/redeal

mkdir -p /app/report
/app/build/redeal /app/openings /app/report
