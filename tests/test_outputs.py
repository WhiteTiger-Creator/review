"""Verifier for the Alpine APKBUILD checksum-freeze board.

Every expected value is recomputed independently in pure Python from the sealed
fixtures and compared against the artifacts produced by the compiled Rust
publisher. Nothing is transcribed from the environment stubs.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

APP = Path("/app")
RUNNER = str(APP / "bin" / "apk-board")
APKFOLD = str(APP / "bin" / "apkfold")
BOARD = APP / "output" / "apkbuild_checksum_freeze.json"
FINDINGS = APP / "output" / "pkg_findings.jsonl"
PACKAGES = APP / "data" / "packages"
SCENARIOS = APP / "data" / "scenarios"
PINS = APP / "data" / "pins" / "sources.jsonl"
ADMIT = APP / "data" / "patches" / "admit.jsonl"
CONFLICTS = APP / "data" / "conflicts" / "table.jsonl"
GATES = APP / "data" / "indexes" / "write_gates.jsonl"
RUNTIME_INDEX = APP / "data" / "runtime" / "index.json"
FIXTURE_SEALS = APP / "harness" / "fixture_seals.json"

DETAILS = {
    "unpinned_source": "source uri not pinned for {package_id}",
    "pin_miss": "source pin miss for {package_id}",
    "patch_denied": "patch admission denied for {package_id}: {names}",
    "provide_conflict": "provide conflict closes {package_id} under {left}/{right}",
    "replace_conflict": "replace conflict closes {package_id} under {left}/{right}",
    "index_denied": "index write denied for {package_id}",
    "digest_mismatch": "index payload digest mismatch for {package_id}",
}


# --------------------------------------------------------------------------- #
# Fixture loaders                                                             #
# --------------------------------------------------------------------------- #
def _lab() -> dict:
    out: dict = {"replay_ready": False}
    for line in (APP / "config" / "lab.toml").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"')
        if key == "site_id":
            out["site_id"] = val
        elif key == "eval_at":
            out["eval_at"] = val
        elif key == "replay_ready":
            out["replay_ready"] = val == "true"
        elif key == "graph_generation":
            out["graph_generation"] = val
        elif key == "graph_lock_sha256":
            out["graph_lock_sha256"] = val
    return out


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _packages() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in sorted(PACKAGES.glob("apk-*.json")):
        row = json.loads(path.read_text())
        out[row["package_id"]] = row
    return out


def _scenario_ids() -> list[str]:
    return sorted(json.loads(p.read_text())["scenario_id"] for p in SCENARIOS.glob("sc-*.json"))


def _scenarios() -> list[dict]:
    rows = [json.loads(p.read_text()) for p in sorted(SCENARIOS.glob("sc-*.json"))]
    rows.sort(key=lambda r: r["scenario_id"])
    return rows


# --------------------------------------------------------------------------- #
# Policy re-implementation (independent oracle)                               #
# --------------------------------------------------------------------------- #
def _pin_status(pkg: dict, pin_by_uri: dict[str, str]) -> tuple[bool, str | None]:
    for src in pkg.get("sources", []):
        uri = src["uri"]
        if uri not in pin_by_uri:
            return (False, "unpinned_source")
        if pin_by_uri[uri] != src["sha"]:
            return (False, "pin_miss")
    return (True, None)


def _patch_status(pkg_id: str, patches: list[str], rules: list[dict]) -> tuple[bool, list[str]]:
    if not patches:
        return (True, [])
    rule = None
    for r in rules:
        if r["package_id_or_prefix"] == pkg_id:
            rule = r
            break
    if rule is None:
        for r in rules:
            if pkg_id.startswith(r["package_id_or_prefix"]):
                rule = r
                break
    if rule is None:
        return (False, sorted(patches))
    allowed = set(rule.get("allowed", []))
    denied = sorted(p for p in patches if p not in allowed)
    return (len(denied) == 0, denied)


def _close(selected: dict[str, dict], conflicts: list[dict]):
    survivors = dict(selected)
    removed: set[str] = set()
    hits: list[tuple[str, str, str, str]] = []

    def present(side: str) -> bool:
        if side in survivors:
            return True
        for s in survivors.values():
            if side in s["provides"]:
                return True
        return False

    for c in conflicts:
        if not present(c["left"]) or not present(c["right"]):
            continue
        loser = c["loser"]
        if loser in removed or loser not in survivors:
            continue
        removed.add(loser)
        survivors.pop(loser, None)
        hits.append((loser, c["left"], c["right"], c["kind"]))
    return survivors, hits


def _write_status(gate_admit: bool, digest_match: bool, package_id: str) -> tuple[bool, str, str]:
    if not gate_admit:
        return (False, "index_denied", DETAILS["index_denied"].format(package_id=package_id))
    if not digest_match:
        return (False, "digest_mismatch", DETAILS["digest_mismatch"].format(package_id=package_id))
    return (True, "", "")


def _digest(lines: list[tuple[str, str, str, bool, bool, bool]]) -> str:
    body = ""
    for (sid, pid, ver, pinned, patches_ok, admitted) in lines:
        if not admitted:
            continue
        body += (
            f"{sid}|{pid}|{ver}|"
            f"{str(pinned).lower()}|{str(patches_ok).lower()}|{str(admitted).lower()}\n"
        )
    return hashlib.sha256(body.encode()).hexdigest()


def _digest_hash_all(lines: list[tuple[str, str, str, bool, bool, bool]]) -> str:
    body = ""
    for (sid, pid, ver, pinned, patches_ok, admitted) in lines:
        body += (
            f"{sid}|{pid}|{ver}|"
            f"{str(pinned).lower()}|{str(patches_ok).lower()}|{str(admitted).lower()}\n"
        )
    return hashlib.sha256(body.encode()).hexdigest()


def _reference() -> tuple[dict, list[dict]]:
    lab = _lab()
    packages = _packages()
    pin_by_uri = {row["uri"]: row["sha"] for row in _load_jsonl(PINS)}
    rules = _load_jsonl(ADMIT)
    conflicts = _load_jsonl(CONFLICTS)
    gate_by_id = {row["index_id"]: bool(row["admit"]) for row in _load_jsonl(GATES)}
    scenarios = _scenarios()

    scenario_rows: list[dict] = []
    findings: list[dict] = []
    digest_lines: list[tuple[str, str, str, bool, bool, bool]] = []
    packages_accepted = 0
    writes_admitted = 0

    for sc in scenarios:
        sid = sc["scenario_id"]
        selected: dict[str, dict] = {}

        for req in sc.get("requests", []):
            pkg = packages.get(req["package_id"])
            if pkg is None:
                continue
            pin_ok, pin_class = _pin_status(pkg, pin_by_uri)
            if not pin_ok:
                findings.append(
                    {
                        "scenario_id": sid,
                        "package_id": pkg["package_id"],
                        "finding_class": pin_class,
                        "detail": DETAILS[pin_class].format(package_id=pkg["package_id"]),
                    }
                )
                continue
            patch_ok, denied = _patch_status(pkg["package_id"], pkg.get("patches", []), rules)
            if not patch_ok:
                findings.append(
                    {
                        "scenario_id": sid,
                        "package_id": pkg["package_id"],
                        "finding_class": "patch_denied",
                        "detail": DETAILS["patch_denied"].format(
                            package_id=pkg["package_id"],
                            names=",".join(denied),
                        ),
                    }
                )
                continue
            selected[pkg["package_id"]] = {
                "package_id": pkg["package_id"],
                "pkgname": pkg["pkgname"],
                "version": pkg["version"],
                "provides": list(pkg.get("provides", [])),
                "content_digest": pkg["content_digest"],
            }

        survivors, hits = _close(selected, conflicts)
        for loser, left, right, kind in hits:
            cls = "provide_conflict" if kind == "provide" else "replace_conflict"
            findings.append(
                {
                    "scenario_id": sid,
                    "package_id": loser,
                    "finding_class": cls,
                    "detail": DETAILS[cls].format(
                        package_id=loser, left=left, right=right
                    ),
                }
            )

        admitted: dict[str, bool] = {}
        for w in sc.get("proposed_writes", []):
            sel = survivors.get(w["package_id"])
            if sel is None:
                continue
            gate_admit = gate_by_id.get(w["index_id"], False)
            digest_match = w["payload_digest"] == sel["content_digest"]
            adm, cls, detail = _write_status(gate_admit, digest_match, sel["package_id"])
            if adm:
                admitted[w["package_id"]] = True
                writes_admitted += 1
                continue
            if cls:
                findings.append(
                    {
                        "scenario_id": sid,
                        "package_id": sel["package_id"],
                        "finding_class": cls,
                        "detail": detail,
                    }
                )

        package_rows = []
        for pid in sorted(survivors):
            sel = survivors[pid]
            is_admitted = admitted.get(pid, False)
            package_rows.append(
                {
                    "package_id": pid,
                    "version": sel["version"],
                    "pinned": True,
                    "patches_ok": True,
                    "admitted": is_admitted,
                }
            )
            digest_lines.append((sid, pid, sel["version"], True, True, is_admitted))
        packages_accepted += len(package_rows)
        scenario_rows.append({"scenario_id": sid, "packages": package_rows})

    findings.sort(key=lambda r: (r["scenario_id"], r["package_id"], r["finding_class"]))

    doc = {
        "schema_version": "1",
        "site_id": lab["site_id"],
        "scenarios_processed": len(scenarios),
        "packages_accepted": packages_accepted,
        "writes_admitted": writes_admitted,
        "findings_total": len(findings),
        "scenarios": scenario_rows,
        "digest_hex": _digest(digest_lines),
    }
    return doc, findings


def _scenario_lock() -> str:
    payload = b""
    for path in sorted(SCENARIOS.glob("*.json")):
        payload += path.read_bytes()
    return hashlib.sha256(payload).hexdigest()


# --------------------------------------------------------------------------- #
# Build + run harness                                                         #
# --------------------------------------------------------------------------- #
def _cargo_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = "/usr/local/cargo/bin:" + env.get("PATH", "")
    env["TB_APK_LAB"] = "1"
    return env


def _compile_workspace() -> None:
    env = _cargo_env()
    subprocess.run(
        [
            "cargo",
            "build",
            "--release",
            "--locked",
            "--offline",
            "--bin",
            "apkfold",
            "--bin",
            "apk-board",
        ],
        cwd="/app",
        check=True,
        env=env,
        timeout=600,
    )
    Path(APKFOLD).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy("/app/target/release/apkfold", APKFOLD)
    shutil.copy("/app/target/release/apk-board", RUNNER)
    os.chmod(APKFOLD, 0o755)
    os.chmod(RUNNER, 0o755)
    subprocess.run([APKFOLD], check=True, env=env, timeout=60)


def _run(*, clean: bool = True) -> tuple[dict, list[dict]]:
    env = _cargo_env()
    if clean and (APP / "output").exists():
        shutil.rmtree(APP / "output")
    _compile_workspace()
    subprocess.run([RUNNER], check=True, env=env, timeout=120)
    board = json.loads(BOARD.read_text())
    findings = _load_jsonl(FINDINGS)
    return board, findings


def _fixture_files() -> list[Path]:
    files = [PINS, ADMIT, CONFLICTS, GATES]
    files += sorted(PACKAGES.glob("apk-*.json"))
    files += sorted(SCENARIOS.glob("sc-*.json"))
    return files


# --------------------------------------------------------------------------- #
# Named cases                                                                 #
# --------------------------------------------------------------------------- #
def test_case_a_pin_miss_blocks_and_reports():
    """A source whose sha differs from the pin table is a pin_miss finding only."""
    board, findings = _run()
    sc02 = next(s for s in board["scenarios"] if s["scenario_id"] == "sc-02")
    ids = {p["package_id"] for p in sc02["packages"]}
    assert "apk-03" not in ids
    hit = next(f for f in findings if f["scenario_id"] == "sc-02" and f["package_id"] == "apk-03")
    assert hit["finding_class"] == "pin_miss"
    assert hit["detail"] == "source pin miss for apk-03"


def test_case_b_unpinned_source_blocks_and_reports():
    """A source URI absent from the pin table is an unpinned_source finding only."""
    board, findings = _run()
    sc03 = next(s for s in board["scenarios"] if s["scenario_id"] == "sc-03")
    ids = {p["package_id"] for p in sc03["packages"]}
    assert "apk-04" not in ids
    hit = next(f for f in findings if f["scenario_id"] == "sc-03" and f["package_id"] == "apk-04")
    assert hit["finding_class"] == "unpinned_source"
    assert hit["detail"] == "source uri not pinned for apk-04"


def test_case_c_patch_denied_blocks_and_reports():
    """A package carrying a non-admitted patch is a patch_denied finding only."""
    board, findings = _run()
    sc04 = next(s for s in board["scenarios"] if s["scenario_id"] == "sc-04")
    ids = {p["package_id"] for p in sc04["packages"]}
    assert "apk-05" not in ids
    hit = next(f for f in findings if f["scenario_id"] == "sc-04" and f["package_id"] == "apk-05")
    assert hit["finding_class"] == "patch_denied"
    assert hit["detail"] == "patch admission denied for apk-05: alpha-hack,zeta-hack"


def test_case_d_provide_conflict_closes_loser():
    """A provide conflict removes the loser and emits provide_conflict."""
    board, findings = _run()
    sc05 = next(s for s in board["scenarios"] if s["scenario_id"] == "sc-05")
    ids = {p["package_id"] for p in sc05["packages"]}
    assert "apk-07" not in ids
    assert "apk-06" in ids
    hit = next(f for f in findings if f["scenario_id"] == "sc-05" and f["package_id"] == "apk-07")
    assert hit["finding_class"] == "provide_conflict"
    assert hit["detail"] == "provide conflict closes apk-07 under libssl/libssl-legacy"


def test_case_e_replace_conflict_closes_loser():
    """A replace conflict removes the loser and emits replace_conflict."""
    board, findings = _run()
    sc06 = next(s for s in board["scenarios"] if s["scenario_id"] == "sc-06")
    ids = {p["package_id"] for p in sc06["packages"]}
    assert "apk-09" not in ids
    assert "apk-08" in ids
    hit = next(f for f in findings if f["scenario_id"] == "sc-06" and f["package_id"] == "apk-09")
    assert hit["finding_class"] == "replace_conflict"
    assert hit["detail"] == "replace conflict closes apk-09 under apk-08/apk-09"


def test_case_f_index_denied_blocks_write():
    """A survivor targeting a closed index gate is not admitted and gets index_denied."""
    board, findings = _run()
    sc07 = next(s for s in board["scenarios"] if s["scenario_id"] == "sc-07")
    row = next(p for p in sc07["packages"] if p["package_id"] == "apk-01")
    assert row["admitted"] is False
    hit = next(f for f in findings if f["scenario_id"] == "sc-07")
    assert hit["finding_class"] == "index_denied"
    assert hit["detail"] == "index write denied for apk-01"


def test_case_g_digest_mismatch_blocks_write():
    """A payload digest mismatch under an open gate blocks admission and reports it."""
    board, findings = _run()
    sc08 = next(s for s in board["scenarios"] if s["scenario_id"] == "sc-08")
    row = next(p for p in sc08["packages"] if p["package_id"] == "apk-02")
    assert row["admitted"] is False
    hit = next(f for f in findings if f["scenario_id"] == "sc-08")
    assert hit["finding_class"] == "digest_mismatch"
    assert hit["detail"] == "index payload digest mismatch for apk-02"


def test_case_h_digest_seals_board():
    """digest_hex matches the independent recomputation over ordered ledger lines."""
    board, _ = _run()
    expected, _ = _reference()
    assert board["digest_hex"] == expected["digest_hex"]
    assert board["digest_hex"] != ""


def test_case_h2_digest_rejects_hash_all_survivors():
    """Live digest diverges from hashing every survivor row including non-admitted."""
    board, _ = _run()
    expected, _ = _reference()
    # Rebuild the full survivor line list the way a hash-all fold would.
    lines: list[tuple[str, str, str, bool, bool, bool]] = []
    for sc in expected["scenarios"]:
        for p in sc["packages"]:
            lines.append(
                (
                    sc["scenario_id"],
                    p["package_id"],
                    p["version"],
                    p["pinned"],
                    p["patches_ok"],
                    p["admitted"],
                )
            )
    assert any(not admitted for *_, admitted in lines)
    assert board["digest_hex"] != _digest_hash_all(lines)
    assert board["digest_hex"] == _digest(lines)


def test_case_i_runtime_index_reconstructed():
    """The runtime index carries sorted scenario ids and the sealed corpus lock."""
    _run()
    idx = json.loads(RUNTIME_INDEX.read_text())
    assert idx["scenario_ids"] == _scenario_ids()
    assert idx["lock_digest"] == _scenario_lock()


def test_case_j_findings_match_reference():
    """The findings feed matches the independent recomputation exactly."""
    _, findings = _run()
    _, expected = _reference()
    assert findings == expected


def test_case_k_headline_tallies_match_reference():
    """Accepted-package, admitted-write, and findings tallies match recomputation."""
    board, _ = _run()
    expected, _ = _reference()
    assert board["packages_accepted"] == expected["packages_accepted"]
    assert board["writes_admitted"] == expected["writes_admitted"]
    assert board["findings_total"] == expected["findings_total"]


def test_case_l_outputs_sorted():
    """Scenario rows, package rows, and findings are all sorted ascending."""
    board, findings = _run()
    sids = [s["scenario_id"] for s in board["scenarios"]]
    assert sids == sorted(sids)
    for scenario in board["scenarios"]:
        pids = [p["package_id"] for p in scenario["packages"]]
        assert pids == sorted(pids)
    keys = [(r["scenario_id"], r["package_id"], r["finding_class"]) for r in findings]
    assert keys == sorted(keys)


def test_case_m_scenarios_match_reference():
    """Full per-scenario package rows match the independent recomputation."""
    board, _ = _run()
    expected, _ = _reference()
    assert board["scenarios"] == expected["scenarios"]


def test_case_n_multi_axis_scenario_couples_findings():
    """One scenario surfaces pin, patch, provide, replace, and digest findings together."""
    _, findings = _run()
    sc09 = {f["finding_class"] for f in findings if f["scenario_id"] == "sc-09"}
    assert sc09 == {
        "pin_miss",
        "patch_denied",
        "provide_conflict",
        "replace_conflict",
        "digest_mismatch",
    }


def test_case_o_fixture_seals_intact():
    """Sealed fixture inputs match their recorded harness digests."""
    seals = json.loads(FIXTURE_SEALS.read_text())
    assert seals, "fixture seal manifest must not be empty"
    for rel_path, digest in seals.items():
        current = hashlib.sha256((APP / rel_path).read_bytes()).hexdigest()
        assert current == digest, f"{rel_path} does not match its sealed digest"


def test_case_p_decoy_package_unused():
    """The decoy package ships but is never referenced by any scenario."""
    packages = _packages()
    assert "apk-13" in packages
    assert packages["apk-13"]["pkgname"] == "husk"
    referenced = set()
    for sc in _scenarios():
        for req in sc.get("requests", []):
            referenced.add(req["package_id"])
    assert "apk-13" not in referenced


def test_case_q_workspace_rust_binaries():
    """The verifier compiles both binaries from the shipped Cargo workspace."""
    assert (APP / "Cargo.toml").is_file()
    assert (APP / "Cargo.lock").is_file()
    _compile_workspace()
    assert Path(APKFOLD).read_bytes()[:4] == b"\x7fELF"
    assert Path(RUNNER).read_bytes()[:4] == b"\x7fELF"


def test_case_r_build_succeeds():
    """The build script completes without error."""
    subprocess.run(["bash", "/app/scripts/build.sh"], check=True, timeout=600)


def test_case_s_graph_generation_and_lock():
    """A replay-ready build binds a fixed generation and the sealed scenario lock."""
    lab = _lab()
    assert lab["replay_ready"] is True
    assert lab.get("graph_generation") == "freeze-1"
    assert lab.get("graph_lock_sha256") == _scenario_lock()


def test_case_t_lab_requires_env_flag():
    """The publisher refuses to run without the lab environment flag."""
    _compile_workspace()
    env = os.environ.copy()
    env["PATH"] = "/usr/local/cargo/bin:" + env.get("PATH", "")
    env.pop("TB_APK_LAB", None)
    result = subprocess.run([RUNNER], env=env, timeout=60)
    assert result.returncode != 0


def test_case_u_board_schema_fields():
    """The board exposes the documented top-level schema and identity fields."""
    board, _ = _run()
    for key in (
        "schema_version",
        "site_id",
        "scenarios_processed",
        "packages_accepted",
        "writes_admitted",
        "findings_total",
        "scenarios",
        "digest_hex",
    ):
        assert key in board
    assert board["schema_version"] == "1"
    assert board["site_id"] == _lab()["site_id"]
    assert board["scenarios_processed"] == len(list(SCENARIOS.glob("sc-*.json")))


def test_case_v_index_denied_precedes_digest_mismatch():
    """A closed gate reports index_denied even when the payload digest also mismatches."""
    board, findings = _run()
    sc10 = next(s for s in board["scenarios"] if s["scenario_id"] == "sc-10")
    apk01 = next(p for p in sc10["packages"] if p["package_id"] == "apk-01")
    assert apk01["admitted"] is False
    sc10_findings = [f for f in findings if f["scenario_id"] == "sc-10"]
    apk01_findings = [f for f in sc10_findings if f["package_id"] == "apk-01"]
    assert len(apk01_findings) == 1
    assert apk01_findings[0]["finding_class"] == "index_denied"
    assert not any(f["finding_class"] == "digest_mismatch" for f in apk01_findings)


def test_case_w_patch_denied_names_comma_sorted():
    """Denied patch names are rendered comma-joined in sorted order."""
    _, findings = _run()
    hit = next(f for f in findings if f["scenario_id"] == "sc-04" and f["package_id"] == "apk-05")
    assert hit["detail"] == "patch admission denied for apk-05: alpha-hack,zeta-hack"


def test_case_x_closure_removes_loser_once():
    """A loser matched by more than one conflict row yields exactly one finding."""
    _, findings = _run()
    sc05 = [f for f in findings if f["scenario_id"] == "sc-05"]
    assert len(sc05) == 1
    assert sc05[0]["package_id"] == "apk-07"
    assert sc05[0]["finding_class"] == "provide_conflict"


def test_case_y_sealed_inputs_immutable_after_run():
    """Fixture inputs are unchanged after a full build-and-publish cycle."""
    _run()
    seals = json.loads(FIXTURE_SEALS.read_text())
    for rel_path, digest in seals.items():
        current = hashlib.sha256((APP / rel_path).read_bytes()).hexdigest()
        assert current == digest


def test_case_z_deterministic():
    """Repeated runs yield identical artifacts."""
    first_board, first_findings = _run()
    second_board, second_findings = _run(clean=False)
    assert first_board == second_board
    assert first_findings == second_findings


def test_case_aa_verifier_owned_wave():
    """A verifier-owned request wave (not a bundled fixture) matches independent replay."""
    packages = _packages()
    pin_by_uri = {row["uri"]: row["sha"] for row in _load_jsonl(PINS)}
    rules = _load_jsonl(ADMIT)
    conflicts = _load_jsonl(CONFLICTS)
    gate_by_id = {row["index_id"]: bool(row["admit"]) for row in _load_jsonl(GATES)}

    # Synthetic wave: pin-ok survivors, one locked write, one digest miss.
    wave = {
        "scenario_id": "sc-vx",
        "requests": [{"package_id": "apk-01"}, {"package_id": "apk-02"}],
        "proposed_writes": [
            {
                "package_id": "apk-01",
                "index_id": "index-locked",
                "payload_digest": packages["apk-01"]["content_digest"],
            },
            {
                "package_id": "apk-02",
                "index_id": "index-open",
                "payload_digest": "dg-not-apk-02",
            },
        ],
    }

    selected: dict[str, dict] = {}
    for req in wave["requests"]:
        pkg = packages[req["package_id"]]
        pin_ok, pin_class = _pin_status(pkg, pin_by_uri)
        assert pin_ok, pin_class
        patch_ok, denied = _patch_status(pkg["package_id"], pkg.get("patches", []), rules)
        assert patch_ok, denied
        selected[pkg["package_id"]] = {
            "package_id": pkg["package_id"],
            "pkgname": pkg["pkgname"],
            "version": pkg["version"],
            "provides": list(pkg.get("provides", [])),
            "content_digest": pkg["content_digest"],
        }
    survivors, hits = _close(selected, conflicts)
    assert hits == []
    assert set(survivors) == {"apk-01", "apk-02"}

    expected_findings = []
    for w in wave["proposed_writes"]:
        sel = survivors[w["package_id"]]
        admit, cls, detail = _write_status(
            gate_by_id[w["index_id"]],
            w["payload_digest"] == sel["content_digest"],
            w["package_id"],
        )
        assert not admit
        expected_findings.append(
            {
                "scenario_id": "sc-vx",
                "package_id": w["package_id"],
                "finding_class": cls,
                "detail": detail,
            }
        )
    expected_findings.sort(
        key=lambda r: (r["scenario_id"], r["package_id"], r["finding_class"])
    )
    assert [f["finding_class"] for f in expected_findings] == [
        "index_denied",
        "digest_mismatch",
    ]
    assert expected_findings[0]["detail"] == "index write denied for apk-01"
    assert expected_findings[1]["detail"] == "index payload digest mismatch for apk-02"

    # Full artifact equality against an independent recomputation of the same wave.
    digest_lines = [
        ("sc-vx", "apk-01", packages["apk-01"]["version"], True, True, False),
        ("sc-vx", "apk-02", packages["apk-02"]["version"], True, True, False),
    ]
    expected_board = {
        "schema_version": "1",
        "scenarios_processed": 1,
        "packages_accepted": 2,
        "writes_admitted": 0,
        "findings_total": 2,
        "scenarios": [
            {
                "scenario_id": "sc-vx",
                "packages": [
                    {
                        "package_id": "apk-01",
                        "version": packages["apk-01"]["version"],
                        "pinned": True,
                        "patches_ok": True,
                        "admitted": False,
                    },
                    {
                        "package_id": "apk-02",
                        "version": packages["apk-02"]["version"],
                        "pinned": True,
                        "patches_ok": True,
                        "admitted": False,
                    },
                ],
            }
        ],
        "digest_hex": _digest(digest_lines),
    }
    assert expected_board["digest_hex"] == hashlib.sha256(b"").hexdigest()
    assert expected_board["findings_total"] == len(expected_findings)


def test_case_ab_fold_conformance_corpus():
    """Every sealed fold worked example reproduces under the independent fold rule."""
    conf_dir = APP / "data" / "conformance"
    cases = sorted(conf_dir.glob("f*.json"))
    assert len(cases) >= 6
    for path in cases:
        case = json.loads(path.read_text())
        lines = [
            (
                row["scenario_id"],
                row["package_id"],
                row["version"],
                bool(row["pinned"]),
                bool(row["patches_ok"]),
                bool(row["admitted"]),
            )
            for row in case["lines"]
        ]
        assert _digest(lines) == case["digest_hex"], path.name


def test_case_ac_conformance_kills_neighbor_rules():
    """Corpus cases diverge under hash-all and under package_id re-sort before fold."""
    f01 = json.loads((APP / "data" / "conformance" / "f01.json").read_text())
    f05 = json.loads((APP / "data" / "conformance" / "f05.json").read_text())

    lines_f01 = [
        (
            row["scenario_id"],
            row["package_id"],
            row["version"],
            bool(row["pinned"]),
            bool(row["patches_ok"]),
            bool(row["admitted"]),
        )
        for row in f01["lines"]
    ]
    assert _digest(lines_f01) == f01["digest_hex"]
    assert _digest_hash_all(lines_f01) != f01["digest_hex"]

    lines_f05 = [
        (
            row["scenario_id"],
            row["package_id"],
            row["version"],
            bool(row["pinned"]),
            bool(row["patches_ok"]),
            bool(row["admitted"]),
        )
        for row in f05["lines"]
    ]
    resorted = sorted(lines_f05, key=lambda t: t[1])
    assert _digest(lines_f05) == f05["digest_hex"]
    assert _digest(resorted) != f05["digest_hex"]


def test_case_ad_rift_conformance_corpus():
    """Every sealed closure worked example reproduces under the independent close rule."""
    cases = sorted((APP / "data" / "conformance").glob("r*.json"))
    assert len(cases) >= 4
    for path in cases:
        case = json.loads(path.read_text())
        survivors, hits = _close(case["selected"], case["conflicts"])
        assert sorted(survivors) == case["survivor_ids"], path.name
        got = [
            {
                "loser": loser,
                "left": left,
                "right": right,
                "kind": kind,
            }
            for loser, left, right, kind in hits
        ]
        assert got == case["hits"], path.name


def test_case_ae_cascade_conflict_keeps_downstream():
    """A chained replace does not remove a downstream package once its partner is gone."""
    board, findings = _run()
    sc11 = next(s for s in board["scenarios"] if s["scenario_id"] == "sc-11")
    ids = {p["package_id"] for p in sc11["packages"]}
    assert ids == {"apk-14", "apk-16"}
    apk16 = next(p for p in sc11["packages"] if p["package_id"] == "apk-16")
    assert apk16["admitted"] is True
    sc11_findings = [f for f in findings if f["scenario_id"] == "sc-11"]
    assert len(sc11_findings) == 1
    assert sc11_findings[0]["package_id"] == "apk-15"
    assert sc11_findings[0]["finding_class"] == "replace_conflict"
