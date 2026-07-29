#include "util.hpp"
#include <cctype>
#include <fstream>
#include <sstream>
#include <stdexcept>

std::string trim(const std::string& value) {
    std::size_t first = 0;
    while (first < value.size() && std::isspace(static_cast<unsigned char>(value[first]))) ++first;
    std::size_t last = value.size();
    while (last > first && std::isspace(static_cast<unsigned char>(value[last - 1]))) --last;
    return value.substr(first, last - first);
}

std::vector<std::string> split(const std::string& value, char delimiter) {
    std::vector<std::string> out;
    std::string item;
    std::istringstream input(value);
    while (std::getline(input, item, delimiter)) out.push_back(item);
    if (!value.empty() && value.back() == delimiter) out.emplace_back();
    return out;
}

std::map<std::string, std::string> read_key_values(const std::string& path) {
    std::ifstream input(path);
    if (!input) throw std::runtime_error("cannot open " + path);
    std::map<std::string, std::string> values;
    std::string line;
    while (std::getline(input, line)) {
        line = trim(line);
        if (line.empty() || line[0] == '#') continue;
        const auto pos = line.find('=');
        if (pos == std::string::npos) throw std::runtime_error("invalid key/value line in " + path);
        const std::string key = trim(line.substr(0, pos));
        const std::string val = trim(line.substr(pos + 1));
        if (!values.emplace(key, val).second) throw std::runtime_error("duplicate key " + key);
    }
    return values;
}

std::string json_escape(const std::string& value) {
    std::ostringstream out;
    for (unsigned char c : value) {
        switch (c) {
            case '\\': out << "\\\\"; break;
            case '"': out << "\\\""; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default:
                if (c < 0x20) out << "?"; else out << static_cast<char>(c);
        }
    }
    return out.str();
}
