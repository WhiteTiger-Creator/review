#include "config.hpp"
#include "http.hpp"
#include "route.hpp"
#include "util.hpp"
#include <cerrno>
#include <csignal>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

namespace {
volatile std::sig_atomic_t running = 1;
void stop(int) { running = 0; }

std::string response_for(const RelayConfig& cfg, const std::vector<RouteEntry>& routes, const std::string& bytes) {
    try {
        const auto request = parse_http_request(bytes);
        if (request.body.size() > static_cast<std::size_t>(cfg.request_body_limit)) {
            return "HTTP/1.1 413 Payload Too Large\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
        }
        const RouteEntry* route = find_route(routes, request.method, request.path);
        if (!route) return "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
        std::string body = "{\"site\":\"" + json_escape(cfg.site_key) + "\",\"method\":\"" + json_escape(request.method)
            + "\",\"path\":\"" + json_escape(request.path) + "\",\"upstream\":\"" + json_escape(route->upstream)
            + "\",\"auth_mode\":\"" + json_escape(route->auth_mode) + "\",\"timeout_ms\":" + std::to_string(route->timeout_ms)
            + ",\"source_route_id\":\"" + json_escape(route->source_route_id) + "\"}";
        return "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: " + std::to_string(body.size())
            + "\r\nConnection: close\r\n\r\n" + body;
    } catch (const std::exception&) {
        return "HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
    }
}
}

int main(int argc, char** argv) {
    try {
        std::string config_path = "/app/etc/harbor-relay/relay.conf";
        bool check_only = false;
        if (const char* env = std::getenv("HARBOR_RELAY_CONFIG")) config_path = env;
        if (argc == 3 && std::string(argv[1]) == "--config") config_path = argv[2];
        else if (argc == 3 && std::string(argv[1]) == "--check-config") { config_path = argv[2]; check_only = true; }
        else if (argc != 1) throw std::runtime_error("usage: harbor-relay [--config FILE | --check-config FILE]");
        const auto cfg = load_relay_config(config_path);
        const auto routes = load_routes(cfg.route_map);
        if (check_only) return 0;
        std::filesystem::create_directories(std::filesystem::path(cfg.socket_path).parent_path());
        ::unlink(cfg.socket_path.c_str());
        int fd = ::socket(AF_UNIX, SOCK_STREAM, 0);
        if (fd < 0) throw std::runtime_error(std::strerror(errno));
        sockaddr_un addr{};
        addr.sun_family = AF_UNIX;
        if (cfg.socket_path.size() >= sizeof(addr.sun_path)) throw std::runtime_error("socket path too long");
        std::strncpy(addr.sun_path, cfg.socket_path.c_str(), sizeof(addr.sun_path) - 1);
        if (::bind(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) throw std::runtime_error(std::strerror(errno));
        mode_t mode = static_cast<mode_t>(std::stoul(cfg.socket_mode, nullptr, 8));
        ::chmod(cfg.socket_path.c_str(), mode);
        if (::listen(fd, cfg.listen_backlog) != 0) throw std::runtime_error(std::strerror(errno));
        std::signal(SIGTERM, stop);
        std::signal(SIGINT, stop);
        while (running) {
            int client = ::accept(fd, nullptr, nullptr);
            if (client < 0) {
                if (errno == EINTR) continue;
                throw std::runtime_error(std::strerror(errno));
            }
            std::string bytes;
            char buffer[8192];
            while (true) {
                ssize_t n = ::recv(client, buffer, sizeof(buffer), 0);
                if (n <= 0) break;
                bytes.append(buffer, static_cast<std::size_t>(n));
                auto pos = bytes.find("\r\n\r\n");
                if (pos != std::string::npos) {
                    std::size_t header_end = pos + 4;
                    std::size_t content_length = 0;
                    auto marker = bytes.find("Content-Length:");
                    if (marker != std::string::npos) content_length = std::stoull(bytes.substr(marker + 15));
                    if (bytes.size() >= header_end + content_length) break;
                }
            }
            const std::string response = response_for(cfg, routes, bytes);
            ::send(client, response.data(), response.size(), 0);
            ::close(client);
        }
        ::close(fd);
        ::unlink(cfg.socket_path.c_str());
        return 0;
    } catch (const std::exception& ex) {
        std::cerr << "harbor-relay: " << ex.what() << "\n";
        return 78;
    }
}
