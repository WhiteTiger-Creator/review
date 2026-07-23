#include "report.hpp"

#include "fingerprint.hpp"
#include "json.hpp"

#include <filesystem>
#include <fstream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unistd.h>

namespace fs = std::filesystem;

namespace termatrix {

std::map<std::string, std::string> read_meta_file(const fs::path &path) {
    std::ifstream in(path);
    if (!in) {
        throw std::runtime_error("missing object metadata: " + path.string());
    }
    std::map<std::string, std::string> fields;
    for (std::string line; std::getline(in, line);) {
        auto eq = line.find('=');
        if (eq != std::string::npos) {
            fields[line.substr(0, eq)] = line.substr(eq + 1);
        }
    }
    return fields;
}

static std::string field_or_empty(
    const std::map<std::string, std::string> &fields,
    const std::string &name) {
    auto it = fields.find(name);
    return it == fields.end() ? "" : it->second;
}

void write_pkg_config(const fs::path &stage, const Descriptor &descriptor) {
    fs::path pc_dir = stage / "lib/pkgconfig";
    fs::create_directories(pc_dir);
    fs::path pc = pc_dir / "termatrix.pc";
    std::ofstream out(pc);
    out << "prefix=${pcfiledir}/../..\n";
    out << "exec_prefix=${prefix}\n";
    out << "libdir=${prefix}/lib\n";
    out << "includedir=${prefix}/include\n\n";
    out << "Name: termatrix-" << descriptor.target_name << "\n";
    out << "Description: Termatrix ABI matrix artifact for " << descriptor.target_name << "\n";
    out << "Version: 2.4.0\n";
    out << "Cflags: -I${includedir} -DTERMATRIX_ABI_GLIBC=1 -DTERMATRIX_TARGET_GLIBC_X86_64=1\n";
    out << "Libs: -L${libdir} -ltermatrix\n";
}

void write_identity_json(const fs::path &stage, const Descriptor &descriptor) {
    std::ofstream out(stage / "abi_identity.json");
    out << "{\n";
    out << "  \"schema_version\": " << kSchemaVersion << ",\n";
    out << "  \"target\": ";
    json_string(out, descriptor.target_name);
    out << ",\n  \"abi_family\": ";
    json_string(out, descriptor.abi_family);
    out << ",\n  \"library\": \"lib/libtermatrix.a\",\n";
    out << "  \"header\": \"include/termatrix/matrix.h\",\n";
    out << "  \"pkg_config\": \"lib/pkgconfig/termatrix.pc\",\n";
    out << "  \"object_units\": [\"identity\", \"mix\"]\n";
    out << "}\n";
}

static const UnitPreState *find_pre_state(
    const std::vector<UnitPreState> &states,
    const std::string &unit) {
    for (const auto &state : states) {
        if (state.unit == unit) {
            return &state;
        }
    }
    return nullptr;
}

void write_cache_report(
    const fs::path &root,
    const fs::path &stage,
    const fs::path &cache_root,
    const Descriptor &descriptor,
    const std::vector<UnitPreState> &pre_states) {
    fs::path lib = stage / "lib/libtermatrix.a";
    fs::path header = stage / "include/termatrix/matrix.h";
    fs::path pc = stage / "lib/pkgconfig/termatrix.pc";
    fs::path report_tmp = stage / ("cache_provenance.json.tmp." + std::to_string(static_cast<long long>(getpid())));
    fs::path report = stage / "cache_provenance.json";

    std::ifstream pc_in(pc);
    std::string pc_line;
    std::string cflags;
    std::string libs;
    while (std::getline(pc_in, pc_line)) {
        if (pc_line.rfind("Cflags: ", 0) == 0) {
            cflags = pc_line.substr(8);
        }
        if (pc_line.rfind("Libs: ", 0) == 0) {
            libs = pc_line.substr(6);
        }
    }

    std::ofstream out(report_tmp);
    out << "{\n";
    out << "  \"schema_version\": " << kSchemaVersion << ",\n";
    out << "  \"generator\": \"" << kGenerator << "\",\n";
    out << "  \"requested\": {\n";
    out << "    \"target\": "; json_string(out, descriptor.target_name); out << ",\n";
    out << "    \"abi_family\": "; json_string(out, descriptor.abi_family); out << ",\n";
    out << "    \"toolchain_file\": "; json_string(out, descriptor.toolchain_file); out << ",\n";
    out << "    \"descriptor_file\": "; json_string(out, fs::relative(descriptor.descriptor_path, root).generic_string()); out << ",\n";
    out << "    \"compiler_profile\": "; json_string(out, descriptor.compiler_profile); out << "\n";
    out << "  },\n";
    out << "  \"artifact\": {\n";
    out << "    \"library\": \"lib/libtermatrix.a\",\n";
    out << "    \"library_sha256\": "; json_string(out, sha256_file(lib)); out << ",\n";
    out << "    \"header_sha256\": "; json_string(out, sha256_file(header)); out << ",\n";
    out << "    \"object_units\": [\"identity\", \"mix\"]\n";
    out << "  },\n";
    out << "  \"cache\": {\n";
    out << "    \"root\": "; json_string(out, cache_root.generic_string()); out << ",\n";
    out << "    \"key_fields\": [";
    auto fields = cache_key_fields();
    for (std::size_t i = 0; i < fields.size(); ++i) {
        if (i != 0) out << ", ";
        json_string(out, fields[i]);
    }
    out << "],\n";
    out << "    \"units\": [\n";
    auto units = object_units();
    for (std::size_t i = 0; i < units.size(); ++i) {
        const auto &unit = units[i];
        auto meta = read_meta_file(stage / "share/termatrix" / (unit.name + ".meta"));
        std::string expected_key = cache_key_for_unit(root, descriptor, unit);
        fs::path cache_obj = cache_root / (unit.name + "-" + expected_key) / (unit.name + ".o");
        const UnitPreState *pre = find_pre_state(pre_states, unit.name);
        bool valid = field_or_empty(meta, "target") == descriptor.target_name &&
                     field_or_empty(meta, "abi_family") == descriptor.abi_family &&
                     field_or_empty(meta, "unit") == unit.name &&
                     field_or_empty(meta, "cache_key") == expected_key;
        bool hit = valid && pre && pre->hit;
        if (i != 0) out << ",\n";
        out << "      {\n";
        out << "        \"unit\": "; json_string(out, unit.name); out << ",\n";
        out << "        \"key\": "; json_string(out, expected_key); out << ",\n";
        out << "        \"cache_path\": "; json_string(out, (unit.name + "-" + expected_key + "/" + unit.name + ".o")); out << ",\n";
        out << "        \"hit\": " << (hit ? "true" : "false") << ",\n";
        out << "        \"reason\": "; json_string(out, pre ? pre->reason : "not-inspected"); out << ",\n";
        out << "        \"valid_for_request\": " << (valid ? "true" : "false") << ",\n";
        out << "        \"object_sha256\": "; json_string(out, field_or_empty(meta, "object_sha256")); out << ",\n";
        out << "        \"actual_object_sha256\": "; json_string(out, fs::is_regular_file(cache_obj) ? sha256_file(cache_obj) : ""); out << ",\n";
        out << "        \"object_target\": "; json_string(out, field_or_empty(meta, "target")); out << ",\n";
        out << "        \"object_abi_family\": "; json_string(out, field_or_empty(meta, "abi_family")); out << ",\n";
        out << "        \"identity\": "; json_string(out, field_or_empty(meta, "identity")); out << ",\n";
        out << "        \"unit_source_sha256\": "; json_string(out, field_or_empty(meta, "unit_source_sha256")); out << ",\n";
        out << "        \"public_header_sha256\": "; json_string(out, field_or_empty(meta, "public_header_sha256")); out << ",\n";
        out << "        \"descriptor_sha256\": "; json_string(out, field_or_empty(meta, "descriptor_sha256")); out << ",\n";
        out << "        \"toolchain_sha256\": "; json_string(out, field_or_empty(meta, "toolchain_sha256")); out << ",\n";
        out << "        \"build_logic_sha256\": "; json_string(out, field_or_empty(meta, "build_logic_sha256")); out << "\n";
        out << "      }";
    }
    out << "\n    ]\n";
    out << "  },\n";
    out << "  \"pkg_config\": {\n";
    out << "    \"file\": \"lib/pkgconfig/termatrix.pc\",\n";
    out << "    \"cflags\": "; json_string(out, cflags); out << ",\n";
    out << "    \"libs\": "; json_string(out, libs); out << "\n";
    out << "  }\n";
    out << "}\n";
    out.close();
    fs::rename(report_tmp, report);
}

void write_top_report(const fs::path &out_root, const std::vector<std::string> &targets) {
    fs::create_directories(out_root);
    fs::path report_tmp = out_root / ("build-cache-provenance.json.tmp." + std::to_string(static_cast<long long>(getpid())));
    fs::path report = out_root / "build-cache-provenance.json";
    std::ofstream out(report_tmp);
    out << "{\n";
    out << "  \"schema_version\": " << kSchemaVersion << ",\n";
    out << "  \"generator\": \"" << kGenerator << "\",\n";
    out << "  \"transaction\": {\n";
    out << "    \"status\": \"success\",\n";
    out << "    \"requested\": [";
    for (std::size_t i = 0; i < targets.size(); ++i) {
        if (i != 0) out << ", ";
        json_string(out, targets[i]);
    }
    out << "],\n";
    out << "    \"published\": [";
    for (std::size_t i = 0; i < targets.size(); ++i) {
        if (i != 0) out << ", ";
        json_string(out, targets[i]);
    }
    out << "]\n";
    out << "  },\n";
    out << "  \"targets\": [";
    for (std::size_t i = 0; i < targets.size(); ++i) {
        if (i != 0) out << ", ";
        json_string(out, targets[i]);
    }
    out << "],\n";
    out << "  \"reports\": {\n";
    for (std::size_t i = 0; i < targets.size(); ++i) {
        if (i != 0) out << ",\n";
        out << "    "; json_string(out, targets[i]); out << ": ";
        json_string(out, "artifacts/" + targets[i] + "/cache_provenance.json");
    }
    out << "\n  }\n";
    out << "}\n";
    out.close();
    fs::rename(report_tmp, report);
}

}  // namespace termatrix
