#pragma once
#include <string>

struct RelayConfig {
    std::string site_key;
    std::string socket_path;
    std::string socket_mode;
    std::string socket_owner;
    std::string socket_group;
    int listen_backlog{};
    std::string route_map;
    std::string limits_file;
    std::string audit_db;
    int catalog_generation{};
    int request_body_limit{};
};

RelayConfig load_relay_config(const std::string& path);
