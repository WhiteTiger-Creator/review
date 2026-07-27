#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <numeric>
#include <set>
#include <sstream>
#include <string>
#include <vector>

namespace {

constexpr int kMissing = -1;

struct Rat {
    long long n = 0;
    long long d = 1;
};

Rat make_rat(long long n, long long d) {
    if (d < 0) {
        n = -n;
        d = -d;
    }
    long long g = std::gcd(n < 0 ? -n : n, d);
    if (g != 0) {
        n /= g;
        d /= g;
    }
    return Rat{n, d};
}

Rat add(Rat a, Rat b) {
    return make_rat(a.n * b.d + b.n * a.d, a.d * b.d);
}

Rat sub(Rat a, Rat b) {
    return make_rat(a.n * b.d - b.n * a.d, a.d * b.d);
}

Rat mul(Rat a, Rat b) {
    return make_rat(a.n * b.n, a.d * b.d);
}

int compare(Rat a, Rat b) {
    long long left = a.n * b.d;
    long long right = b.n * a.d;
    if (left < right) {
        return -1;
    }
    return left > right ? 1 : 0;
}

std::string render(Rat a) {
    return std::to_string(a.n) + "/" + std::to_string(a.d);
}

struct Row {
    std::vector<int> features;
    int label = 0;
};

struct Surrogate {
    Rat association;
    int feature = 0;
    int threshold = 0;
    char direction = 'F';
};

struct Node {
    int id = 0;
    int depth = 0;
    int size = 0;
    bool leaf = true;
    int label = 0;
    int feature = 0;
    int threshold = 0;
    Rat gain;
    std::vector<Surrogate> surrogates;
    std::vector<int> rows_at;
    bool block_left = true;
    int left = -1;
    int right = -1;
};

using Table = std::vector<Row>;

Rat gini(const Table& rows, const std::vector<int>& subset, int classes) {
    if (subset.empty()) {
        return Rat{0, 1};
    }
    std::vector<long long> counts(classes, 0);
    for (int i : subset) {
        counts[rows[i].label] += 1;
    }
    long long n = static_cast<long long>(subset.size());
    Rat acc{0, 1};
    for (long long c : counts) {
        acc = add(acc, make_rat(c * c, n * n));
    }
    return sub(Rat{1, 1}, acc);
}

int majority(const Table& rows, const std::vector<int>& subset, int classes) {
    std::vector<long long> counts(classes, 0);
    for (int i : subset) {
        counts[rows[i].label] += 1;
    }
    int best = 0;
    for (int c = 1; c < classes; ++c) {
        if (counts[c] > counts[best]) {
            best = c;
        }
    }
    return best;
}

struct Split {
    bool found = false;
    int feature = 0;
    int threshold = 0;
    Rat gain;
};

Split best_split(const Table& rows, const std::vector<int>& subset, int features, int classes) {
    Split best;
    for (int j = 0; j < features; ++j) {
        std::vector<int> observed;
        for (int i : subset) {
            if (rows[i].features[j] != kMissing) {
                observed.push_back(i);
            }
        }
        if (observed.size() < 2) {
            continue;
        }
        std::set<int> distinct;
        for (int i : observed) {
            distinct.insert(rows[i].features[j]);
        }
        if (distinct.size() < 2) {
            continue;
        }
        Rat parent = gini(rows, observed, classes);
        long long total = static_cast<long long>(observed.size());
        std::vector<int> values(distinct.begin(), distinct.end());
        for (size_t vi = 0; vi + 1 < values.size(); ++vi) {
            int t = values[vi];
            std::vector<int> left;
            std::vector<int> right;
            for (int i : observed) {
                if (rows[i].features[j] <= t) {
                    left.push_back(i);
                } else {
                    right.push_back(i);
                }
            }
            Rat gain = sub(parent, mul(make_rat(static_cast<long long>(left.size()), total),
                                       gini(rows, left, classes)));
            gain = sub(gain, mul(make_rat(static_cast<long long>(right.size()), total),
                                 gini(rows, right, classes)));
            if (!best.found || compare(gain, best.gain) > 0) {
                best.found = true;
                best.feature = j;
                best.threshold = t;
                best.gain = gain;
            }
        }
    }
    return best;
}

std::vector<Surrogate> fit_surrogates(const Table& rows, const std::vector<int>& subset,
                                      int features, int jstar, int tstar) {
    std::vector<Surrogate> found;
    for (int k = 0; k < features; ++k) {
        if (k == jstar) {
            continue;
        }
        std::vector<int> pool;
        for (int i : subset) {
            if (rows[i].features[k] != kMissing && rows[i].features[jstar] != kMissing) {
                pool.push_back(i);
            }
        }
        if (pool.empty()) {
            continue;
        }
        std::vector<char> goes_left(pool.size(), 0);
        long long left_count = 0;
        for (size_t pi = 0; pi < pool.size(); ++pi) {
            bool value = rows[pool[pi]].features[jstar] <= tstar;
            goes_left[pi] = value ? 1 : 0;
            if (value) {
                left_count += 1;
            }
        }
        long long right_count = static_cast<long long>(pool.size()) - left_count;
        long long smaller = std::min(left_count, right_count);
        if (smaller == 0) {
            continue;
        }
        std::set<int> distinct;
        for (int i : pool) {
            distinct.insert(rows[i].features[k]);
        }
        if (distinct.size() < 2) {
            continue;
        }
        std::vector<int> values(distinct.begin(), distinct.end());
        bool have = false;
        long long best_agree = 0;
        int best_u = 0;
        char best_dir = 'F';
        std::vector<size_t> by_value(pool.size());
        for (size_t pi = 0; pi < pool.size(); ++pi) {
            by_value[pi] = pi;
        }
        std::sort(by_value.begin(), by_value.end(), [&](size_t a, size_t b) {
            return rows[pool[a]].features[k] < rows[pool[b]].features[k];
        });
        long long right_total = static_cast<long long>(pool.size()) - left_count;
        long long seen_left = 0;
        long long seen_right = 0;
        size_t cursor = 0;
        for (size_t vi = 0; vi + 1 < values.size(); ++vi) {
            int u = values[vi];
            while (cursor < by_value.size()
                   && rows[pool[by_value[cursor]]].features[k] <= u) {
                if (goes_left[by_value[cursor]]) {
                    seen_left += 1;
                } else {
                    seen_right += 1;
                }
                cursor += 1;
            }
            long long forward = seen_left + (right_total - seen_right);
            long long reverse = static_cast<long long>(pool.size()) - forward;
            if (!have || forward > best_agree) {
                have = true;
                best_agree = forward;
                best_u = u;
                best_dir = 'F';
            }
            if (reverse > best_agree) {
                best_agree = reverse;
                best_u = u;
                best_dir = 'V';
            }
        }
        if (!have) {
            continue;
        }
        Rat association =
            make_rat(smaller - (static_cast<long long>(pool.size()) - best_agree), smaller);
        if (association.n > 0) {
            found.push_back(Surrogate{association, k, best_u, best_dir});
        }
    }
    std::stable_sort(found.begin(), found.end(), [](const Surrogate& a, const Surrogate& b) {
        int c = compare(a.association, b.association);
        if (c != 0) {
            return c > 0;
        }
        if (a.feature != b.feature) {
            return a.feature < b.feature;
        }
        if (a.threshold != b.threshold) {
            return a.threshold < b.threshold;
        }
        return a.direction == 'F' && b.direction != 'F';
    });
    return found;
}

std::pair<std::string, bool> route(const std::vector<int>& features_row, const Node& node) {
    if (features_row[node.feature] != kMissing) {
        return {"P", features_row[node.feature] <= node.threshold};
    }
    for (size_t rank = 0; rank < node.surrogates.size(); ++rank) {
        const Surrogate& s = node.surrogates[rank];
        if (features_row[s.feature] != kMissing) {
            bool left = s.direction == 'F' ? features_row[s.feature] <= s.threshold
                                           : features_row[s.feature] > s.threshold;
            return {"S" + std::to_string(rank + 1), left};
        }
    }
    return {"B", node.block_left};
}

int build(std::vector<Node>& tree, const Table& rows, const std::vector<int>& subset, int features,
          int classes, int depth, int max_depth, int min_split, int& counter) {
    Node node;
    node.id = counter++;
    node.depth = depth;
    node.size = static_cast<int>(subset.size());
    node.leaf = true;
    node.label = majority(rows, subset, classes);
    node.rows_at = subset;
    int index = static_cast<int>(tree.size());
    tree.push_back(node);

    std::set<int> labels;
    for (int i : subset) {
        labels.insert(rows[i].label);
    }
    if (depth >= max_depth || labels.size() <= 1 ||
        static_cast<int>(subset.size()) < min_split) {
        return index;
    }
    Split chosen = best_split(rows, subset, features, classes);
    if (!chosen.found) {
        return index;
    }
    tree[index].leaf = false;
    tree[index].feature = chosen.feature;
    tree[index].threshold = chosen.threshold;
    tree[index].gain = chosen.gain;
    tree[index].surrogates = fit_surrogates(rows, subset, features, chosen.feature, chosen.threshold);

    long long observed = 0;
    long long observed_left = 0;
    for (int i : subset) {
        if (rows[i].features[chosen.feature] != kMissing) {
            observed += 1;
            if (rows[i].features[chosen.feature] <= chosen.threshold) {
                observed_left += 1;
            }
        }
    }
    tree[index].block_left = observed_left >= observed - observed_left;

    std::vector<int> left;
    std::vector<int> right;
    for (int i : subset) {
        auto decision = route(rows[i].features, tree[index]);
        if (decision.second) {
            left.push_back(i);
        } else {
            right.push_back(i);
        }
    }
    int left_index =
        build(tree, rows, left, features, classes, depth + 1, max_depth, min_split, counter);
    int right_index =
        build(tree, rows, right, features, classes, depth + 1, max_depth, min_split, counter);
    tree[index].left = left_index;
    tree[index].right = right_index;
    return index;
}

void importances(const std::vector<Node>& tree, std::vector<Rat>& primary,
                 std::vector<Rat>& substitute) {
    for (const Node& node : tree) {
        if (node.leaf) {
            continue;
        }
        Rat weight = make_rat(static_cast<long long>(node.size), 1);
        primary[node.feature] = add(primary[node.feature], mul(weight, node.gain));
        for (const Surrogate& s : node.surrogates) {
            substitute[s.feature] = add(substitute[s.feature], mul(weight, s.association));
        }
    }
}

std::pair<Rat, int> descend(const std::vector<int>& features_row, const std::vector<Node>& tree,
                            int root) {
    Rat evidence = make_rat(1, 1);
    int current = root;
    while (!tree[current].leaf) {
        auto decision = route(features_row, tree[current]);
        if (decision.first == "B") {
            evidence = make_rat(0, 1);
        } else if (decision.first != "P") {
            int rank = std::stoi(decision.first.substr(1));
            const Rat& association = tree[current].surrogates[rank - 1].association;
            if (compare(association, evidence) < 0) {
                evidence = association;
            }
        }
        current = decision.second ? tree[current].left : tree[current].right;
    }
    return {evidence, current};
}

std::vector<Rat> posterior(const Table& rows, const std::vector<int>& subset, int classes) {
    std::vector<long long> counts(classes, 0);
    for (int i : subset) {
        counts[rows[i].label] += 1;
    }
    std::vector<Rat> out;
    for (int c = 0; c < classes; ++c) {
        out.push_back(make_rat(counts[c], static_cast<long long>(subset.size())));
    }
    return out;
}

bool parse_int(const std::string& token, int& out) {
    size_t start = 0;
    while (start < token.size() && token[start] == '+') {
        ++start;
    }
    if (start >= token.size()) {
        return false;
    }
    for (size_t i = start; i < token.size(); ++i) {
        if (token[i] < '0' || token[i] > '9') {
            return false;
        }
    }
    out = std::stoi(token.substr(start));
    return true;
}

bool handle(const std::map<std::string, Table>& tables, const std::vector<std::string>& parts,
            std::vector<std::string>& lines) {
    if (parts.size() != 5) {
        return false;
    }
    auto train_it = tables.find(parts[1]);
    auto query_it = tables.find(parts[2]);
    if (train_it == tables.end() || query_it == tables.end()) {
        return false;
    }
    int max_depth = 0;
    int min_split = 0;
    if (!parse_int(parts[3], max_depth) || !parse_int(parts[4], min_split)) {
        return false;
    }
    if (max_depth < 1 || min_split < 2) {
        return false;
    }
    const Table& rows = train_it->second;
    const Table& probes = query_it->second;
    if (rows.empty() || probes.empty()) {
        return false;
    }
    size_t features = rows[0].features.size();
    for (const Row& r : rows) {
        if (r.features.size() != features) {
            return false;
        }
    }
    for (const Row& p : probes) {
        if (p.features.size() != features) {
            return false;
        }
    }
    int classes = 0;
    for (const Row& r : rows) {
        classes = std::max(classes, r.label + 1);
    }
    std::vector<int> subset(rows.size());
    for (size_t i = 0; i < rows.size(); ++i) {
        subset[i] = static_cast<int>(i);
    }
    std::vector<Node> tree;
    int counter = 0;
    int root = build(tree, rows, subset, static_cast<int>(features), classes, 0, max_depth,
                     min_split, counter);
    const std::string& qid = parts[0];
    std::vector<Rat> primary(features, make_rat(0, 1));
    std::vector<Rat> substitute(features, make_rat(0, 1));
    importances(tree, primary, substitute);
    for (size_t j = 0; j < features; ++j) {
        lines.push_back(qid + " V " + std::to_string(j) + " P " + render(primary[j]) + " S " +
                        render(substitute[j]));
    }
    for (size_t index = 0; index < probes.size(); ++index) {
        std::pair<Rat, int> reached = descend(probes[index].features, tree, root);
        const Node& leaf = tree[reached.second];
        Rat impurity = gini(rows, leaf.rows_at, classes);
        std::vector<Rat> spread = posterior(rows, leaf.rows_at, classes);
        std::string shown;
        for (size_t c = 0; c < spread.size(); ++c) {
            if (c != 0) {
                shown += " ";
            }
            shown += render(spread[c]);
        }
        lines.push_back(qid + " Q " + std::to_string(index) + " C " + std::to_string(leaf.label) +
                        " N " + std::to_string(leaf.size) + " I " + render(impurity) + " E " +
                        render(reached.first) + " D " + shown);
    }
    std::vector<const Node*> splits;
    for (const Node& n : tree) {
        if (!n.leaf) {
            splits.push_back(&n);
        }
    }
    std::sort(splits.begin(), splits.end(),
              [](const Node* a, const Node* b) { return a->id < b->id; });
    for (const Node* n : splits) {
        lines.push_back(qid + " D " + std::to_string(n->id) + " V " +
                        std::to_string(n->feature) + " T " + std::to_string(n->threshold) +
                        " N " + std::to_string(n->size) + " G " + render(n->gain));
    }
    std::vector<const Node*> ordered;
    for (const Node& n : tree) {
        if (!n.leaf) {
            ordered.push_back(&n);
        }
    }
    std::sort(ordered.begin(), ordered.end(),
              [](const Node* a, const Node* b) { return a->id < b->id; });
    for (const Node* n : ordered) {
        for (size_t rank = 0; rank < n->surrogates.size(); ++rank) {
            const Surrogate& s = n->surrogates[rank];
            lines.push_back(qid + " G " + std::to_string(n->id) + " R " +
                            std::to_string(rank + 1) + " V " + std::to_string(s.feature) +
                            " T " + std::to_string(s.threshold) + " D " +
                            std::string(1, s.direction) + " A " + render(s.association));
        }
    }
    return true;
}

std::map<std::string, Table> read_tables(const std::string& directory) {
    std::map<std::string, Table> out;
    std::vector<std::string> names;
    for (const auto& entry : std::filesystem::directory_iterator(directory)) {
        std::string name = entry.path().filename().string();
        if (name.size() > 4 && name.substr(name.size() - 4) == ".csv") {
            names.push_back(name);
        }
    }
    std::sort(names.begin(), names.end());
    for (const std::string& name : names) {
        std::ifstream in(directory + "/" + name);
        std::string line;
        Table rows;
        bool header = true;
        while (std::getline(in, line)) {
            while (!line.empty() && (line.back() == '\r' || line.back() == ' ')) {
                line.pop_back();
            }
            if (line.empty()) {
                continue;
            }
            if (header) {
                header = false;
                continue;
            }
            std::vector<int> cells;
            std::stringstream ss(line);
            std::string cell;
            while (std::getline(ss, cell, ',')) {
                cells.push_back(std::stoi(cell));
            }
            Row row;
            row.label = cells.back();
            cells.pop_back();
            row.features = cells;
            rows.push_back(row);
        }
        out[name.substr(0, name.size() - 4)] = rows;
    }
    return out;
}

}

int main(int argc, char** argv) {
    if (argc < 3) {
        return 1;
    }
    std::map<std::string, Table> tables = read_tables(argv[1]);
    std::ifstream queries(argv[2]);
    std::string line;
    std::string out;
    while (std::getline(queries, line)) {
        std::stringstream ss(line);
        std::vector<std::string> parts;
        std::string token;
        while (ss >> token) {
            parts.push_back(token);
        }
        if (parts.empty()) {
            continue;
        }
        std::vector<std::string> lines;
        if (handle(tables, parts, lines)) {
            for (const std::string& row : lines) {
                out += row;
                out += "\n";
            }
        } else {
            out += parts[0] + " REJECT\n";
        }
    }
    std::cout << out;
    return 0;
}
