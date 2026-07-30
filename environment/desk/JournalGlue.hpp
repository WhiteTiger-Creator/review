#pragma once
#include <nlohmann/json.hpp>
#include <string>
#include <vector>

// Desk-facing journal orchestration helper.
nlohmann::json assemble_emit_bundle(const std::vector<nlohmann::json>& built_rows,
                                    const std::string& journal_root,
                                    const std::string& stamp_path);
