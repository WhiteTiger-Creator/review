#pragma once
#include <map>
#include <string>

struct HttpRequest {
    std::string method;
    std::string target;
    std::string path;
    std::map<std::string, std::string> headers;
    std::string body;
};

HttpRequest parse_http_request(const std::string& bytes);
