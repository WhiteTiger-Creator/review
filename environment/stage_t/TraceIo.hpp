#pragma once
#include <string>
#include <vector>
#include <nlohmann/json.hpp>

std::vector<nlohmann::json> load_trace_suite(const std::string& path);
int score_pair_local(int a, int b, int depth, int boost);
