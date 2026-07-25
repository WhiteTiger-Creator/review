#pragma once
#include <array>
#include "board.hpp"

namespace arimaa {

typedef std::array<char, 64> Board;

inline const int *trap_squares() {
    static const int t[4] = {18, 21, 42, 45};
    return t;
}

inline bool is_empty(char c) { return c == '.'; }
inline bool is_gold(char c) { return c >= 'A' && c <= 'Z'; }
inline int color_of(char c) { return is_gold(c) ? 0 : 1; }

inline int strength_of(char c) {
    switch (c) {
        case 'E': case 'e': return 6;
        case 'M': case 'm': return 5;
        case 'H': case 'h': return 4;
        case 'D': case 'd': return 3;
        case 'C': case 'c': return 2;
        case 'R': case 'r': return 1;
    }
    return 0;
}

inline int rank_of(int i) { return i >> 3; }
inline int file_of(int i) { return i & 7; }

inline bool adjacent(int a, int b) {
    int dr = rank_of(a) - rank_of(b);
    int df = file_of(a) - file_of(b);
    if (dr < 0) dr = -dr;
    if (df < 0) df = -df;
    return dr + df == 1;
}

inline int neighbors(int i, int *out) {
    int n = 0;
    if (rank_of(i) < 7) out[n++] = i + 8;
    if (rank_of(i) > 0) out[n++] = i - 8;
    if (file_of(i) < 7) out[n++] = i + 1;
    if (file_of(i) > 0) out[n++] = i - 1;
    return n;
}

inline void resolve_traps(Board &b) {
    const int *T = trap_squares();
    for (int t = 0; t < 4; t++) {
        int sq = T[t];
        if (is_empty(b[sq])) continue;
        int col = color_of(b[sq]);
        int nb[4];
        int n = neighbors(sq, nb);
        bool guarded = false;
        for (int k = 0; k < n; k++)
            if (!is_empty(b[nb[k]]) && color_of(b[nb[k]]) == col) {
                guarded = true;
                break;
            }
        if (!guarded) b[sq] = '.';
    }
}

inline bool is_frozen(const Board &b, int i) {
    char p = b[i];
    if (is_empty(p)) return false;
    int col = color_of(p);
    int nb[4];
    int n = neighbors(i, nb);
    bool stronger = false, friendly = false;
    for (int k = 0; k < n; k++) {
        char q = b[nb[k]];
        if (is_empty(q)) continue;
        if (color_of(q) == col) friendly = true;
        else if (strength_of(q) > strength_of(p)) stronger = true;
    }
    return stronger && !friendly;
}

inline bool rabbit_dir_ok(char p, int from, int to) {
    if (p == 'R') return to != from - 8;
    if (p == 'r') return to != from + 8;
    return true;
}

inline bool apply_step(const Board &in, int mover, int from, int to, Board &out) {
    char p = in[from];
    if (is_empty(p) || color_of(p) != mover) return false;
    if (!adjacent(from, to)) return false;
    if (!is_empty(in[to])) return false;
    if (!rabbit_dir_ok(p, from, to)) return false;
    if (is_frozen(in, from)) return false;
    out = in;
    out[to] = p;
    out[from] = '.';
    resolve_traps(out);
    return true;
}

inline bool apply_push(const Board &in, int mover, int from, int victim, int dest,
                       Board &out) {
    char a = in[from], v = in[victim];
    if (is_empty(a) || color_of(a) != mover) return false;
    if (is_empty(v) || color_of(v) == mover) return false;
    if (strength_of(a) <= strength_of(v)) return false;
    if (!adjacent(from, victim) || !adjacent(victim, dest)) return false;
    if (!is_empty(in[dest])) return false;
    if (is_frozen(in, from)) return false;
    out = in;
    out[dest] = v;
    out[victim] = '.';
    resolve_traps(out);
    out[victim] = out[from];
    out[from] = '.';
    resolve_traps(out);
    return true;
}

inline bool apply_pull(const Board &in, int mover, int from, int dest, int victim,
                       Board &out) {
    char a = in[from], v = in[victim];
    if (is_empty(a) || color_of(a) != mover) return false;
    if (is_empty(v) || color_of(v) == mover) return false;
    if (strength_of(a) <= strength_of(v)) return false;
    if (!adjacent(from, dest) || !adjacent(from, victim)) return false;
    if (dest == victim) return false;
    if (!is_empty(in[dest])) return false;
    if (is_frozen(in, from)) return false;
    out = in;
    out[dest] = a;
    out[from] = '.';
    resolve_traps(out);
    out[from] = out[victim];
    out[victim] = '.';
    resolve_traps(out);
    return true;
}

}  // namespace arimaa
