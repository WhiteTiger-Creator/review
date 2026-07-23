#include "descriptor.hpp"

#include <cstdlib>
#include <fstream>
#include <map>
#include <sstream>
#include <stdexcept>

namespace fs = std::filesystem;

namespace termatrix {

std::vector<std::string> parse_target_list() {
    const char *raw = std::getenv("TERMATRIX_TARGETS");
    std::string text = raw ? raw : "glibc-x86_64 musl-x86_64";
    std::istringstream in(text);
    std::vector<std::string> targets;
    for (std::string item; in >> item;) {
        targets.push_back(item);
    }
    if (targets.empty()) {
        throw std::runtime_error("TERMATRIX_TARGETS did not name any targets");
    }
    return targets;
}

static std::map<std::string, std::string> read_env_file(const fs::path &path) {
    std::ifstream in(path);
    if (!in) {
        throw std::runtime_error("unknown matrix target: " + path.stem().string());
    }

    std::map<std::string, std::string> fields;
    for (std::string line; std::getline(in, line);) {
        if (line.empty() || line[0] == '#') {
            continue;
        }
        auto eq = line.find('=');
        if (eq == std::string::npos) {
            continue;
        }
        fields[line.substr(0, eq)] = line.substr(eq + 1);
    }
    return fields;
}

static std::string require_field(
    const std::map<std::string, std::string> &fields,
    const std::string &name,
    const fs::path &path) {
    auto it = fields.find(name);
    if (it == fields.end() || it->second.empty()) {
        throw std::runtime_error("missing " + name + " in " + path.string());
    }
    return it->second;
}

Descriptor load_descriptor(const fs::path &root, const std::string &target) {
    fs::path path = root / "config/matrix" / (target + ".env");
    auto fields = read_env_file(path);

    Descriptor out;
    out.requested_name = target;
    out.target_name = require_field(fields, "target_name", path);
    out.abi_family = require_field(fields, "abi_family", path);
    out.abi_define = require_field(fields, "abi_define", path);
    out.target_define = require_field(fields, "target_define", path);
    out.toolchain_file = require_field(fields, "toolchain_file", path);
    out.compiler_profile = require_field(fields, "compiler_profile", path);
    out.descriptor_path = path;

    if (out.target_name != target) {
        throw std::runtime_error("descriptor target mismatch for " + target);
    }
    if (!fs::is_regular_file(root / out.toolchain_file)) {
        throw std::runtime_error("missing toolchain for " + target);
    }
    return out;
}

}  // namespace termatrix
