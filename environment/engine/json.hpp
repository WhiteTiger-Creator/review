#pragma once

#include <ostream>
#include <string>

namespace termatrix {

std::string json_escape(const std::string &value);
void json_string(std::ostream &out, const std::string &value);

}  // namespace termatrix
