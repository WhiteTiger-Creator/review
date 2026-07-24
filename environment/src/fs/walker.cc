#include "fs/walker.h"

#include "support/files.h"

#include <algorithm>
#include <iomanip>
#include <sstream>

namespace site {
namespace {

void absorb(std::uint64_t& value, const std::string& text) {
    for (const unsigned char byte : text) {
        value ^= byte;
        value *= 1099511628211ULL;
    }
}

}  // namespace

Scan observe_tree(const std::filesystem::path& root) {
    Scan scan{{}, 1469598103934665603ULL};
    const auto payload = root / "payload";
    std::error_code error;
    if (!std::filesystem::is_directory(payload, error)) {
        return scan;
    }
    for (const auto& entry : std::filesystem::recursive_directory_iterator(payload)) {
        if (!entry.is_regular_file()) {
            continue;
        }
        scan.paths.push_back(std::filesystem::relative(entry.path(), payload).generic_string());
    }
    std::sort(scan.paths.begin(), scan.paths.end());
    for (const auto& path : scan.paths) {
        absorb(scan.fingerprint, path);
    }
    return scan;
}

std::string render_scan(const Scan& scan) {
    std::ostringstream output;
    output << "count=" << scan.paths.size() << '\n';
    output << "fingerprint=" << std::hex << std::setw(16) << std::setfill('0')
           << scan.fingerprint << '\n';
    for (const auto& path : scan.paths) {
        output << "path=" << path << '\n';
    }
    return output.str();
}

}  // namespace site
