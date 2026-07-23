import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ENV_ROOT = Path("/app/environment")
OUT_ROOT = Path("/app/output/abi-matrix")
CACHE_ROOT = Path("/app/output/termatrix-cache")
TMP_ROOT = Path(tempfile.mkdtemp(prefix="tmx-"))

GENERATOR = "termatrix-cmake-cache-matrix-v2"
UNITS = ["identity", "mix"]
KEY_FIELDS = [
    "unit_source_sha256",
    "public_header_sha256",
    "descriptor_sha256",
    "toolchain_sha256",
    "interface_fragment_sha256",
    "build_logic_sha256",
    "target",
    "abi_family",
    "compiler_profile",
    "unit_name",
]
TARGET_ORDER = ["glibc-x86_64", "musl-x86_64"]
REVERSED_TARGETS = list(reversed(TARGET_ORDER))
REVERSED_TARGETS_ARG = " ".join(REVERSED_TARGETS)
EXPECTED_PUBLIC_HEADER_BYTES = (
    b"#ifndef TERMATRIX_MATRIX_H\n"
    b"#define TERMATRIX_MATRIX_H\n"
    b"\n"
    b"#include <stdint.h>\n"
    b'#include "termatrix/detail/export.h"\n'
    b"\n"
    b"TERMATRIX_BEGIN_C\n"
    b"\n"
    b"const char *termatrix_compiled_abi(void);\n"
    b"const char *termatrix_compiled_target(void);\n"
    b"uint32_t termatrix_abi_code(void);\n"
    b"uint32_t termatrix_mix(uint32_t seed);\n"
    b"\n"
    b"TERMATRIX_END_C\n"
    b"\n"
    b"#endif\n"
)


def read_env_file(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        fields[key] = value
    return fields


TARGETS = {
    target: read_env_file(ENV_ROOT / "config/matrix" / f"{target}.env")
    for target in TARGET_ORDER
}


def reset_outputs() -> None:
    assert_public_header_unchanged(ENV_ROOT / "include/termatrix/matrix.h")
    shutil.rmtree(OUT_ROOT, ignore_errors=True)
    shutil.rmtree(CACHE_ROOT, ignore_errors=True)
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    Path("/app/output").mkdir(parents=True, exist_ok=True)


def run_matrix(targets: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    if targets is None:
        env.pop("TERMATRIX_TARGETS", None)
    else:
        env["TERMATRIX_TARGETS"] = targets
    result = subprocess.run(
        ["bash", "/app/environment/scripts/build_matrix.sh", "/app/output/abi-matrix"],
        cwd="/app",
        env=env,
        text=True,
        capture_output=True,
        timeout=900,
    )
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def load_json(path: Path) -> dict:
    assert path.is_file(), f"missing {path}"
    return json.loads(path.read_text())


def sha256_file(path: Path) -> str:
    result = subprocess.run(["sha256sum", str(path)], text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.split()[0]


def public_header_sha256() -> str:
    return sha256_file(ENV_ROOT / "include/termatrix/matrix.h")


def assert_public_header_unchanged(path: Path) -> None:
    content = path.read_bytes()
    assert content == EXPECTED_PUBLIC_HEADER_BYTES, f"{path} was modified"


def strings(path: Path) -> str:
    result = subprocess.run(["strings", str(path)], text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return result.stdout


def target_fields(target: str) -> dict[str, str]:
    fields = TARGETS[target]
    assert fields["target_name"] == target
    return fields


def define_flag(name: str) -> str:
    return f"-D{name}=1"


def interface_identity(abi_family: str, target: str) -> str:
    return f"termatrix-interface|abi={abi_family}|target={target}"


def other_defines(target: str) -> list[str]:
    current = target_fields(target)
    return [
        define_flag(fields[name])
        for other, fields in TARGETS.items()
        if other != target
        for name in ("abi_define", "target_define")
        if fields[name] not in {current["abi_define"], current["target_define"]}
    ]


def assert_top_report(expected_targets: list[str]) -> dict:
    top = load_json(OUT_ROOT / "build-cache-provenance.json")
    assert top["schema_version"] == 2
    assert top["generator"] == GENERATOR
    assert str(top["transaction"]["status"]).lower() == "success"
    assert top["transaction"]["requested"] == expected_targets
    assert top["transaction"]["published"] == expected_targets
    assert top["targets"] == expected_targets
    assert list(top["reports"].keys()) == expected_targets
    for target in expected_targets:
        assert top["reports"][target] == {
            "cache": f"artifacts/{target}/cache_provenance.json",
            "interface": f"artifacts/{target}/interface_ledger.json",
        }
    return top


def units_by_name(report: dict) -> dict[str, dict]:
    assert "units" in report["cache"], "cache unit array must be named units"
    units = {unit["unit"]: unit for unit in report["cache"]["units"]}
    assert sorted(units) == UNITS
    return units


def unit_keys(report: dict) -> dict[str, str]:
    return {name: unit["key"] for name, unit in units_by_name(report).items()}


def assert_hit_state(report: dict, *hit_units: str) -> None:
    expected = set(hit_units)
    for name, unit in units_by_name(report).items():
        assert bool(unit["hit"]) is (name in expected), (name, unit)


def assert_target_report(target: str) -> dict:
    fields = target_fields(target)
    abi = fields["abi_family"]
    stage = OUT_ROOT / "artifacts" / target
    assert_public_header_unchanged(ENV_ROOT / "include/termatrix/matrix.h")
    assert_public_header_unchanged(stage / "include/termatrix/matrix.h")
    report = load_json(stage / "cache_provenance.json")
    assert report["schema_version"] == 2
    assert report["generator"] == GENERATOR
    assert report["requested"]["target"] == target
    assert report["requested"]["abi_family"] == abi
    assert report["requested"]["toolchain_file"] == fields["toolchain_file"]
    assert report["requested"]["descriptor_file"] == f"config/matrix/{target}.env"
    assert report["requested"]["interface_fragment_file"] == fields["interface_fragment_file"]
    assert report["requested"]["compiler_profile"] == fields["compiler_profile"]
    assert report["artifact"]["object_units"] == UNITS
    assert report["artifact"]["library_sha256"] == sha256_file(stage / "lib/libtermatrix.a")
    assert report["artifact"]["header_sha256"] == sha256_file(stage / "include/termatrix/matrix.h")
    assert report["artifact"]["header_sha256"] == public_header_sha256()
    assert report["cache"]["key_fields"] == KEY_FIELDS

    identity_text = strings(stage / "lib/libtermatrix.a")
    units = units_by_name(report)
    for unit_name, unit in units.items():
        assert unit["valid_for_request"], unit
        assert unit["object_target"] == target
        assert unit["object_abi_family"] == abi
        assert unit["identity"] == f"termatrix-object|abi={abi}|target={target}|unit={unit_name}"
        assert unit["identity"] in identity_text
        cache_obj = CACHE_ROOT / unit["cache_path"]
        assert cache_obj.is_file(), cache_obj
        assert unit["object_sha256"] == sha256_file(cache_obj)
        assert unit["actual_object_sha256"] == unit["object_sha256"]
        for field in (
            "unit_source_sha256",
            "public_header_sha256",
            "descriptor_sha256",
            "toolchain_sha256",
            "interface_fragment_sha256",
            "build_logic_sha256",
        ):
            assert isinstance(unit[field], str) and len(unit[field]) == 64
    return report


def assert_interface_ledger(target: str) -> dict:
    fields = target_fields(target)
    stage = OUT_ROOT / "artifacts" / target
    ledger = load_json(stage / "interface_ledger.json")
    assert ledger["schema_version"] == 2
    assert ledger["generator"] == GENERATOR
    assert ledger["requested"]["target"] == target
    assert ledger["requested"]["abi_family"] == fields["abi_family"]
    assert ledger["requested"]["descriptor_file"] == f"config/matrix/{target}.env"
    assert ledger["requested"]["toolchain_file"] == fields["toolchain_file"]
    assert ledger["requested"]["interface_fragment_file"] == fields["interface_fragment_file"]
    assert ledger["requested"]["compiler_profile"] == fields["compiler_profile"]
    assert ledger["interface"]["pkg_config"] == "lib/pkgconfig/termatrix.pc"
    assert ledger["interface"]["cmake_config"] == "lib/cmake/Termatrix/TermatrixConfig.cmake"
    assert ledger["interface"]["cmake_targets"] == "lib/cmake/Termatrix/TermatrixTargets.cmake"
    assert ledger["interface"]["imported_target"] == "Termatrix::termatrix"
    assert ledger["interface"]["include_dir"] == "include"
    assert ledger["interface"]["library"] == "lib/libtermatrix.a"
    assert ledger["interface"]["compile_definitions"] == [fields["abi_define"], fields["target_define"]]
    assert ledger["interface"]["identity"] == interface_identity(fields["abi_family"], target)
    assert ledger["interface"]["valid_for_request"] is True
    assert ledger["cache"]["report"] == "cache_provenance.json"
    assert ledger["cache"]["units"] == UNITS

    digest_paths = {
        "library": stage / "lib/libtermatrix.a",
        "public_header": stage / "include/termatrix/matrix.h",
        "pkg_config": stage / "lib/pkgconfig/termatrix.pc",
        "cmake_config": stage / "lib/cmake/Termatrix/TermatrixConfig.cmake",
        "cmake_targets": stage / "lib/cmake/Termatrix/TermatrixTargets.cmake",
        "descriptor": ENV_ROOT / f"config/matrix/{target}.env",
        "toolchain": ENV_ROOT / fields["toolchain_file"],
        "interface_fragment": ENV_ROOT / fields["interface_fragment_file"],
    }
    for key, path in digest_paths.items():
        assert ledger["digests"][f"{key}_sha256"] == sha256_file(path)
    assert isinstance(ledger["digests"]["build_logic_sha256"], str)
    assert len(ledger["digests"]["build_logic_sha256"]) == 64

    config_text = (stage / ledger["interface"]["cmake_config"]).read_text()
    targets_text = (stage / ledger["interface"]["cmake_targets"]).read_text()
    assert "Termatrix::termatrix" in config_text + targets_text
    assert ledger["digests"]["interface_fragment_sha256"] in config_text + targets_text
    return ledger


def pkg_config(target: str, args: list[str]) -> list[str]:
    env = os.environ.copy()
    env["PKG_CONFIG_PATH"] = str(OUT_ROOT / "artifacts" / target / "lib/pkgconfig")
    result = subprocess.run(
        ["pkg-config", *args, "termatrix"],
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.split()


def assert_pkg_config_consumer_builds(target: str) -> None:
    fields = target_fields(target)
    pc_text = (OUT_ROOT / "artifacts" / target / "lib/pkgconfig/termatrix.pc").read_text()
    assert define_flag(fields["abi_define"]) in pc_text
    assert define_flag(fields["target_define"]) in pc_text
    for other in other_defines(target):
        assert other not in pc_text

    cfile = TMP_ROOT / f"pkg-consumer-{target}.c"
    exe = TMP_ROOT / f"pkg-consumer-{target}"
    cfile.write_text(
        f"""
#include <string.h>
#include <termatrix/matrix.h>
int main(void) {{
    if (strcmp(termatrix_compiled_target(), "{target}") != 0) return 10;
    if (strcmp(termatrix_compiled_abi(), "{fields['abi_family']}") != 0) return 11;
#ifndef {fields['abi_define']}
    return 12;
#endif
#ifndef {fields['target_define']}
    return 13;
#endif
    return termatrix_mix(7u) == 0u ? 14 : 0;
}}
""".lstrip()
    )
    flags = pkg_config(target, ["--cflags", "--libs"])
    compiled = subprocess.run(
        ["gcc", str(cfile), "-o", str(exe), *flags],
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    executed = subprocess.run([str(exe)], text=True, capture_output=True, timeout=30)
    assert executed.returncode == 0, executed.stdout + executed.stderr


def assert_cmake_consumer_builds_after_relocation(target: str) -> None:
    fields = target_fields(target)
    copied_prefix = TMP_ROOT / f"relocated-{target}"
    shutil.rmtree(copied_prefix, ignore_errors=True)
    shutil.copytree(OUT_ROOT / "artifacts" / target, copied_prefix)

    project = TMP_ROOT / f"cmake-consumer-{target}"
    build = TMP_ROOT / f"cmake-consumer-build-{target}"
    shutil.rmtree(project, ignore_errors=True)
    shutil.rmtree(build, ignore_errors=True)
    project.mkdir()
    (project / "CMakeLists.txt").write_text(
        """
cmake_minimum_required(VERSION 3.18)
project(termatrix_consumer C)
find_package(Termatrix CONFIG REQUIRED)
add_executable(consumer main.c)
target_link_libraries(consumer PRIVATE Termatrix::termatrix)
""".lstrip()
    )
    (project / "main.c").write_text(
        f"""
#include <string.h>
#include <termatrix/matrix.h>
int main(void) {{
    if (strcmp(termatrix_compiled_target(), "{target}") != 0) return 20;
    if (strcmp(termatrix_compiled_abi(), "{fields['abi_family']}") != 0) return 21;
#ifndef {fields['abi_define']}
    return 22;
#endif
#ifndef {fields['target_define']}
    return 23;
#endif
    return termatrix_abi_code() == 0 ? 24 : 0;
}}
""".lstrip()
    )
    configure = subprocess.run(
        ["cmake", "-S", str(project), "-B", str(build), f"-DCMAKE_PREFIX_PATH={copied_prefix}"],
        text=True,
        capture_output=True,
        timeout=90,
    )
    assert configure.returncode == 0, configure.stdout + configure.stderr
    build_result = subprocess.run(
        ["cmake", "--build", str(build), "--parallel", "1"],
        text=True,
        capture_output=True,
        timeout=90,
    )
    assert build_result.returncode == 0, build_result.stdout + build_result.stderr
    executed = subprocess.run([str(build / "consumer")], text=True, capture_output=True, timeout=30)
    assert executed.returncode == 0, executed.stdout + executed.stderr


def mutate_text(path: Path, suffix: str) -> str:
    original = path.read_text()
    path.write_text(original + suffix)
    return original


def restore_text(path: Path, original: str) -> None:
    path.write_text(original)


def target_observations(target: str) -> dict[str, object]:
    report = assert_target_report(target)
    ledger = assert_interface_ledger(target)
    return {
        "library": report["artifact"]["library_sha256"],
        "header": report["artifact"]["header_sha256"],
        "unit_keys": unit_keys(report),
        "interface": ledger["interface"],
        "digests": ledger["digests"],
    }


def test_reversed_order_fresh_replay_and_consumers() -> None:
    """A reversed full request must publish complete cache and interface capsules that consumers can use."""
    reset_outputs()
    run_matrix(REVERSED_TARGETS_ARG)
    assert_top_report(REVERSED_TARGETS)
    first = {target: assert_target_report(target) for target in REVERSED_TARGETS}
    for target in REVERSED_TARGETS:
        assert_hit_state(first[target])
        assert_interface_ledger(target)
        assert_pkg_config_consumer_builds(target)
        assert_cmake_consumer_builds_after_relocation(target)

    run_matrix(REVERSED_TARGETS_ARG)
    assert_top_report(REVERSED_TARGETS)
    for target in REVERSED_TARGETS:
        replay = assert_target_report(target)
        assert_hit_state(replay, "identity", "mix")
        assert unit_keys(replay) == unit_keys(first[target])
        assert_interface_ledger(target)
    stable_bytes = {
        path: path.read_bytes()
        for path in [
            OUT_ROOT / "build-cache-provenance.json",
            OUT_ROOT / "artifacts/musl-x86_64/cache_provenance.json",
            OUT_ROOT / "artifacts/musl-x86_64/interface_ledger.json",
            OUT_ROOT / "artifacts/glibc-x86_64/cache_provenance.json",
            OUT_ROOT / "artifacts/glibc-x86_64/interface_ledger.json",
        ]
    }
    run_matrix(REVERSED_TARGETS_ARG)
    for target in REVERSED_TARGETS:
        assert_hit_state(assert_target_report(target), "identity", "mix")
        assert_interface_ledger(target)
    for path, content in stable_bytes.items():
        assert path.read_bytes() == content


def test_interface_fragment_change_rotates_capsule_and_cache_keys() -> None:
    """Changing an interface authority fragment must rotate generated package metadata and cache identity."""
    reset_outputs()
    run_matrix("glibc-x86_64")
    first_report = assert_target_report("glibc-x86_64")
    first_ledger = assert_interface_ledger("glibc-x86_64")
    original_keys = unit_keys(first_report)
    fragment = ENV_ROOT / target_fields("glibc-x86_64")["interface_fragment_file"]
    original = mutate_text(fragment, "\n# interface digest probe\n")
    try:
        run_matrix("glibc-x86_64")
        changed_report = assert_target_report("glibc-x86_64")
        changed_ledger = assert_interface_ledger("glibc-x86_64")
    finally:
        restore_text(fragment, original)

    assert changed_ledger["digests"]["interface_fragment_sha256"] != first_ledger["digests"]["interface_fragment_sha256"]
    assert changed_ledger["digests"]["cmake_config_sha256"] != first_ledger["digests"]["cmake_config_sha256"]
    assert changed_ledger["digests"]["cmake_targets_sha256"] != first_ledger["digests"]["cmake_targets_sha256"]
    for unit in UNITS:
        assert unit_keys(changed_report)[unit] != original_keys[unit]
    assert_hit_state(changed_report)
    assert_cmake_consumer_builds_after_relocation("glibc-x86_64")


def test_partial_source_change_keeps_unmodified_unit_hit() -> None:
    """Changing only one object-unit source must preserve the sibling unit as a valid cache hit."""
    reset_outputs()
    run_matrix("musl-x86_64")
    first = assert_target_report("musl-x86_64")
    original_keys = unit_keys(first)
    source = ENV_ROOT / "src/mix.c"
    original = mutate_text(source, "\nstatic const unsigned tmix_probe = 17u;\n")
    try:
        run_matrix("musl-x86_64")
        changed = assert_target_report("musl-x86_64")
    finally:
        restore_text(source, original)

    changed_keys = unit_keys(changed)
    changed_units = units_by_name(changed)
    assert changed_keys["identity"] == original_keys["identity"]
    assert bool(changed_units["identity"]["hit"])
    assert changed_keys["mix"] != original_keys["mix"]
    assert not bool(changed_units["mix"]["hit"])
    assert_interface_ledger("musl-x86_64")


def test_corrupted_cache_object_rebuilds_only_the_bad_unit() -> None:
    """A damaged cached object must be rebuilt without discarding the clean sibling object."""
    reset_outputs()
    run_matrix("glibc-x86_64")
    first = assert_target_report("glibc-x86_64")
    units = units_by_name(first)
    bad_obj = CACHE_ROOT / units["identity"]["cache_path"]
    good_mix_key = units["mix"]["key"]
    with bad_obj.open("ab") as handle:
        handle.write(b"\ncorrupt cached object\n")
    assert sha256_file(bad_obj) != units["identity"]["object_sha256"]

    run_matrix("glibc-x86_64")
    recovered = assert_target_report("glibc-x86_64")
    recovered_units = units_by_name(recovered)
    assert not bool(recovered_units["identity"]["hit"])
    assert recovered_units["identity"]["reason"] in {"corrupt-object", "missing-cache-entry", "stale-metadata"}
    assert recovered_units["identity"]["object_sha256"] == units["identity"]["object_sha256"]
    assert bool(recovered_units["mix"]["hit"])
    assert recovered_units["mix"]["key"] == good_mix_key
    assert_interface_ledger("glibc-x86_64")


def test_stale_publish_stage_and_tampered_interface_are_recovered() -> None:
    """A later valid transaction must clean abandoned staging and regenerate tampered interface files."""
    reset_outputs()
    run_matrix("musl-x86_64")
    before = assert_interface_ledger("musl-x86_64")
    config = OUT_ROOT / "artifacts/musl-x86_64/lib/cmake/Termatrix/TermatrixConfig.cmake"
    config.write_text(config.read_text() + "\nset(TERMATRIX_TARGET_DEFINE TERMATRIX_TARGET_GLIBC_X86_64)\n")
    stale = OUT_ROOT / ".publish-tmp-stale"
    (stale / "artifacts/musl-x86_64").mkdir(parents=True)
    (stale / "artifacts/musl-x86_64/interface_ledger.json").write_text('{"stale": true}\n')

    run_matrix("musl-x86_64")
    report = assert_target_report("musl-x86_64")
    after = assert_interface_ledger("musl-x86_64")
    assert_hit_state(report, "identity", "mix")
    assert after["digests"] == before["digests"]
    assert not stale.exists()
    assert_cmake_consumer_builds_after_relocation("musl-x86_64")


def test_invalid_target_transaction_preserves_previous_artifacts_and_clears_success() -> None:
    """Unknown targets must fail without publishing partial artifacts or leaving a stale success report."""
    reset_outputs()
    run_matrix()
    assert_top_report(TARGET_ORDER)
    before = {
        path: path.read_bytes()
        for path in [
            OUT_ROOT / "artifacts/glibc-x86_64/lib/cmake/Termatrix/TermatrixTargets.cmake",
            OUT_ROOT / "artifacts/glibc-x86_64/interface_ledger.json",
            OUT_ROOT / "artifacts/musl-x86_64/interface_ledger.json",
        ]
    }

    failed = run_matrix("glibc-x86_64 freebsd-x86_64", check=False)
    assert failed.returncode != 0
    top = OUT_ROOT / "build-cache-provenance.json"
    if top.exists():
        top_payload = load_json(top)
        assert str(top_payload.get("transaction", {}).get("status", "")).lower() != "success"
    for path, content in before.items():
        assert path.read_bytes() == content
    assert not (OUT_ROOT / "artifacts/freebsd-x86_64").exists()

    run_matrix(REVERSED_TARGETS_ARG)
    assert_top_report(REVERSED_TARGETS)
    for target in REVERSED_TARGETS:
        assert_hit_state(assert_target_report(target), "identity", "mix")
        assert_interface_ledger(target)


def test_subset_publish_then_full_reuses_cache_and_replaces_scope() -> None:
    """Subset publishes must replace artifact scope while later full publishes reuse valid cache entries."""
    reset_outputs()
    run_matrix()
    assert_top_report(TARGET_ORDER)
    run_matrix("glibc-x86_64")
    assert_top_report(["glibc-x86_64"])
    glibc = assert_target_report("glibc-x86_64")
    assert_hit_state(glibc, "identity", "mix")
    assert_interface_ledger("glibc-x86_64")
    assert not (OUT_ROOT / "artifacts/musl-x86_64").exists()
    stable_report = (OUT_ROOT / "artifacts/glibc-x86_64/cache_provenance.json").read_bytes()
    stable_ledger = (OUT_ROOT / "artifacts/glibc-x86_64/interface_ledger.json").read_bytes()

    run_matrix("glibc-x86_64")
    assert_hit_state(assert_target_report("glibc-x86_64"), "identity", "mix")
    assert (OUT_ROOT / "artifacts/glibc-x86_64/cache_provenance.json").read_bytes() == stable_report
    assert (OUT_ROOT / "artifacts/glibc-x86_64/interface_ledger.json").read_bytes() == stable_ledger

    run_matrix()
    assert_top_report(TARGET_ORDER)
    for target in TARGET_ORDER:
        assert_hit_state(assert_target_report(target), "identity", "mix")
        assert_interface_ledger(target)


def test_metamorphic_target_order_keeps_per_target_identity() -> None:
    """Changing target order must affect top-level order only, not per-target artifact identity."""
    reset_outputs()
    run_matrix()
    assert_top_report(TARGET_ORDER)
    normal = {target: target_observations(target) for target in TARGET_ORDER}

    run_matrix(REVERSED_TARGETS_ARG)
    assert_top_report(REVERSED_TARGETS)
    reversed_observations = {target: target_observations(target) for target in REVERSED_TARGETS}
    for target in TARGET_ORDER:
        assert reversed_observations[target] == normal[target]

    normal_top = load_json(OUT_ROOT / "build-cache-provenance.json")
    assert normal_top["transaction"]["requested"] == REVERSED_TARGETS
    assert list(normal_top["reports"].keys()) == REVERSED_TARGETS
