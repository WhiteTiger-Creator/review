#include "compile.hpp"

#include "descriptor.hpp"
#include "fingerprint.hpp"
#include "model.hpp"
#include "process.hpp"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unistd.h>

namespace fs = std::filesystem;

namespace termatrix {

static UnitDef unit_from_args(const std::string &unit, const std::string &source_rel) {
    for (const auto &known : object_units()) {
        if (known.name == unit) {
            return {unit, source_rel};
        }
    }
    throw std::runtime_error("unknown object unit: " + unit);
}

int key_unit_main(int argc, char **argv) {
    if (argc != 6) {
        throw std::runtime_error("usage: termatrix-driver key-unit ROOT UNIT SOURCE_REL TARGET");
    }
    fs::path root = argv[2];
    std::string unit_name = argv[3];
    std::string source_rel = argv[4];
    std::string target = argv[5];
    Descriptor descriptor = load_descriptor(root, target);
    UnitDef unit = unit_from_args(unit_name, source_rel);
    std::cout << cache_key_for_unit(root, descriptor, unit) << "\n";
    return 0;
}

int compile_unit_main(int argc, char **argv) {
    if (argc != 15) {
        throw std::runtime_error("usage: termatrix-driver compile-unit CC OBJ ROOT UNIT SOURCE_REL TARGET ABI ABI_DEFINE TARGET_DEFINE KEY TOOLCHAIN DESCRIPTOR PROFILE");
    }

    std::string cc = argv[2];
    fs::path obj = argv[3];
    fs::path root = argv[4];
    std::string unit_name = argv[5];
    std::string source_rel = argv[6];
    std::string target = argv[7];
    std::string abi = argv[8];
    std::string abi_define = argv[9];
    std::string target_define = argv[10];
    std::string key = argv[11];
    fs::path toolchain = argv[12];
    fs::path descriptor_path = argv[13];
    std::string profile = argv[14];

    fs::create_directories(obj.parent_path());
    fs::path obj_tmp = obj.string() + ".tmp." + std::to_string(static_cast<long long>(getpid()));
    fs::path meta = obj.parent_path() / (unit_name + ".meta");
    fs::path meta_tmp = meta.string() + ".tmp." + std::to_string(static_cast<long long>(getpid()));
    fs::path source = root / source_rel;

    run_checked({
        cc,
        "-std=c11",
        "-O2",
        "-fPIC",
        "-I" + (root / "include").string(),
        "-D" + abi_define + "=1",
        "-D" + target_define + "=1",
        "-DTERMATRIX_TARGET_NAME=\"" + target + "\"",
        "-DTERMATRIX_CACHE_UNIT=\"" + unit_name + "\"",
        "-c",
        source.string(),
        "-o",
        obj_tmp.string(),
    });

    std::string object_sha = sha256_file(obj_tmp);
    std::string compiler_probe = capture_command({cc, "-dumpmachine"});
    if (!compiler_probe.empty() && compiler_probe.back() == '\n') {
        compiler_probe.pop_back();
    }
    std::string compiler_version = capture_command({cc, "-dumpversion"});
    if (!compiler_version.empty() && compiler_version.back() == '\n') {
        compiler_version.pop_back();
    }

    std::ofstream out(meta_tmp);
    out << "unit=" << unit_name << "\n";
    out << "source_path=" << source_rel << "\n";
    out << "target=" << target << "\n";
    out << "abi_family=" << abi << "\n";
    out << "abi_define=" << abi_define << "\n";
    out << "target_define=" << target_define << "\n";
    out << "cache_key=" << key << "\n";
    out << "object_sha256=" << object_sha << "\n";
    out << "unit_source_sha256=" << sha256_file(source) << "\n";
    out << "public_header_sha256=" << tree_digest(root / "include") << "\n";
    out << "descriptor_sha256=" << sha256_file(descriptor_path) << "\n";
    out << "toolchain_sha256=" << sha256_file(toolchain) << "\n";
    out << "build_logic_sha256=" << build_logic_digest(root) << "\n";
    out << "compiler_profile=" << profile << "\n";
    out << "compiler_probe=" << compiler_probe << "\n";
    out << "compiler_version=" << compiler_version << "\n";
    out << "identity=termatrix-object|abi=" << abi << "|target=" << target << "|unit=" << unit_name << "\n";
    out.close();

    fs::rename(obj_tmp, obj);
    fs::rename(meta_tmp, meta);
    return 0;
}

}  // namespace termatrix
