import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path


APP = Path(os.environ.get("APP_DIR", "/app"))
SCRIPT = APP / "bin" / "freeze-bazel-registry"
SUCCESS = {
    "registry.tar.gz",
    "module-order.txt",
    "selection.tsv",
    "artifact-manifest.tsv",
    "registry-report.json",
    "registry",
}
BASELINE_ORDER = [
    "bazel_skylib@1.7.1",
    "legacy_crypto@0.9.1",
    "lint_tools@0.4.0",
    "linux_sandbox@1.2.0",
    "rules_java@7.6.0",
    "zlib@1.3.1",
    "protobuf@29.0.0",
    "com_acme_app@1.0.0",
    "rules_proto@6.0.0",
    "telemetry_rules@2.1.0",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def copy_input(tmp_path: Path) -> Path:
    dst = tmp_path / "input"
    shutil.copytree(APP / "input", dst)
    return dst


def run_gate(input_dir: Path, out_dir: Path, expect_ok=True):
    proc = subprocess.run(
        [str(SCRIPT), str(input_dir), str(out_dir)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=25,
    )
    if expect_ok:
        detail = proc.stdout + proc.stderr
        if (out_dir / "error.txt").exists():
            detail += (out_dir / "error.txt").read_text()
        assert proc.returncode == 0, detail
    else:
        assert proc.returncode != 0, "command unexpectedly succeeded"
    return proc


def read_dicts(path: Path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def read_tsv(path: Path):
    with path.open(newline="") as f:
        return list(csv.reader(f, delimiter="\t"))


def parse_profile(path: Path):
    result = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def replace_profile_value(input_dir: Path, key: str, value: str):
    profile = input_dir / "profile.env"
    lines = []
    changed = False
    for raw in profile.read_text().splitlines():
        if raw.strip().startswith(f"{key}="):
            lines.append(f"{key}={value}")
            changed = True
        else:
            lines.append(raw)
    assert changed
    profile.write_text("\n".join(lines) + "\n")


def assert_failure(out_dir: Path, category: str):
    assert (out_dir / "error.txt").exists()
    assert (out_dir / "error.txt").read_text().split()[0] == category
    for name in SUCCESS:
        assert not (out_dir / name).exists(), f"stale success output left: {name}"


def append_module(input_dir: Path, module: str, version: str, compat="1", license_name="Apache-2.0", min_bazel="7.0.0", yanked="-", attestor="BazelCentral"):
    with (input_dir / "catalog" / "modules.tsv").open("a") as f:
        f.write(f"{module}\t{version}\t{compat}\t{license_name}\t{min_bazel}\t{yanked}\n")
    rel = Path("sources") / module / version / f"{module}-{version}.tar.gz"
    (input_dir / rel).parent.mkdir(parents=True, exist_ok=True)
    data = f"archive for {module}@{version}\n".encode()
    (input_dir / rel).write_bytes(data)
    digest = sha256_bytes(data)
    with (input_dir / "catalog" / "archives.tsv").open("a") as f:
        f.write(f"{module}\t{version}\t{rel}\t{digest}\t{len(data)}\t{module}-{version}\n")
    with (input_dir / "catalog" / "provenance.tsv").open("a") as f:
        f.write(f"{module}\t{version}\t{digest}\t{attestor}\tverified\t2027-12-31\n")
    return digest, len(data), rel


def append_patch(input_dir: Path, module: str, version: str, name: str, content: bytes, apply="true") -> str:
    rel = Path("patches") / module / version / name
    path = input_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    digest = sha256_bytes(content)
    with (input_dir / "catalog" / "patches.tsv").open("a") as f:
        f.write(f"{module}\t{version}\t{rel}\t{digest}\t{len(content)}\t{apply}\n")
    return rel.as_posix()


def archive_rows(input_dir: Path):
    rows = {}
    for row in read_dicts(input_dir / "catalog" / "archives.tsv"):
        rows[(row["module"], row["version"])] = row
    return rows


def test_factory_linux_registry_is_exact_and_reproducible(tmp_path):
    input_dir = copy_input(tmp_path)
    out_dir = tmp_path / "out"
    run_gate(input_dir, out_dir)

    assert {p.name for p in out_dir.iterdir()} == SUCCESS
    order = (out_dir / "module-order.txt").read_text().splitlines()
    assert order == BASELINE_ORDER
    assert "rules_java@7.4.0" not in order
    assert "protobuf@28.2.0" not in order
    assert "zlib@1.2.13" not in order
    assert "darwin_support@1.0.0" not in order
    assert "lint_tools@0.4.0" in order
    assert "legacy_crypto@0.9.1" in order

    selection = read_tsv(out_dir / "selection.tsv")
    assert len(selection) == len(order)
    assert [f"{row[0]}@{row[1]}" for row in selection] == order
    direct = {f"{row[0]}@{row[1]}" for row in selection if row[4] == "true"}
    assert direct == {"com_acme_app@1.0.0", "telemetry_rules@2.1.0"}
    depths = {f"{row[0]}@{row[1]}": int(row[3]) for row in selection}
    assert depths["com_acme_app@1.0.0"] == 0
    assert depths["telemetry_rules@2.1.0"] == 0
    assert depths["bazel_skylib@1.7.1"] >= 2

    module_file = out_dir / "registry" / "bazel-registry" / "modules" / "com_acme_app" / "1.0.0" / "MODULE.bazel"
    text = module_file.read_text()
    assert text.splitlines()[0] == 'module(name = "com_acme_app", version = "1.0.0", compatibility_level = 1)'
    assert 'bazel_dep(name = "rules_java", version = "7.6.0")' in text
    assert 'bazel_dep(name = "lint_tools", version = "0.4.0")' in text
    assert 'darwin_support' not in text

    source = json.loads((out_dir / "registry" / "bazel-registry" / "modules" / "com_acme_app" / "1.0.0" / "source.json").read_text())
    assert set(source) == {"archive", "sha256", "strip_prefix", "patches"}
    assert source["archive"] == "archives/com_acme_app/1.0.0/com_acme_app-1.0.0.tar.gz"
    assert source["patches"] == ["patches/com_acme_app/1.0.0/com_acme_app-1.0.0.patch"]

    manifest = read_tsv(out_dir / "artifact-manifest.tsv")
    assert [row[2] for row in manifest] == sorted(row[2] for row in manifest)
    for digest, size, rel in manifest:
        f = out_dir / "registry" / "bazel-registry" / rel
        assert f.is_file()
        assert sha256_file(f) == digest
        assert f.stat().st_size == int(size)

    profile = parse_profile(input_dir / "profile.env")
    with tarfile.open(out_dir / "registry.tar.gz", "r:gz") as tar:
        all_members = tar.getmembers()
        assert [m.name for m in all_members] == sorted(m.name for m in all_members)
        members = [m for m in all_members if m.isfile()]
        assert {m.name.removeprefix("bazel-registry/") for m in members} == {row[2] for row in manifest}
        for member in all_members:
            assert member.uid == 0
            assert member.gid == 0
            assert member.mtime == int(profile["source_date_epoch"])

    report = json.loads((out_dir / "registry-report.json").read_text())
    assert set(report) == {
        "profile_name",
        "module_count",
        "archive_count",
        "patch_count",
        "registry",
        "registry_sha256",
        "closure_sha256",
    }
    assert report["profile_name"] == "factory-linux"
    assert report["module_count"] == len(order)
    assert report["archive_count"] == len(order)
    assert report["patch_count"] == 2
    assert len(manifest) == report["archive_count"] + report["patch_count"] + (2 * report["module_count"])
    assert report["registry_sha256"] == sha256_file(out_dir / "registry.tar.gz")
    closure = (out_dir / "module-order.txt").read_bytes() + (out_dir / "selection.tsv").read_bytes() + (out_dir / "artifact-manifest.tsv").read_bytes()
    assert report["closure_sha256"] == sha256_bytes(closure)

    hashes = {name: sha256_file(out_dir / name) for name in SUCCESS if (out_dir / name).is_file()}
    (out_dir / "junk.txt").write_text("remove me\n")
    run_gate(input_dir, out_dir)
    assert {p.name for p in out_dir.iterdir()} == SUCCESS
    assert {name: sha256_file(out_dir / name) for name in hashes} == hashes


def test_profile_whitespace_dev_and_platform_filtering(tmp_path):
    input_dir = copy_input(tmp_path)
    replace_profile_value(input_dir, "force_dev_modules", "")
    out_dir = tmp_path / "out"
    run_gate(input_dir, out_dir)
    order = (out_dir / "module-order.txt").read_text().splitlines()
    assert "lint_tools@0.4.0" not in order

    spaced = copy_input(tmp_path / "spaced")
    (spaced / "profile.env").write_text(
        "\n".join(
            [
                " profile_name = factory-linux ",
                "roots = com_acme_app@1.0.0 , telemetry_rules@2.1.0",
                "target_platform = darwin_arm64",
                "bazel_version = 7.4.0",
                "allowed_licenses = Apache-2.0 , MIT , BSD-3-Clause",
                "trusted_attestors = Buildkite , BazelCentral",
                "current_date = 2026-07-01",
                "source_date_epoch = 1782864000",
                "force_dev_modules = lint_tools",
                "yank_allowlist = legacy_crypto@0.9.1",
                "",
            ]
        )
    )
    deps = spaced / "catalog" / "deps.tsv"
    lines = []
    for line in deps.read_text().splitlines():
        if line.startswith("com_acme_app@1.0.0\tlint_tools\t"):
            lines.append(" com_acme_app@1.0.0 \t lint_tools \t 0.4.0 \t true \t all ")
        else:
            lines.append(line)
    deps.write_text("\n".join(lines) + "\n")
    spaced_out = tmp_path / "spaced-out"
    run_gate(spaced, spaced_out)
    spaced_order = (spaced_out / "module-order.txt").read_text().splitlines()
    assert "linux_sandbox@1.2.0" not in spaced_order
    assert "darwin_support@1.0.0" in spaced_order
    assert "lint_tools@0.4.0" in spaced_order


def test_generated_modules_force_mvs_and_selected_version_dependencies(tmp_path):
    input_dir = copy_input(tmp_path)
    append_module(input_dir, "generated_root", "1.0.0", attestor="Buildkite")
    append_module(input_dir, "generated_helper", "1.0.0")
    append_module(input_dir, "generated_helper", "2.0.0")
    append_module(input_dir, "generated_leaf", "1.0.0")
    append_module(input_dir, "numeric_dep", "1.9.9")
    append_module(input_dir, "numeric_dep", "1.10.0")
    append_module(input_dir, "numeric_leaf", "1.0.0")
    append_module(input_dir, "acme-tool.chain", "0.1.0")
    with (input_dir / "catalog" / "deps.tsv").open("a") as f:
        f.write("generated_root@1.0.0\tgenerated_helper\t1.0.0\tfalse\tall\n")
        f.write("telemetry_rules@2.1.0\tgenerated_helper\t2.0.0\tfalse\tall\n")
        f.write("generated_helper@2.0.0\tgenerated_leaf\t1.0.0\tfalse\tall\n")
        f.write("generated_root@1.0.0\tnumeric_dep\t1.9.9\tfalse\tall\n")
        f.write("telemetry_rules@2.1.0\tnumeric_dep\t1.10.0\tfalse\tall\n")
        f.write("numeric_dep@1.10.0\tnumeric_leaf\t1.0.0\tfalse\tall\n")
        f.write("numeric_dep@1.9.9\tghost_rules\t1.0.0\tfalse\tall\n")
        f.write("generated_root@1.0.0\tacme-tool.chain\t0.1.0\tfalse\tall,!darwin_arm64\n")
        f.write("generated_root@1.0.0\tacme-tool.chain\t0.1.0\tfalse\tall,!darwin_arm64\n")
    profile = parse_profile(input_dir / "profile.env")
    replace_profile_value(input_dir, "roots", profile["roots"] + ",generated_root@1.0.0")
    out_dir = tmp_path / "out"
    run_gate(input_dir, out_dir)
    order = (out_dir / "module-order.txt").read_text().splitlines()
    assert "generated_root@1.0.0" in order
    assert "generated_helper@2.0.0" in order
    assert "generated_helper@1.0.0" not in order
    assert "generated_leaf@1.0.0" in order
    assert order.index("generated_leaf@1.0.0") < order.index("generated_helper@2.0.0")
    assert "numeric_dep@1.10.0" in order
    assert "numeric_dep@1.9.9" not in order
    assert "numeric_leaf@1.0.0" in order
    assert order.index("numeric_leaf@1.0.0") < order.index("numeric_dep@1.10.0")
    assert "acme-tool.chain@0.1.0" in order
    assert "ghost_rules@1.0.0" not in order
    selection = {f"{row[0]}@{row[1]}": row for row in read_tsv(out_dir / "selection.tsv")}
    assert selection["numeric_dep@1.10.0"][3] == "1"
    assert selection["numeric_leaf@1.0.0"][3] == "2"
    root_module = (out_dir / "registry" / "bazel-registry" / "modules" / "generated_root" / "1.0.0" / "MODULE.bazel").read_text()
    assert root_module.count('bazel_dep(name = "acme-tool.chain", version = "0.1.0")') == 1
    punct_source = out_dir / "registry" / "bazel-registry" / "modules" / "acme-tool.chain" / "0.1.0" / "source.json"
    assert punct_source.is_file()


def test_yanked_module_requires_allowlist(tmp_path):
    input_dir = copy_input(tmp_path)
    replace_profile_value(input_dir, "yank_allowlist", "")
    out_dir = tmp_path / "out"
    run_gate(input_dir, out_dir, expect_ok=False)
    assert_failure(out_dir, "yanked")


def test_license_and_bazel_version_policy_failures_are_clean(tmp_path):
    license_input = copy_input(tmp_path / "license")
    modules = license_input / "catalog" / "modules.tsv"
    modules.write_text(modules.read_text().replace("zlib\t1.3.1\t1\tMIT\t6.0.0\t-", "zlib\t1.3.1\t1\tGPL-3.0\t6.0.0\t-"))
    license_out = tmp_path / "license-out"
    run_gate(license_input, license_out, expect_ok=False)
    assert_failure(license_out, "policy")

    bazel_input = copy_input(tmp_path / "bazel")
    modules = bazel_input / "catalog" / "modules.tsv"
    modules.write_text(modules.read_text().replace("rules_java\t7.6.0\t1\tApache-2.0\t7.0.0\t-", "rules_java\t7.6.0\t1\tApache-2.0\t8.0.0\t-"))
    bazel_out = tmp_path / "bazel-out"
    run_gate(bazel_input, bazel_out, expect_ok=False)
    assert_failure(bazel_out, "policy")


def test_archive_checksum_and_duplicate_metadata_failures_are_clean(tmp_path):
    patch_input = copy_input(tmp_path / "patch-sort")
    extra_patch = append_patch(
        patch_input,
        "com_acme_app",
        "1.0.0",
        "000-hardening.patch",
        b"extra applied patch\n",
    )
    with (patch_input / "catalog" / "patches.tsv").open("a") as f:
        f.write("com_acme_app\t1.0.0\tpatches/com_acme_app/1.0.0/missing-unapplied.patch\t0\t0\tfalse\n")
    patch_out = tmp_path / "patch-sort-out"
    run_gate(patch_input, patch_out)
    source = json.loads((patch_out / "registry" / "bazel-registry" / "modules" / "com_acme_app" / "1.0.0" / "source.json").read_text())
    expected_patches = [
        f"patches/com_acme_app/1.0.0/{Path(extra_patch).name}",
        "patches/com_acme_app/1.0.0/com_acme_app-1.0.0.patch",
    ]
    assert source["patches"] == expected_patches
    manifest_paths = {row[2] for row in read_tsv(patch_out / "artifact-manifest.tsv")}
    assert "patches/com_acme_app/1.0.0/missing-unapplied.patch" not in manifest_paths
    report = json.loads((patch_out / "registry-report.json").read_text())
    assert report["patch_count"] == 3

    input_dir = copy_input(tmp_path)
    out_dir = tmp_path / "out"
    run_gate(input_dir, out_dir)
    assert (out_dir / "registry.tar.gz").exists()

    row = archive_rows(input_dir)[("rules_java", "7.6.0")]
    with (input_dir / row["path"]).open("a") as f:
        f.write("corrupt\n")
    run_gate(input_dir, out_dir, expect_ok=False)
    assert_failure(out_dir, "artifact")

    dup_input = copy_input(tmp_path / "dup")
    dup_out = tmp_path / "dup-out"
    row = archive_rows(dup_input)[("rules_java", "7.6.0")]
    with (dup_input / "catalog" / "archives.tsv").open("a") as f:
        f.write(f"rules_java\t7.6.0\t{row['path']}\t{row['sha256']}\t{row['size']}\trules_java-7.6.0\n")
    run_gate(dup_input, dup_out, expect_ok=False)
    assert_failure(dup_out, "artifact")


def test_archive_and_patch_path_containment_failures_are_clean(tmp_path):
    path_input = copy_input(tmp_path / "path")
    path_out = tmp_path / "path-out"
    archives = path_input / "catalog" / "archives.tsv"
    archives.write_text(archives.read_text().replace("sources/rules_java/7.6.0/rules_java-7.6.0.tar.gz", "../outside/rules_java.tar.gz"))
    run_gate(path_input, path_out, expect_ok=False)
    assert_failure(path_out, "artifact")

    symlink_input = copy_input(tmp_path / "symlink")
    symlink_out = tmp_path / "symlink-out"
    row = archive_rows(symlink_input)[("rules_java", "7.6.0")]
    archive_path = symlink_input / row["path"]
    outside_archive = tmp_path / "outside-rules_java-7.6.0.tar.gz"
    outside_archive.write_bytes(archive_path.read_bytes())
    archive_path.unlink()
    archive_path.symlink_to(outside_archive)
    run_gate(symlink_input, symlink_out, expect_ok=False)
    assert_failure(symlink_out, "artifact")

    patch_input = copy_input(tmp_path / "patch")
    patch_out = tmp_path / "patch-out"
    patches = patch_input / "catalog" / "patches.tsv"
    patches.write_text(patches.read_text().replace("zlib-1.3.1.patch", "../zlib-1.3.1.patch"))
    run_gate(patch_input, patch_out, expect_ok=False)
    assert_failure(patch_out, "artifact")

    patch_symlink = copy_input(tmp_path / "patch-symlink")
    patch_symlink_out = tmp_path / "patch-symlink-out"
    rel = Path("patches") / "zlib" / "1.3.1" / "zlib-1.3.1.patch"
    patch_path = patch_symlink / rel
    outside_patch = tmp_path / "outside-zlib-1.3.1.patch"
    outside_patch.write_bytes(patch_path.read_bytes())
    patch_path.unlink()
    patch_path.symlink_to(outside_patch)
    run_gate(patch_symlink, patch_symlink_out, expect_ok=False)
    assert_failure(patch_symlink_out, "artifact")


def test_provenance_revoked_expired_and_untrusted_fail(tmp_path):
    mixed = copy_input(tmp_path / "mixed")
    row = archive_rows(mixed)[("rules_java", "7.6.0")]
    prov = mixed / "catalog" / "provenance.tsv"
    lines = []
    for line in prov.read_text().splitlines():
        if line.startswith("rules_java\t7.6.0\t"):
            lines.append(f"rules_java\t7.6.0\t{row['sha256']}\tUnknown\tverified\t2025-01-01")
            lines.append(line)
        else:
            lines.append(line)
    prov.write_text("\n".join(lines) + "\n")
    mixed_out = tmp_path / "mixed-out"
    run_gate(mixed, mixed_out)
    assert (mixed_out / "registry.tar.gz").exists()

    wrong_sha = copy_input(tmp_path / "wrong-sha")
    row = archive_rows(wrong_sha)[("rules_java", "7.6.0")]
    with (wrong_sha / "catalog" / "provenance.tsv").open("a") as f:
        f.write(f"rules_java\t7.6.0\t{'0' * 64}\tBazelCentral\trevoked\t2027-12-31\n")
    wrong_sha_out = tmp_path / "wrong-sha-out"
    run_gate(wrong_sha, wrong_sha_out)
    assert (wrong_sha_out / "registry.tar.gz").exists()

    input_dir = copy_input(tmp_path)
    row = archive_rows(input_dir)[("rules_java", "7.6.0")]
    with (input_dir / "catalog" / "provenance.tsv").open("a") as f:
        f.write(f"rules_java\t7.6.0\t{row['sha256']}\tBazelCentral\trevoked\t2027-12-31\n")
    out_dir = tmp_path / "out"
    run_gate(input_dir, out_dir, expect_ok=False)
    assert_failure(out_dir, "provenance")

    expired = copy_input(tmp_path / "expired")
    prov = expired / "catalog" / "provenance.tsv"
    lines = []
    for line in prov.read_text().splitlines():
        if line.startswith("protobuf\t29.0.0\t"):
            parts = line.split("\t")
            parts[3] = "Unknown"
            parts[5] = "2025-01-01"
            lines.append("\t".join(parts))
        else:
            lines.append(line)
    prov.write_text("\n".join(lines) + "\n")
    expired_out = tmp_path / "expired-out"
    run_gate(expired, expired_out, expect_ok=False)
    assert_failure(expired_out, "provenance")


def test_compatibility_level_conflict_failure_is_clean(tmp_path):
    compat_input = copy_input(tmp_path / "compat")
    with (compat_input / "catalog" / "deps.tsv").open("a") as f:
        f.write("com_acme_app@1.0.0\tcompat_lib\t1.5.0\tfalse\tall\n")
        f.write("telemetry_rules@2.1.0\tcompat_lib\t2.0.0\tfalse\tall\n")
    compat_out = tmp_path / "compat-out"
    run_gate(compat_input, compat_out, expect_ok=False)
    assert_failure(compat_out, "compatibility")


def test_cycle_missing_and_duplicate_module_failures_are_clean(tmp_path):
    cycle_input = copy_input(tmp_path / "cycle")
    with (cycle_input / "catalog" / "deps.tsv").open("a") as f:
        f.write("zlib@1.3.1\tcom_acme_app\t1.0.0\tfalse\tall\n")
    cycle_out = tmp_path / "cycle-out"
    run_gate(cycle_input, cycle_out, expect_ok=False)
    assert_failure(cycle_out, "cycle")

    missing_input = copy_input(tmp_path / "missing")
    with (missing_input / "catalog" / "deps.tsv").open("a") as f:
        f.write("com_acme_app@1.0.0\tghost_rules\t1.0.0\tfalse\tall\n")
    missing_out = tmp_path / "missing-out"
    run_gate(missing_input, missing_out, expect_ok=False)
    assert_failure(missing_out, "missing")

    dup_module = copy_input(tmp_path / "dup-module")
    with (dup_module / "catalog" / "modules.tsv").open("a") as f:
        f.write("rules_java\t7.6.0\t1\tApache-2.0\t7.0.0\t-\n")
    dup_module_out = tmp_path / "dup-module-out"
    run_gate(dup_module, dup_module_out, expect_ok=False)
    assert_failure(dup_module_out, "policy")


def test_command_remains_bash_only_and_offline_static():
    script = SCRIPT.read_text()
    assert script.startswith("#!/usr/bin/env bash")
    lowered = script.lower()
    forbidden = [
        r"python[0-9.]*",
        r"ruby",
        r"perl",
        r"node",
        r"go",
        r"java",
        r"bazel",
        r"npm",
        r"pip[0-9.]*",
        r"apt-get",
        r"curl",
        r"wget",
        r"docker",
        r"podman",
    ]
    for pattern in forbidden:
        assert not re.search(rf"(^|[^a-z0-9_./-]){pattern}(\s|[;|&<>()]|\Z)", lowered)
