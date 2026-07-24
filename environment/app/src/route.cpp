#include "route.hpp"
#include "util.hpp"
#include <fstream>
#include <stdexcept>

std::vector<RouteEntry> load_routes(const std::string& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("cannot open route map " + path);
    std::string line;
    if (!std::getline(input, line) || line != "method\texternal_path\tupstream\tauth_mode\ttimeout_ms\tsource_route_id") {
        throw std::runtime_error("invalid route map header");
    }
    std::vector<RouteEntry> routes;
    while (std::getline(input, line)) {
        if (line.empty()) continue;
        const auto fields = split(line, '\t');
        if (fields.size() != 6) throw std::runtime_error("invalid route row");
        routes.push_back({fields[0], fields[1], fields[2], fields[3], std::stoi(fields[4]), fields[5]});
    }
    return routes;
}

const RouteEntry* find_route(const std::vector<RouteEntry>& routes, const std::string& method, const std::string& path) {
    for (const auto& route : routes) {
        if (route.method == method && route.external_path == path) return &route;
    }
    return nullptr;
}
