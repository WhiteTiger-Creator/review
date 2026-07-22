import subprocess
import shutil
from pathlib import Path


APP = Path("/app")


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=True)


def checksum(identifier, payload, hops, priority):
    state = 2166136261
    for text in [identifier, payload, *hops]:
        for byte in text.encode():
            state ^= byte
            state = (state * 16777619) & 0xFFFFFFFF
    state ^= priority
    return state & 0xFFFF


def build_and_install(tmp_path, build_type):
    build = tmp_path / f"build-{build_type.lower()}"
    prefix = tmp_path / f"install-{build_type.lower()}"
    run([
        "cmake",
        "-S",
        str(APP),
        "-B",
        str(build),
        "-G",
        "Ninja",
        f"-DCMAKE_BUILD_TYPE={build_type}",
        f"-DCMAKE_INSTALL_PREFIX={prefix}",
    ])
    run(["cmake", "--build", str(build), "--parallel", "2"])
    run(["cmake", "--install", str(build)])
    return prefix


def run_route(prefix, build_type, identifier, payload, hops, priority):
    exe = prefix / "bin" / "route_cli"
    cmd = [str(exe), "--id", identifier, "--payload", payload]
    for hop in hops:
        cmd.extend(["--hop", hop])
    cmd.extend(["--priority", str(priority)])
    result = run(cmd)
    expected = f"{identifier}|{build_type}|{'->'.join(hops)}|{checksum(identifier, payload, hops, priority)}"
    assert result.stdout.strip() == expected
    assert result.stderr == ""


def test_release_install_runs_with_generated_grpc_and_plugin(tmp_path):
    """A Release install builds generated protocol code and runs from its prefix."""
    prefix = build_and_install(tmp_path, "Release")
    plugin = prefix / "lib" / "route" / "libroute_audit.so"
    assert plugin.exists(), "audit plugin must be installed in the runtime layout"
    run_route(prefix, "Release", "alpha", "orbit", ["edge", "core", "egress"], 7)


def test_debug_consumer_inherits_headers_links_and_mode(tmp_path):
    """A Debug build exposes public generated headers and build-mode definitions to consumers."""
    prefix = build_and_install(tmp_path, "Debug")
    consumer_dir = tmp_path / "consumer"
    consumer_dir.mkdir()
    (consumer_dir / "main.cpp").write_text(
        '#include "router/router.h"\n'
        "int main() { routekit::v1::RouteJob job; job.set_id(router::expected_mode()); return job.id().empty(); }\n"
    )
    (consumer_dir / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.25)\n"
        "project(RouteKitConsumer LANGUAGES CXX)\n"
        "find_package(RouteKit REQUIRED CONFIG)\n"
        "add_executable(consumer main.cpp)\n"
        "target_link_libraries(consumer PRIVATE RouteKit::router)\n"
    )
    build_dir = tmp_path / "consumer-build"
    run([
        "cmake",
        "-S",
        str(consumer_dir),
        "-B",
        str(build_dir),
        "-G",
        "Ninja",
        f"-DCMAKE_PREFIX_PATH={prefix}",
    ])
    run(["cmake", "--build", str(build_dir), "--parallel", "2"])
    run([str(build_dir / "consumer")])
    run_route(prefix, "Debug", "beta", "payload", ["north", "south"], 19)


def test_installed_executable_has_no_unresolved_project_libraries(tmp_path):
    """The installed executable and plugin have runtime lookup paths for project shared objects."""
    prefix = build_and_install(tmp_path, "Release")
    ldd_exe = run(["ldd", str(prefix / "bin" / "route_cli")]).stdout
    ldd_plugin = run(["ldd", str(prefix / "lib" / "route" / "libroute_audit.so")]).stdout
    assert (prefix / "lib" / "libroute_policy.so").exists()
    assert "not found" not in ldd_exe
    assert "not found" not in ldd_plugin


def test_relocated_install_prefix_still_runs_and_exports_package(tmp_path):
    """A copied install tree remains self-contained for route_cli and CMake consumers."""
    prefix = build_and_install(tmp_path, "Release")
    relocated = tmp_path / "relocated-routekit"
    shutil.copytree(prefix, relocated)
    run_route(relocated, "Release", "gamma", "copyable", ["inlet", "relay", "sink"], 23)

    consumer_dir = tmp_path / "relocated-consumer"
    consumer_dir.mkdir()
    (consumer_dir / "main.cpp").write_text(
        '#include "router/router.h"\n'
        "#include <iostream>\n"
        "int main() { routekit::v1::RouteJob job; job.set_id(router::expected_mode()); "
        "job.set_payload(\"relocated\"); job.add_hops(\"edge\"); "
        "std::cout << router::render(router::summarize(job)) << \"\\n\"; return 0; }\n"
    )
    (consumer_dir / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.25)\n"
        "project(RelocatedRouteKitConsumer LANGUAGES CXX)\n"
        "find_package(RouteKit REQUIRED CONFIG)\n"
        "add_executable(consumer main.cpp)\n"
        "target_link_libraries(consumer PRIVATE RouteKit::router)\n"
    )
    build_dir = tmp_path / "relocated-consumer-build"
    run([
        "cmake",
        "-S",
        str(consumer_dir),
        "-B",
        str(build_dir),
        "-G",
        "Ninja",
        f"-DCMAKE_PREFIX_PATH={relocated}",
    ])
    run(["cmake", "--build", str(build_dir), "--parallel", "2"])
    assert run([str(build_dir / "consumer")]).stdout.strip().startswith("Release|Release|edge|")
