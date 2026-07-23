#include "model/record.h"

#include <charconv>

namespace site {

std::string Record::get(const std::string& key, const std::string& fallback) const {
    const auto it = values.find(key);
    return it == values.end() ? fallback : it->second;
}

long Record::number(const std::string& key, long fallback) const {
    const auto text = get(key);
    long value = fallback;
    const auto result = std::from_chars(text.data(), text.data() + text.size(), value);
    return result.ec == std::errc{} ? value : fallback;
}

void Record::set(const std::string& key, const std::string& value) {
    values[key] = value;
}

}  // namespace site
