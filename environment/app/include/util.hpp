#pragma once
#include <map>
#include <string>
#include <vector>

std::string trim(const std::string& value);
std::vector<std::string> split(const std::string& value, char delimiter);
std::map<std::string, std::string> read_key_values(const std::string& path);
std::string json_escape(const std::string& value);
