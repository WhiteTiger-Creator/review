#pragma once
#include <string>
#include <vector>

struct RouteEntry {
    std::string method;
    std::string external_path;
    std::string upstream;
    std::string auth_mode;
    int timeout_ms{};
    std::string source_route_id;
};

std::vector<RouteEntry> load_routes(const std::string& path);
const RouteEntry* find_route(const std::vector<RouteEntry>& routes, const std::string& method, const std::string& path);
