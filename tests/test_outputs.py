import hashlib
import json
import os
import re
import sqlite3
import subprocess
import time
import tomllib
import urllib.request
from pathlib import Path


APP = Path("/app")
EXPECTED_BASELINE = "125bcc456efaa89ff675b0360e0168b763a79060bff18a5bfff3a0041191757d"
TARGETS = {
    "crossbeam-channel": ("0.5.14", "0.5.15", "RUSTSEC-2025-0024", 1, "1.60"),
    "serde-json-wasm": ("1.0.0", "1.0.1", "RUSTSEC-2024-0012", 0, ""),
    "time": ("0.3.36", "0.3.47", "RUSTSEC-2026-0009", 0, "1.88.0"),
}


def run(command, *, timeout=180, env=None):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(command, cwd=APP, text=True, capture_output=True, timeout=timeout, env=merged)


def tree_digest():
    digest = hashlib.sha256()
    for root_name in ["crates", "docs", "sql", "tooling"]:
        root = APP / root_name
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = path.relative_to(APP).as_posix().encode()
            digest.update(relative)
            digest.update(b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def lock_data():
    return tomllib.loads((APP / "Cargo.lock").read_text(encoding="utf-8"))


def locked_versions(name):
    return [item["version"] for item in lock_data()["package"] if item["name"] == name]


def fetch_json(url):
    last = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "terminus-release-policy/1"})
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.load(response)
        except Exception as error:
            last = error
            time.sleep(1 + attempt)
    raise last


def sparse_path(name):
    if len(name) == 1:
        return f"1/{name}"
    if len(name) == 2:
        return f"2/{name}"
    if len(name) == 3:
        return f"3/{name[0]}/{name}"
    return f"{name[:2]}/{name[2:4]}/{name}"


def fetch_index_row(name, version):
    url = f"https://index.crates.io/{sparse_path(name)}"
    last = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "terminus-release-policy/1"})
            with urllib.request.urlopen(request, timeout=20) as response:
                rows = [json.loads(line) for line in response.read().decode().splitlines() if line]
            return next(row for row in rows if row["vers"] == version)
        except Exception as error:
            last = error
            time.sleep(1 + attempt)
    raise last


def test_release_baseline_source_and_policy_inputs_are_unchanged():
    """The dependency operation leaves every source, policy, SQL, and pinned tooling byte at its baseline value."""
    assert tree_digest() == EXPECTED_BASELINE


def test_only_authorized_release_paths_exist():
    """The handoff adds policy and evidence files without a wrapper command, executable, patch crate, or stray top-level file."""
    allowed = {
        ".cargo", ".dockerignore", "Cargo.lock", "Cargo.toml", "Dockerfile", "LICENSE",
        "crates", "deny.toml", "docs", "release", "sql", "target", "tooling", "vendor",
    }
    assert {path.name for path in APP.iterdir()} <= allowed
    assert not (APP / "bin").exists()
    assert {path.name for path in (APP / "release").iterdir()} == {"dependency-ledger.sqlite", "reconciliation.md"}
    assert not list(APP.glob("*.sh"))
    assert not list((APP / "crates").rglob("*.sh"))


def test_workspace_manifest_has_exact_safe_pins_and_minimum_msrv():
    """The workspace policy carries the three safe exact pins, the coupled Serde pin, and only the required MSRV increase."""
    root = tomllib.loads((APP / "Cargo.toml").read_text(encoding="utf-8"))
    assert root["workspace"]["package"]["rust-version"] == "1.88"
    dependencies = root["workspace"]["dependencies"]
    assert dependencies["crossbeam-channel"] == "=0.5.15"
    assert dependencies["serde-json-wasm"] == "=1.0.1"
    assert dependencies["time"]["version"] == "=0.3.47"
    assert dependencies["serde"]["version"] == "=1.0.220"
    assert "patch" not in root
    for name, value in dependencies.items():
        if isinstance(value, dict) and "path" in value:
            assert value["version"] == "=0.7.0", name


def test_lockfile_has_one_registry_release_per_quarantined_crate():
    """Cargo's format-4 lock contains one selected target version with registry source and checksum and no git package."""
    lock = lock_data()
    assert lock["version"] == 4
    for name, (_old, selected, _advisory, _yanked, _rust) in TARGETS.items():
        assert locked_versions(name) == [selected]
    for item in lock["package"]:
        source = item.get("source")
        if source is not None:
            assert source == "registry+https://github.com/rust-lang/crates.io-index"
            assert re.fullmatch(r"[0-9a-f]{64}", item["checksum"])


def test_final_source_replacement_is_exact_and_vendor_replays_metadata():
    """The exact vendor source policy supports locked offline metadata with the full eight-member workspace graph."""
    expected = (
        '[source.crates-io]\nreplace-with = "vendored-sources"\n\n'
        '[source.vendored-sources]\ndirectory = "vendor"\n\n'
        '[net]\ngit-fetch-with-cli = true\n'
    )
    assert (APP / ".cargo/config.toml").read_text(encoding="utf-8") == expected
    result = run(
        ["cargo", "metadata", "--locked", "--offline", "--format-version", "1"],
        env={"CARGO_NET_OFFLINE": "true"},
    )
    assert result.returncode == 0, result.stderr
    metadata = json.loads(result.stdout)
    members = [package for package in metadata["packages"] if package["source"] is None]
    assert len(members) == 8


def test_workspace_build_and_tests_pass_with_network_disabled():
    """Stock Cargo compiles and tests every existing workspace target using only the locked vendor graph."""
    result = run(
        ["cargo", "test", "--workspace", "--all-targets", "--locked", "--offline"],
        env={"CARGO_NET_OFFLINE": "true"},
    )
    assert result.returncode == 0, result.stderr
    assert "test result: ok" in result.stdout or "test result: ok" in result.stderr


def test_vendor_packages_carry_cargo_checksum_manifests():
    """Every vendored registry directory has Cargo's checksum manifest and each selected target matches its locked package name."""
    vendor = APP / "vendor"
    directories = [path for path in vendor.iterdir() if path.is_dir()]
    assert len(directories) >= 40
    for directory in directories:
        checksum = directory / ".cargo-checksum.json"
        assert checksum.is_file(), directory.name
        parsed = json.loads(checksum.read_text(encoding="utf-8"))
        assert "files" in parsed and "package" in parsed
    for name in TARGETS:
        manifest = tomllib.loads((vendor / name / "Cargo.toml").read_text(encoding="utf-8"))
        assert manifest["package"]["version"] == TARGETS[name][1]


def test_deny_policy_has_no_suppression_and_matches_release_rules():
    """cargo-deny checks every feature without advisory ignores, skips, wildcard pins, or untrusted sources."""
    deny = tomllib.loads((APP / "deny.toml").read_text(encoding="utf-8"))
    assert deny["graph"]["all-features"] is True
    assert set(deny["advisories"]) == {"ignore", "git-fetch-with-cli"}
    assert deny["advisories"]["ignore"] == []
    assert deny["advisories"]["git-fetch-with-cli"] is True
    assert deny["licenses"]["confidence-threshold"] == 0.8
    assert set(deny["licenses"]["allow"]) == {
        "Apache-2.0", "Apache-2.0 WITH LLVM-exception", "BSD-3-Clause", "ISC", "MIT", "Unicode-3.0", "Zlib"
    }
    assert deny["bans"]["multiple-versions"] == "warn"
    assert deny["bans"]["wildcards"] == "deny"
    assert deny["bans"]["skip"] == deny["bans"]["skip-tree"] == []
    banned = {item["crate"] for item in deny["bans"]["deny"]}
    assert banned == {"crossbeam-channel@=0.5.14", "serde-json-wasm@=1.0.0", "time@=0.3.36"}
    assert deny["sources"]["unknown-registry"] == "deny"
    assert deny["sources"]["unknown-git"] == "deny"
    assert deny["sources"]["allow-registry"] == ["https://github.com/rust-lang/crates.io-index"]
    assert deny["sources"]["allow-git"] == []


def test_cargo_deny_local_checks_pass_without_fetching():
    """The final graph passes cargo-deny bans, licenses, and sources in offline mode with all features active."""
    result = run([
        "cargo", "deny", "--offline", "--all-features", "check", "bans", "licenses", "sources"
    ])
    assert result.returncode == 0, result.stderr
    combined = result.stdout + result.stderr
    assert "bans ok" in combined and "licenses ok" in combined and "sources ok" in combined


def test_release_ledger_schema_identity_and_dependency_rows():
    """SQLite binds one release run and the three specified dependency changes to the exact final lockfile hash."""
    database = APP / "release/dependency-ledger.sqlite"
    connection = sqlite3.connect(database)
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert connection.execute("SELECT count(*) FROM release_run").fetchone()[0] == 1
    run_row = connection.execute(
        "SELECT run_id,resolved_at,rust_version,cargo_version,cargo_audit_version,cargo_deny_version,"
        "cargo_lock_sha256,rustsec_commit,offline_replay,source_unchanged FROM release_run"
    ).fetchone()
    lock_hash = hashlib.sha256((APP / "Cargo.lock").read_bytes()).hexdigest()
    assert run_row[0] == lock_hash[:20]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", run_row[1])
    assert run_row[2].startswith("rustc 1.89.")
    assert run_row[3].startswith("cargo 1.89.")
    assert run_row[4] == "cargo-audit-audit 0.22.2"
    assert run_row[5] == "cargo-deny 0.19.4"
    assert run_row[6] == lock_hash
    assert re.fullmatch(r"[0-9a-f]{40}", run_row[7])
    assert run_row[8:] == (1, 1)
    rows = connection.execute(
        "SELECT name,from_version,to_version,advisory_id,yanked_before,target_rust_version "
        "FROM dependency_change ORDER BY name"
    ).fetchall()
    assert rows == [(name, *TARGETS[name]) for name in sorted(TARGETS)]
    connection.close()


def test_ledger_contains_the_four_exact_passing_policy_checks():
    """The release ledger records each required stock-tool check once with its exact replay command and pass status."""
    connection = sqlite3.connect(APP / "release/dependency-ledger.sqlite")
    rows = connection.execute("SELECT tool,command,status FROM policy_check ORDER BY tool").fetchall()
    connection.close()
    assert rows == [
        ("cargo-audit", "cargo audit --json", "pass"),
        ("cargo-deny", "cargo deny --all-features check advisories bans licenses sources", "pass"),
        ("cargo-metadata", "cargo metadata --locked --offline --format-version 1", "pass"),
        ("cargo-test", "cargo test --workspace --all-targets --locked --offline", "pass"),
    ]


def test_handoff_note_matches_lock_ledger_tools_and_changes():
    """The handoff note matches SQLite and semantically confirms that the source baseline stayed unchanged."""
    note = (APP / "release/reconciliation.md").read_text(encoding="utf-8")
    connection = sqlite3.connect(APP / "release/dependency-ledger.sqlite")
    run_row = connection.execute(
        "SELECT resolved_at,rust_version,cargo_version,cargo_audit_version,cargo_deny_version,cargo_lock_sha256,rustsec_commit "
        "FROM release_run"
    ).fetchone()
    connection.close()
    for value in run_row:
        assert value in note
    for name, values in TARGETS.items():
        assert name in note and values[0] in note and values[1] in note and values[2] in note
    for command in [
        "cargo metadata --locked --offline --format-version 1",
        "cargo test --workspace --all-targets --locked --offline",
        "cargo audit --json",
        "cargo deny --all-features check advisories bans licenses sources",
    ]:
        assert command in note
    note_sentences = re.split(r"(?:[.!?](?:\s+|$)|\n+)", note.lower())
    unchanged_wording = re.compile(
        r"\b(?:unchanged|unmodified|unaltered|intact|preserved)\b"
        r"|\b(?:not|no)\b.{0,80}\b(?:change|changed|changes|modify|modified|"
        r"modifications|alter|altered|alterations)\b"
    )
    assert any(unchanged_wording.search(sentence) for sentence in note_sentences)
    assert "\u2014" not in note


def test_live_frozen_advisory_boundaries_and_selected_index_rows():
    """Frozen RustSec records retain their fixed boundaries and the selected live index rows remain published, non-yanked, and toolchain-compatible."""
    fixed = {
        "RUSTSEC-2024-0012": "1.0.1",
        "RUSTSEC-2025-0024": "0.5.15",
        "RUSTSEC-2026-0009": "0.3.47",
    }
    for advisory_id, boundary in fixed.items():
        record = fetch_json(f"https://api.osv.dev/v1/vulns/{advisory_id}")
        assert record["id"] == advisory_id
        events = [
            event for affected in record["affected"] for item in affected.get("ranges", [])
            if item["type"] == "SEMVER" for event in item["events"]
        ]
        assert {event.get("fixed") for event in events} >= {boundary}
    for name, (_old, selected, _advisory, _yanked, _rust) in TARGETS.items():
        row = fetch_index_row(name, selected)
        assert row["name"] == name and row["vers"] == selected and row["yanked"] is False
        required = row.get("rust_version")
        if required:
            assert tuple(map(int, required.split("."))) <= (1, 89, 0)


def test_live_stock_policy_tools_clear_the_current_database():
    """cargo-audit and cargo-deny both clear the final graph against the current default RustSec database without ignores."""
    audit = run(["cargo", "audit", "--json"], timeout=180)
    assert audit.returncode == 0, audit.stderr
    report = json.loads(audit.stdout)
    assert report["vulnerabilities"]["found"] is False
    assert report["vulnerabilities"]["count"] == 0
    deny = run([
        "cargo", "deny", "--all-features", "check", "advisories", "bans", "licenses", "sources"
    ], timeout=180)
    assert deny.returncode == 0, deny.stderr
    assert "advisories ok" in deny.stdout + deny.stderr
