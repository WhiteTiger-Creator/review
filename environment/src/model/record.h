#pragma once

#include <map>
#include <string>

namespace site {

struct Record {
    std::map<std::string, std::string> values;

    std::string get(const std::string& key, const std::string& fallback = "") const;
    long number(const std::string& key, long fallback = 0) const;
    void set(const std::string& key, const std::string& value);
};

}  // namespace site
