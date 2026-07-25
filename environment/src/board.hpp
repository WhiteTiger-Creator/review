#pragma once
#include <array>

struct State {
    std::array<char, 64> sq;
    int stm;
};

inline int sq_rank(int i) { return i >> 3; }
inline int sq_file(int i) { return i & 7; }
inline int sq_index(int rank, int file) { return rank * 8 + file; }
