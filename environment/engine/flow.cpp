#include "flow.hpp"

#include "descriptor.hpp"
#include "fingerprint.hpp"
#include "model.hpp"
#include "process.hpp"
#include "report.hpp"

#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace termatrix {

static fs::path driver_path;

static fs::path cache_root_from_env() {
    const char *raw = std::getenv("TERMATRIX_CACHE_ROOT");
    return raw ? fs::path(raw) : fs::path("/app/output/termatrix-cache");
}

static fs::path build_dir_for(const fs::path &out_root, const Descriptor &) {
    return out_root / "build/current";
}

static UnitPreState inspect_unit_cache(
    const fs::path &root,
    const fs::path &cache_root,
    const Descriptor &descriptor,
    const UnitDef &unit) {
    UnitPreState state;
    state.unit = unit.name;
    state.key = cache_key_for_unit(root, descriptor, unit);
    fs::path slot = cache_root / (unit.name + "-" + state.key);
    fs::path obj = slot / (unit.name + ".o");
    fs::path meta = slot / (unit.name + ".meta");
    if (fs::is_regular_file(obj) && fs::is_regular_file(meta)) {
        state.hit = true;
        state.reason = "cache-object-present";
    } else {
        state.hit = false;
        state.reason = "missing-cache-entry";
    }
    return state;
}

static std::vector<UnitPreState> inspect_target_cache(
    const fs::path &root,
    const fs::path &cache_root,
    const Descriptor &descriptor) {
    std::vector<UnitPreState> states;
    for (const auto &unit : object_units()) {
        states.push_back(inspect_unit_cache(root, cache_root, descriptor, unit));
    }
    return states;
}

static void build_target(
    const fs::path &root,
    const fs::path &out_root,
    const fs::path &artifact_root,
    const fs::path &cache_root,
    const Descriptor &descriptor) {
    auto pre_states = inspect_target_cache(root, cache_root, descriptor);
    fs::path stage = artifact_root / descriptor.target_name;
    fs::remove_all(stage);
    fs::create_directories(stage);
    fs::create_directories(cache_root);

    fs::path toolchain = root / descriptor.toolchain_file;
    fs::path build_dir = build_dir_for(out_root, descriptor);
    fs::create_directories(build_dir);

    run_checked({
        "cmake",
        "-S", root.string(),
        "-B", build_dir.string(),
        "-DCMAKE_TOOLCHAIN_FILE=" + toolchain.string(),
        "-DTERMATRIX_CACHE_ROOT=" + cache_root.string(),
        "-DTERMATRIX_DRIVER=" + driver_path.string(),
        "-DTERMATRIX_DESCRIPTOR_FILE=" + descriptor.descriptor_path.string(),
        "-DTERMATRIX_COMPILER_PROFILE=" + descriptor.compiler_profile,
        "-DCMAKE_BUILD_TYPE=Release",
    });
    run_checked({"cmake", "--build", build_dir.string(), "--target", "termatrix", "--parallel", "1"});
    run_checked({"cmake", "--install", build_dir.string(), "--prefix", stage.string()});

    write_pkg_config(stage, descriptor);
    write_identity_json(stage, descriptor);
    write_cache_report(root, stage, cache_root, descriptor, pre_states);
    std::cout << "built " << descriptor.target_name << " into " << stage << "\n";
}

int run_matrix_main(int argc, char **argv) {
    if (argc != 4) {
        throw std::runtime_error("usage: termatrix-driver run ROOT OUT_ROOT");
    }

    driver_path = fs::absolute(argv[0]);
    fs::path root = fs::absolute(argv[2]);
    fs::path out_root = fs::absolute(argv[3]);
    fs::path cache_root = cache_root_from_env();
    fs::create_directories(out_root);
    fs::create_directories(cache_root);

    std::vector<std::string> targets = parse_target_list();
    fs::path artifact_root = out_root / "artifacts";
    for (const auto &target : targets) {
        Descriptor descriptor = load_descriptor(root, target);
        build_target(root, out_root, artifact_root, cache_root, descriptor);
    }
    write_top_report(out_root, targets);
    return 0;
}

}  // namespace termatrix
