#pragma once

#include <string>
#include <vector>

namespace termatrix {

std::string shell_quote(const std::string &value);
std::string capture_command(const std::vector<std::string> &args);
void run_checked(const std::vector<std::string> &args);

}  // namespace termatrix
