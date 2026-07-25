#!/bin/bash
set -euo pipefail

cat > /app/src/retro.cpp <<'EOF'
#include "retro.hpp"
#include "rules.hpp"
#include <cctype>
#include <deque>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>

namespace {

using arimaa::Board;
using arimaa::adjacent;
using arimaa::apply_pull;
using arimaa::apply_push;
using arimaa::apply_step;
using arimaa::color_of;
using arimaa::is_empty;
using arimaa::neighbors;
using arimaa::rank_of;
using arimaa::resolve_traps;
using arimaa::strength_of;
using arimaa::trap_squares;

const int LIMITS[6] = {1, 1, 2, 2, 2, 8};
const char *TYPES = "EMHDCR";

std::string key_of(const Board &b) { return std::string(b.begin(), b.end()); }

bool inventory_ok(const Board &b) {
    int cnt[128] = {0};
    for (int i = 0; i < 64; i++)
        if (!is_empty(b[i])) cnt[(int)b[i]]++;
    for (int t = 0; t < 6; t++) {
        if (cnt[(int)TYPES[t]] > LIMITS[t]) return false;
        if (cnt[(int)std::tolower(TYPES[t])] > LIMITS[t]) return false;
    }
    return true;
}

bool clean(const Board &b) {
    Board r = b;
    resolve_traps(r);
    return r == b;
}

bool decided(const Board &b) {
    int gr = 0, sr = 0;
    for (int i = 0; i < 64; i++) {
        if (b[i] == 'R') {
            gr++;
            if (rank_of(i) == 7) return true;
        }
        if (b[i] == 'r') {
            sr++;
            if (rank_of(i) == 0) return true;
        }
    }
    return gr == 0 || sr == 0;
}

struct Walker {
    Board P;
    int side;
    int base_count;
    std::unordered_set<std::string> seen;
    std::unordered_set<std::string> accept;
    std::deque<std::pair<Board, int> > todo;
    Board scratch;

    static int piece_count(const Board &b) {
        int n = 0;
        for (int i = 0; i < 64; i++)
            if (!is_empty(b[i])) n++;
        return n;
    }

    void offer(const Board &cand, int units) {
        if (piece_count(cand) > base_count + 1) return;
        if (!inventory_ok(cand)) return;
        if (!clean(cand)) return;
        std::string k = key_of(cand);
        k += (char)('0' + units);
        if (!seen.insert(k).second) return;
        todo.push_back(std::make_pair(cand, units));
        if (cand != P && !decided(cand)) accept.insert(key_of(cand));
    }

    int trap_next_to(int sq) {
        const int *T = trap_squares();
        for (int t = 0; t < 4; t++)
            if (adjacent(sq, T[t])) return T[t];
        return -1;
    }

    void mover_types(std::vector<char> &out) {
        out.clear();
        for (int k = 0; k < 6; k++)
            out.push_back(side == 0 ? TYPES[k] : (char)std::tolower(TYPES[k]));
    }

    void opp_types(std::vector<char> &out) {
        out.clear();
        for (int k = 0; k < 6; k++)
            out.push_back(side == 0 ? (char)std::tolower(TYPES[k]) : TYPES[k]);
    }

    void guard_variants(const Board &b, int departed, int color, std::vector<Board> &out) {
        out.push_back(b);
        int t = trap_next_to(departed);
        if (t < 0 || !is_empty(b[t])) return;
        std::vector<char> ts;
        if (color == side) mover_types(ts);
        else opp_types(ts);
        for (size_t k = 0; k < ts.size(); k++) {
            Board nb = b;
            nb[t] = ts[k];
            out.push_back(nb);
        }
    }

    void check_step(const Board &S, int units, const Board &S1, int i, int j) {
        std::vector<Board> vars;
        guard_variants(S1, i, side, vars);
        for (size_t x = 0; x < vars.size(); x++)
            if (apply_step(vars[x], side, i, j, scratch) && scratch == S)
                offer(vars[x], units + 1);
    }

    void un_steps(const Board &S, int units) {
        std::vector<char> mts;
        mover_types(mts);
        const int *T = trap_squares();
        for (int j = 0; j < 64; j++) {
            bool alive = !is_empty(S[j]) && color_of(S[j]) == side;
            bool dead_slot = false;
            for (int t = 0; t < 4; t++)
                if (T[t] == j && is_empty(S[j])) dead_slot = true;
            if (!alive && !dead_slot) continue;
            int nb[4];
            int n = neighbors(j, nb);
            for (int d = 0; d < n; d++) {
                int i = nb[d];
                if (!is_empty(S[i])) continue;
                if (alive) {
                    Board S1 = S;
                    S1[i] = S1[j];
                    S1[j] = '.';
                    check_step(S, units, S1, i, j);
                } else {
                    for (size_t k = 0; k < mts.size(); k++) {
                        Board S1 = S;
                        S1[i] = mts[k];
                        check_step(S, units, S1, i, j);
                    }
                }
            }
        }
    }

    void check_push(const Board &S, int units, const Board &S1, int aa, int vb, int vc) {
        std::vector<Board> v1;
        guard_variants(S1, vb, 1 - side, v1);
        for (size_t x = 0; x < v1.size(); x++) {
            std::vector<Board> v2;
            guard_variants(v1[x], aa, side, v2);
            for (size_t y = 0; y < v2.size(); y++)
                if (apply_push(v2[y], side, aa, vb, vc, scratch) && scratch == S)
                    offer(v2[y], units + 2);
        }
    }

    void un_pushes(const Board &S, int units) {
        std::vector<char> mts, ots;
        mover_types(mts);
        opp_types(ots);
        const int *T = trap_squares();
        for (int vb = 0; vb < 64; vb++) {
            bool actor_alive = !is_empty(S[vb]) && color_of(S[vb]) == side;
            bool actor_dead = false;
            for (int t = 0; t < 4; t++)
                if (T[t] == vb && is_empty(S[vb])) actor_dead = true;
            if (!actor_alive && !actor_dead) continue;
            std::vector<char> actors;
            if (actor_alive) actors.push_back(S[vb]);
            else actors = mts;
            int eb[4];
            int en = neighbors(vb, eb);
            for (int e = 0; e < en; e++) {
                int vc = eb[e];
                bool victim_alive = !is_empty(S[vc]) && color_of(S[vc]) != side;
                bool victim_dead = false;
                for (int t = 0; t < 4; t++)
                    if (T[t] == vc && is_empty(S[vc])) victim_dead = true;
                if (!victim_alive && !victim_dead) continue;
                std::vector<char> victims;
                if (victim_alive) victims.push_back(S[vc]);
                else victims = ots;
                int db[4];
                int dn = neighbors(vb, db);
                for (int d = 0; d < dn; d++) {
                    int aa = db[d];
                    if (aa == vc) continue;
                    if (!is_empty(S[aa])) continue;
                    for (size_t ai = 0; ai < actors.size(); ai++)
                        for (size_t vi = 0; vi < victims.size(); vi++) {
                            if (strength_of(actors[ai]) <= strength_of(victims[vi])) continue;
                            Board S1 = S;
                            if (actor_alive) S1[vb] = '.';
                            if (victim_alive) S1[vc] = '.';
                            S1[aa] = actors[ai];
                            S1[vb] = victims[vi];
                            check_push(S, units, S1, aa, vb, vc);
                        }
                }
            }
        }
    }

    void check_pull(const Board &S, int units, const Board &S1, int aa, int ad, int vb) {
        std::vector<Board> v1;
        guard_variants(S1, aa, side, v1);
        for (size_t x = 0; x < v1.size(); x++) {
            std::vector<Board> v2;
            guard_variants(v1[x], vb, 1 - side, v2);
            for (size_t y = 0; y < v2.size(); y++)
                if (apply_pull(v2[y], side, aa, ad, vb, scratch) && scratch == S)
                    offer(v2[y], units + 2);
        }
    }

    void un_pulls(const Board &S, int units) {
        std::vector<char> mts, ots;
        mover_types(mts);
        opp_types(ots);
        const int *T = trap_squares();
        for (int ad = 0; ad < 64; ad++) {
            bool actor_alive = !is_empty(S[ad]) && color_of(S[ad]) == side;
            bool actor_dead = false;
            for (int t = 0; t < 4; t++)
                if (T[t] == ad && is_empty(S[ad])) actor_dead = true;
            if (!actor_alive && !actor_dead) continue;
            std::vector<char> actors;
            if (actor_alive) actors.push_back(S[ad]);
            else actors = mts;
            int db[4];
            int dn = neighbors(ad, db);
            for (int d = 0; d < dn; d++) {
                int aa = db[d];
                bool victim_alive = !is_empty(S[aa]) && color_of(S[aa]) != side;
                bool victim_dead = false;
                for (int t = 0; t < 4; t++)
                    if (T[t] == aa && is_empty(S[aa])) victim_dead = true;
                if (!victim_alive && !victim_dead) continue;
                std::vector<char> victims;
                if (victim_alive) victims.push_back(S[aa]);
                else victims = ots;
                int eb[4];
                int en = neighbors(aa, eb);
                for (int e = 0; e < en; e++) {
                    int vb = eb[e];
                    if (vb == ad) continue;
                    if (!is_empty(S[vb])) continue;
                    for (size_t ai = 0; ai < actors.size(); ai++)
                        for (size_t vi = 0; vi < victims.size(); vi++) {
                            if (strength_of(actors[ai]) <= strength_of(victims[vi])) continue;
                            Board S1 = S;
                            if (actor_alive) S1[ad] = '.';
                            if (victim_alive) S1[aa] = '.';
                            S1[aa] = actors[ai];
                            S1[vb] = victims[vi];
                            check_pull(S, units, S1, aa, ad, vb);
                        }
                }
            }
        }
    }

    long long run(const Board &p, int s) {
        P = p;
        side = s;
        base_count = piece_count(p);
        seen.clear();
        accept.clear();
        todo.clear();
        std::string k0 = key_of(P);
        k0 += '0';
        todo.push_back(std::make_pair(P, 0));
        seen.insert(k0);
        while (!todo.empty()) {
            std::pair<Board, int> cur = todo.front();
            todo.pop_front();
            if (cur.second >= 4) continue;
            if (cur.second + 1 <= 4) un_steps(cur.first, cur.second);
            if (cur.second + 2 <= 4) {
                un_pushes(cur.first, cur.second);
                un_pulls(cur.first, cur.second);
            }
        }
        return (long long)accept.size();
    }
};

}  // namespace

long long predecessor_count(const State &s) {
    Walker w;
    return w.run(s.sq, s.stm);
}
EOF

cd /app
make
./run_samples.sh
