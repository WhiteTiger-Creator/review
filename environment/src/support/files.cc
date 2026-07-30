#include "support/files.h"

#include <fstream>
#include <sstream>
#include <stdexcept>

namespace site {

std::string read_text(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        return "";
    }
    std::ostringstream buffer;
    buffer << input.rdbuf();
    return buffer.str();
}

void write_atomic(const std::filesystem::path& path, const std::string& text) {
    std::error_code exists_error;
    if (std::filesystem::is_regular_file(path, exists_error)) {
        if (read_text(path) == text) {
            return;
        }
    }
    const auto parent = path.parent_path();
    if (!parent.empty()) {
        std::filesystem::create_directories(parent);
    }
    const auto temporary = path.string() + ".new";
    {
        std::ofstream output(temporary, std::ios::binary | std::ios::trunc);
        if (!output) {
            throw std::runtime_error("cannot create local record");
        }
        output.write(text.data(), static_cast<std::streamsize>(text.size()));
        output.flush();
        if (!output) {
            throw std::runtime_error("cannot write local record");
        }
    }
    std::error_code rename_error;
    std::filesystem::rename(temporary, path, rename_error);
    if (rename_error) {
        std::filesystem::remove(temporary);
        throw std::runtime_error("cannot replace local record");
    }
}

bool has_nonempty(const std::filesystem::path& path) {
    std::error_code error;
    return std::filesystem::exists(path, error) &&
           std::filesystem::is_regular_file(path, error) &&
           std::filesystem::file_size(path, error) > 0;
}

}  // namespace site
