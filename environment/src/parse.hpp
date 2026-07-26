#pragma once
#include <string>
#include "board.hpp"

bool parse_position(const std::string &placement, const std::string &side, State &out);
