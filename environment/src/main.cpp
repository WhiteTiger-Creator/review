#include <cstdio>
#include <iostream>
#include <string>
#include "board.hpp"
#include "parse.hpp"
#include "retro.hpp"

int main() {
    std::string placement, side;
    while (std::cin >> placement >> side) {
        State s;
        if (!parse_position(placement, side, s)) return 1;
        std::printf("%lld\n", predecessor_count(s));
    }
    return 0;
}
