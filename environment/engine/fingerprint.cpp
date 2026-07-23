#include "fingerprint.hpp"

#include "process.hpp"

#include <algorithm>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unistd.h>

namespace fs = std::filesystem;

namespace termatrix {

static std::string trim_first_field(const std::string &value) {
    auto end = value.find_first_of(" \t\r\n");
    if (end == std::string::npos) {
        return value;
    }
    return value.substr(0, end);
}

std::string sha256_file(const fs::path &path) {
    if (!fs::is_regular_file(path)) {
        throw std::runtime_error("cannot hash missing file: " + path.string());
    }
    return trim_first_field(capture_command({"sha256sum", path.string()}));
}

std::string sha256_text(const std::string &text) {
    fs::path tmp = fs::temp_directory_path() /
        ("termatrix-hash-" + std::to_string(static_cast<long long>(getpid())) + ".txt");
    {
        std::ofstream out(tmp);
        out << text;
    }
    std::string digest = sha256_file(tmp);
    fs::remove(tmp);
    return digest;
}

static std::vector<fs::path> sorted_files(const fs::path &root) {
    std::vector<fs::path> files;
    if (!fs::exists(root)) {
        return files;
    }
    for (const auto &entry : fs::recursive_directory_iterator(root)) {
        if (entry.is_regular_file()) {
            files.push_back(entry.path());
        }
    }
    std::sort(files.begin(), files.end());
    return files;
}

std::string tree_digest(const fs::path &root) {
    std::ostringstream payload;
    for (const auto &file : sorted_files(root)) {
        payload << fs::relative(file, root).generic_string()
                << "\t" << fs::file_size(file)
                << "\t" << sha256_file(file) << "\n";
    }
    return sha256_text(payload.str());
}

std::string build_logic_digest(const fs::path &root) {
    std::vector<fs::path> files = {
        root / "CMakeLists.txt",
        root / "scripts/build_matrix.sh",
    };
    auto engine_files = sorted_files(root / "engine");
    files.insert(files.end(), engine_files.begin(), engine_files.end());
    std::sort(files.begin(), files.end());

    std::ostringstream payload;
    for (const auto &file : files) {
        if (fs::is_regular_file(file)) {
            payload << fs::relative(file, root).generic_string()
                    << "\t" << fs::file_size(file)
                    << "\t" << sha256_file(file) << "\n";
        }
    }
    return sha256_text(payload.str());
}

std::string cache_key_for_unit(
    const fs::path &root,
    const Descriptor &descriptor,
    const UnitDef &unit) {
    std::ostringstream payload;
    payload << "unit_name=" << unit.name << "\n";
    payload << "unit_source_sha256=" << tree_digest(root / "src") << "\n";
    payload << "public_header_sha256=" << tree_digest(root / "include") << "\n";
    payload << "target=" << descriptor.target_name << "\n";
    payload << "abi_family=" << descriptor.abi_family << "\n";
    payload << "toolchain_sha256=" << sha256_file(root / descriptor.toolchain_file) << "\n";
    payload << "compiler_profile=" << descriptor.compiler_profile << "\n";
    return sha256_text(payload.str()).substr(0, 32);
}

}  // namespace termatrix
