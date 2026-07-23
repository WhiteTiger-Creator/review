#include "config.hpp"
#include "util.hpp"
#include <set>
#include <stdexcept>

RelayConfig load_relay_config(const std::string& path) {
    auto values = read_key_values(path);
    const std::set<std::string> expected = {
        "site_key", "socket_path", "socket_mode", "socket_owner", "socket_group",
        "listen_backlog", "route_map", "limits_file", "audit_db", "catalog_generation"
    };
    for (const auto& [key, value] : values) {
        (void)value;
        if (!expected.count(key)) throw std::runtime_error("unknown relay key " + key);
    }
    for (const auto& key : expected) if (!values.count(key)) throw std::runtime_error("missing relay key " + key);
    auto limits = read_key_values(values.at("limits_file"));
    for (const auto& key : {"open_files_soft", "reserved_files", "max_connections", "request_body_limit"}) {
        if (!limits.count(key)) throw std::runtime_error(std::string("missing limit key ") + key);
    }
    RelayConfig cfg;
    cfg.site_key = values.at("site_key");
    cfg.socket_path = values.at("socket_path");
    cfg.socket_mode = values.at("socket_mode");
    cfg.socket_owner = values.at("socket_owner");
    cfg.socket_group = values.at("socket_group");
    cfg.listen_backlog = std::stoi(values.at("listen_backlog"));
    cfg.route_map = values.at("route_map");
    cfg.limits_file = values.at("limits_file");
    cfg.audit_db = values.at("audit_db");
    cfg.catalog_generation = std::stoi(values.at("catalog_generation"));
    cfg.request_body_limit = std::stoi(limits.at("request_body_limit"));
    return cfg;
}
