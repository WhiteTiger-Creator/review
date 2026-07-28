#include "support/codec.h"

#include <sstream>

namespace site {

Record decode_record(const std::string& text) {
    Record result;
    std::istringstream input(text);
    std::string line;
    while (std::getline(input, line)) {
        const auto pos = line.find('=');
        if (pos != std::string::npos && pos > 0) {
            result.set(line.substr(0, pos), line.substr(pos + 1));
        }
    }
    return result;
}

std::string encode_record(const Record& record) {
    std::ostringstream output;
    for (const auto& [key, value] : record.values) {
        output << key << '=' << value << '\n';
    }
    return output.str();
}

}  // namespace site
