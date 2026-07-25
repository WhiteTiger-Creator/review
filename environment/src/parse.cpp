#include "parse.hpp"
#include <cstring>
#include <vector>

bool parse_position(const std::string &placement, const std::string &side, State &out) {
    out.sq.fill('.');
    std::vector<std::string> rows;
    std::string cur;
    for (size_t i = 0; i <= placement.size(); i++) {
        if (i == placement.size() || placement[i] == '/') {
            rows.push_back(cur);
            cur.clear();
        } else {
            cur.push_back(placement[i]);
        }
    }
    if (rows.size() != 8) return false;
    for (int r = 0; r < 8; r++) {
        int rank = 7 - r;
        int file = 0;
        const std::string &row = rows[r];
        for (size_t i = 0; i < row.size(); i++) {
            char c = row[i];
            if (c >= '1' && c <= '8') {
                file += c - '0';
            } else if (std::strchr("EMHDCRemhdcr", c)) {
                if (file >= 8) return false;
                out.sq[sq_index(rank, file)] = c;
                file++;
            } else {
                return false;
            }
            if (file > 8) return false;
        }
        if (file != 8) return false;
    }
    if (side == "g") out.stm = 0;
    else if (side == "s") out.stm = 1;
    else return false;
    return true;
}
