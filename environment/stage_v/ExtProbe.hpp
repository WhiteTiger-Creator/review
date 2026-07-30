#pragma once
#include <nlohmann/json.hpp>
nlohmann::json run_ext_probe(const nlohmann::json& dossier,
                             const nlohmann::json& closed);
