#pragma once

#include "fs/walker.h"

#include <filesystem>
#include <optional>
#include <string>

namespace site {

struct Candidate {
    long generation;
    std::string count;
    std::string fingerprint;
    std::filesystem::path source;
};

void stage_candidate(const std::filesystem::path& root, const Scan& scan);
std::optional<Candidate> select_candidate(const std::filesystem::path& root, const Scan& scan);
void commit_candidate(const std::filesystem::path& root, const Candidate& candidate);
bool account_matches(const std::filesystem::path& root, const Scan& scan);

}  // namespace site
