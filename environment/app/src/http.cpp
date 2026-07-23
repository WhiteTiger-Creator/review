#include "http.hpp"
#include "util.hpp"
#include <algorithm>
#include <cctype>
#include <sstream>
#include <stdexcept>

static std::string lower(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c){ return static_cast<char>(std::tolower(c)); });
    return value;
}

HttpRequest parse_http_request(const std::string& bytes) {
    std::size_t split_pos = bytes.find("\r\n\r\n");
    std::size_t separator = 4;
    if (split_pos == std::string::npos) {
        split_pos = bytes.find("\n\n");
        separator = 2;
    }
    if (split_pos == std::string::npos) throw std::runtime_error("missing HTTP header separator");
    std::string head = bytes.substr(0, split_pos);
    std::string body = bytes.substr(split_pos + separator);
    std::istringstream lines(head);
    std::string line;
    if (!std::getline(lines, line)) throw std::runtime_error("missing request line");
    if (!line.empty() && line.back() == '\r') line.pop_back();
    std::istringstream first(line);
    HttpRequest request;
    std::string version;
    if (!(first >> request.method >> request.target >> version)) throw std::runtime_error("invalid request line");
    request.path = request.target.substr(0, request.target.find('?'));
    while (std::getline(lines, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        const auto pos = line.find(':');
        if (pos == std::string::npos) throw std::runtime_error("invalid header");
        request.headers[lower(trim(line.substr(0, pos)))] = trim(line.substr(pos + 1));
    }
    request.body = body;
    auto it = request.headers.find("content-length");
    if (it != request.headers.end() && static_cast<std::size_t>(std::stoull(it->second)) != body.size()) {
        throw std::runtime_error("content length mismatch");
    }
    return request;
}
