"""Verification for meshgrid Gradle monorepo gridknit stabilizer."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPORT_PATH = Path("/app/build/gradle_stabilization_report.json")
BINARY = Path("/app/build/gridknit")
ROOT = Path("/app/meshgrid")
POLICY = Path("/app/gradle-policy")
APP = Path("/app")

WORKSPACE_KEYS = [
    "gradle_major",
    "gradle_minor",
    "module_count",
    "require_offline_vault",
    "fail_on_project_repos",
    "max_direct_deps",
    "strict_bom",
]
MODULE_KEYS = [
    "module_id",
    "coordinate",
    "bom_consumer",
    "direct_deps",
    "capture",
    "status",
]
CAPTURE_KEYS = [
    "format_version",
    "records_total",
    "records_valid",
    "records_rejected",
    "dup_coord_rejects",
    "payload_bytes",
]
FINDING_KEYS = [
    "finding_id",
    "module_id",
    "entity_id",
    "kind",
    "event_seq",
    "detail",
]
ROOT_KEYS = [
    "workspace",
    "modules",
    "findings",
    "duplicate_modules_skipped",
    "status",
]

PLUGIN_DEFAULTS = {
    "com.meshgrid.wireloom": (8, 7),
    "com.meshgrid.depknit": (8, 8),
    "com.meshgrid.artifactseal": (8, 10),
    "com.meshgrid.pluginbridge": (8, 5),
    "com.meshgrid.releasemesh": (8, 9),
    "com.meshgrid.cataloghub": (8, 10),
    "org.gradle.publish-offline": (8, 6),
}

IMMUTABLE_SHA256: dict[str, str] = {}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_coord(coord: str, version: str) -> str:
    return hashlib.sha256(f"{coord}|{version}".encode()).hexdigest()


def _split_kv(line: str) -> tuple[str, str] | None:
    if "=" not in line:
        return None
    k, v = line.split("=", 1)
    return k.strip(), v.strip()


def load_catalog(path: Path) -> dict[str, Any]:
    versions: dict[str, str] = {}
    libraries: dict[str, dict[str, Any]] = {}
    bundles: dict[str, list[str]] = {}
    section = ""
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line.strip("[]")
            continue
        kv = _split_kv(line)
        if not kv:
            continue
        k, v = kv
        if section == "versions":
            versions[k] = v.strip('"')
        elif section == "libraries":
            libraries[k] = _parse_lib(v)
        elif section == "bundles":
            inner = v.strip().strip("[]")
            bundles[k] = [p.strip().strip('"') for p in inner.split(",") if p.strip()]
    return {"versions": versions, "libraries": libraries, "bundles": bundles}


def _parse_lib(rest: str) -> dict[str, Any]:
    rest = rest.strip().strip("{}")
    out: dict[str, Any] = {"module": "", "version": "", "version_ref": "", "inline": False}
    for part in rest.split(","):
        kv = _split_kv(part.strip())
        if not kv:
            continue
        k, v = kv
        v = v.strip('"')
        if k == "module":
            out["module"] = v
        elif k == "version.ref":
            out["version_ref"] = v
        elif k == "version":
            out["version"] = v
            out["inline"] = True
    return out


def load_plugins(path: Path) -> list[dict[str, Any]]:
    reqs: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[[plugins]]":
            if cur is not None:
                reqs.append(cur)
            cur = {}
            continue
        if cur is None:
            continue
        kv = _split_kv(line)
        if not kv:
            continue
        k, v = kv
        v = v.strip('"')
        if k == "id":
            cur["id"] = v
        elif k == "version":
            cur["version"] = v
        elif k == "min_gradle":
            maj, minor = v.split(".")
            cur["min_gradle"] = (int(maj), int(minor))
    if cur is not None:
        reqs.append(cur)
    return reqs


def load_publish(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        kv = _split_kv(line)
        if not kv:
            continue
        k, v = kv
        v = v.strip('"')
        if k == "signed_publish":
            out[k] = v == "true"
        else:
            out[k] = v
    return out


def decode_lock(path: Path) -> tuple[dict[str, int], list[dict[str, Any]]]:
    stats = {
        "format_version": 0,
        "records_total": 0,
        "records_valid": 0,
        "records_rejected": 0,
        "dup_coord_rejects": 0,
        "payload_bytes": 0,
    }
    if not path.exists():
        return stats, []
    lines = path.read_text().splitlines()
    if not lines or lines[0] != "LOCK1":
        raise ValueError("bad magic")
    stats["format_version"] = int(lines[1])
    seen: set[str] = set()
    recs: list[dict[str, Any]] = []
    for line in lines[3:]:
        if not line.strip():
            continue
        stats["records_total"] += 1
        parts = line.split("\t")
        if len(parts) != 4:
            stats["records_rejected"] += 1
            continue
        coord, version, checksum, opt = parts
        reason = ""
        if opt not in ("0", "1"):
            reason = "BAD_OPTIONAL"
        elif checksum != _sha256_coord(coord, version):
            reason = "BAD_CHECKSUM"
        elif coord in seen:
            reason = "DUP_COORD"
        seen.add(coord)
        if reason:
            stats["records_rejected"] += 1
            if reason == "DUP_COORD":
                stats["dup_coord_rejects"] += 1
            continue
        recs.append(
            {
                "coordinate": coord,
                "version": version,
                "checksum": checksum,
                "optional": opt == "1",
            }
        )
        stats["records_valid"] += 1
        stats["payload_bytes"] += len(line)
    return stats, recs


def resolve_policy(man: dict[str, Any]) -> tuple[bool, bool, int, bool]:
    require_offline = bool(man.get("require_offline_vault", True))
    fail_on_project = bool(man.get("fail_on_project_repos", True))
    max_deps = int(man.get("max_direct_deps") or 3)
    strict_bom = bool(man.get("strict_bom", True))
    ov = man.get("policy_overrides") or {}
    if "require_offline_vault" in ov:
        require_offline = bool(ov["require_offline_vault"])
    if "fail_on_project_repos" in ov:
        fail_on_project = bool(ov["fail_on_project_repos"])
    if "strict_bom" in ov:
        strict_bom = bool(ov["strict_bom"])
    if "max_direct_deps" in ov:
        max_deps = int(ov["max_direct_deps"])
    return require_offline, fail_on_project, max_deps, strict_bom


def plugin_incompatible(req: dict[str, Any], maj: int, minor: int) -> bool:
    if "min_gradle" in req:
        need = req["min_gradle"]
    elif req["id"] in PLUGIN_DEFAULTS:
        need = PLUGIN_DEFAULTS[req["id"]]
    else:
        return False
    if maj < need[0]:
        return True
    if maj > need[0]:
        return False
    return minor < need[1]


def fid(mid: str, entity: str, kind: str, seq: int) -> str:
    return f"{mid}::{entity}::{kind}::{seq:04d}"


def referenced_coords(mf: dict[str, Any], cat: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for alias in mf.get("library_aliases") or []:
        lib = cat["libraries"].get(alias)
        if not lib:
            continue
        if lib["version_ref"]:
            ver = cat["versions"].get(lib["version_ref"])
            if ver is None:
                continue
        elif lib["inline"]:
            ver = lib["version"]
        else:
            continue
        out[lib["module"]] = ver
    for k, v in (mf.get("version_overrides") or {}).items():
        out[k] = v
    return out


def cycle_successors(loaded: dict[str, dict[str, Any]]) -> dict[str, str]:
    in_cycle: set[str] = set()
    for start in loaded:
        visited: set[str] = set()

        def dfs(cur: str, path: list[str], seen: set[str]) -> bool:
            if cur in path:
                idx = path.index(cur)
                in_cycle.update(path[idx:])
                in_cycle.add(cur)
                return True
            if cur in seen:
                return False
            seen.add(cur)
            for dep in loaded[cur].get("dependencies") or []:
                if dep not in loaded:
                    continue
                if dfs(dep, path + [cur], seen):
                    return True
            return False

        dfs(start, [], visited)
    out: dict[str, str] = {}
    for mid in in_cycle:
        cands = sorted(
            d for d in (loaded[mid].get("dependencies") or []) if d in in_cycle
        )
        if cands:
            out[mid] = cands[0]
    return out


def build_expected() -> dict[str, Any]:
    man = json.loads((ROOT / "workspace.manifest.json").read_text())
    require_offline, fail_on_project, max_deps, strict_bom = resolve_policy(man)
    cat = load_catalog(ROOT / "catalog" / "libs.versions.toml")
    reqs = load_plugins(ROOT / "plugins" / "plugin-requests.toml")
    pub = load_publish(ROOT / "publish" / "offline-vault.toml")

    findings: list[dict[str, Any]] = []

    for req in reqs:
        if plugin_incompatible(req, man["gradle_major"], man["gradle_minor"]):
            findings.append(
                {
                    "finding_id": fid("meshgrid", req["id"], "PLUGIN_INCOMPATIBLE", 0),
                    "module_id": "meshgrid",
                    "entity_id": req["id"],
                    "kind": "PLUGIN_INCOMPATIBLE",
                    "event_seq": 0,
                    "detail": req["version"],
                }
            )

    for alias in sorted(set(cat["bundles"]) & set(cat["libraries"])):
        findings.append(
            {
                "finding_id": fid("meshgrid", alias, "CATALOG_ALIAS_CONFLICT", 0),
                "module_id": "meshgrid",
                "entity_id": alias,
                "kind": "CATALOG_ALIAS_CONFLICT",
                "event_seq": 0,
                "detail": "bundle",
            }
        )

    for alias, lib in sorted(cat["libraries"].items()):
        if not lib["inline"]:
            continue
        if alias in cat["versions"] and cat["versions"][alias] != lib["version"]:
            findings.append(
                {
                    "finding_id": fid("meshgrid", alias, "CATALOG_VERSION_DRIFT", 0),
                    "module_id": "meshgrid",
                    "entity_id": alias,
                    "kind": "CATALOG_VERSION_DRIFT",
                    "event_seq": 0,
                    "detail": lib["version"],
                }
            )

    if fail_on_project and pub.get("repositories_mode") != "FAIL_ON_PROJECT_REPOS":
        findings.append(
            {
                "finding_id": fid("meshgrid", "repositories_mode", "PROJECT_REPO_FORBIDDEN", 0),
                "module_id": "meshgrid",
                "entity_id": "repositories_mode",
                "kind": "PROJECT_REPO_FORBIDDEN",
                "event_seq": 0,
                "detail": pub.get("repositories_mode", ""),
            }
        )
    if require_offline:
        if pub.get("vault_path") != "/app/meshgrid/offline-vault":
            findings.append(
                {
                    "finding_id": fid("meshgrid", "vault_path", "OFFLINE_REPO_MISCONFIG", 0),
                    "module_id": "meshgrid",
                    "entity_id": "vault_path",
                    "kind": "OFFLINE_REPO_MISCONFIG",
                    "event_seq": 0,
                    "detail": pub.get("vault_path", ""),
                }
            )
        if not pub.get("signed_publish"):
            findings.append(
                {
                    "finding_id": fid("meshgrid", "signed_publish", "PUBLISH_UNSIGNED", 0),
                    "module_id": "meshgrid",
                    "entity_id": "signed_publish",
                    "kind": "PUBLISH_UNSIGNED",
                    "event_seq": 0,
                    "detail": "",
                }
            )

    seen: set[str] = set()
    dup_skipped = 0
    max_ord = -1
    loaded: dict[str, dict[str, Any]] = {}
    module_order: list[str] = []
    coords: dict[str, str] = {}
    finding_count: dict[str, int] = {}
    captures: dict[str, dict[str, int]] = {}

    for ord_, mid in enumerate(man["modules"]):
        max_ord = max(max_ord, ord_)
        if mid in seen:
            dup_skipped += 1
            continue
        seen.add(mid)
        module_order.append(mid)
        mf = json.loads((ROOT / "modules" / f"{mid}.module.json").read_text())
        loaded[mid] = mf
        coord = f"{mf['group']}:{mf['artifact']}"
        if coord in coords:
            findings.append(
                {
                    "finding_id": fid(mid, coord, "DUPLICATE_MODULE_COORDINATE", ord_),
                    "module_id": mid,
                    "entity_id": coord,
                    "kind": "DUPLICATE_MODULE_COORDINATE",
                    "event_seq": ord_,
                    "detail": coords[coord],
                }
            )
            finding_count[mid] = finding_count.get(mid, 0) + 1
        else:
            coords[coord] = mid

        for dep in mf.get("dependencies") or []:
            if dep == mid:
                findings.append(
                    {
                        "finding_id": fid(mid, mid, "SELF_DEPENDENCY", ord_),
                        "module_id": mid,
                        "entity_id": mid,
                        "kind": "SELF_DEPENDENCY",
                        "event_seq": ord_,
                        "detail": "",
                    }
                )
                finding_count[mid] = finding_count.get(mid, 0) + 1

        if len(mf.get("dependencies") or []) > max_deps:
            findings.append(
                {
                    "finding_id": fid(mid, mid, "DEPENDENCY_FANOUT", ord_),
                    "module_id": mid,
                    "entity_id": mid,
                    "kind": "DEPENDENCY_FANOUT",
                    "event_seq": ord_,
                    "detail": str(len(mf["dependencies"])),
                }
            )
            finding_count[mid] = finding_count.get(mid, 0) + 1

        overrides = mf.get("version_overrides") or {}
        if strict_bom and mf.get("bom_consumer") and overrides:
            k = min(overrides)
            findings.append(
                {
                    "finding_id": fid(mid, k, "BOM_OVERRIDE_FORBIDDEN", ord_),
                    "module_id": mid,
                    "entity_id": k,
                    "kind": "BOM_OVERRIDE_FORBIDDEN",
                    "event_seq": ord_,
                    "detail": overrides[k],
                }
            )
            finding_count[mid] = finding_count.get(mid, 0) + 1

        lock_path = ROOT / "locks" / f"{mid}.lock"
        if not lock_path.exists():
            findings.append(
                {
                    "finding_id": fid(mid, mid, "LOCK_MISSING", ord_),
                    "module_id": mid,
                    "entity_id": mid,
                    "kind": "LOCK_MISSING",
                    "event_seq": ord_,
                    "detail": "",
                }
            )
            finding_count[mid] = finding_count.get(mid, 0) + 1
            captures[mid] = {
                "format_version": 0,
                "records_total": 0,
                "records_valid": 0,
                "records_rejected": 0,
                "dup_coord_rejects": 0,
                "payload_bytes": 0,
            }
        else:
            st, recs = decode_lock(lock_path)
            captures[mid] = st
            refs = referenced_coords(mf, cat)
            for rec in recs:
                if rec["optional"]:
                    continue
                if rec["coordinate"] in refs:
                    if refs[rec["coordinate"]] != rec["version"]:
                        findings.append(
                            {
                                "finding_id": fid(mid, rec["coordinate"], "LOCK_VERSION_DRIFT", ord_),
                                "module_id": mid,
                                "entity_id": rec["coordinate"],
                                "kind": "LOCK_VERSION_DRIFT",
                                "event_seq": ord_,
                                "detail": rec["version"],
                            }
                        )
                        finding_count[mid] = finding_count.get(mid, 0) + 1
                else:
                    findings.append(
                        {
                            "finding_id": fid(mid, rec["coordinate"], "ORPHAN_LOCK_ENTRY", ord_),
                            "module_id": mid,
                            "entity_id": rec["coordinate"],
                            "kind": "ORPHAN_LOCK_ENTRY",
                            "event_seq": ord_,
                            "detail": "",
                        }
                    )
                    finding_count[mid] = finding_count.get(mid, 0) + 1

    for mid in module_order:
        mf = loaded[mid]
        ord_ = man["modules"].index(mid)
        for dep in mf.get("dependencies") or []:
            if dep == mid:
                continue
            if dep not in loaded:
                findings.append(
                    {
                        "finding_id": fid(mid, dep, "UNKNOWN_DEPENDENCY", ord_),
                        "module_id": mid,
                        "entity_id": dep,
                        "kind": "UNKNOWN_DEPENDENCY",
                        "event_seq": ord_,
                        "detail": "UNKNOWN_DEPENDENCY",
                    }
                )
                finding_count[mid] = finding_count.get(mid, 0) + 1

    audit = max_ord + 1
    for mid, succ in sorted(cycle_successors(loaded).items()):
        findings.append(
            {
                "finding_id": fid(mid, mid, "MODULE_CYCLE", audit),
                "module_id": mid,
                "entity_id": mid,
                "kind": "MODULE_CYCLE",
                "event_seq": audit,
                "detail": succ,
            }
        )
        finding_count[mid] = finding_count.get(mid, 0) + 1

    unresolved: set[str] = set()
    for lib in cat["libraries"].values():
        ref = lib["version_ref"]
        if ref and ref not in cat["versions"]:
            unresolved.add(ref)
    for ref in sorted(unresolved):
        findings.append(
            {
                "finding_id": fid("meshgrid", ref, "CATALOG_UNRESOLVED_REF", audit),
                "module_id": "meshgrid",
                "entity_id": ref,
                "kind": "CATALOG_UNRESOLVED_REF",
                "event_seq": audit,
                "detail": "",
            }
        )

    modules_out: list[dict[str, Any]] = []
    for mid in sorted(module_order):
        mf = loaded[mid]
        modules_out.append(
            {
                "module_id": mid,
                "coordinate": f"{mf['group']}:{mf['artifact']}:{mf['version']}",
                "bom_consumer": bool(mf.get("bom_consumer")),
                "direct_deps": sorted(mf.get("dependencies") or []),
                "capture": captures[mid],
                "status": "DRIFT" if finding_count.get(mid, 0) else "STABLE",
            }
        )

    findings.sort(key=lambda f: f["finding_id"])
    status = "DRIFT" if findings else "STABLE"
    return {
        "workspace": {
            "gradle_major": man["gradle_major"],
            "gradle_minor": man["gradle_minor"],
            "module_count": len(modules_out),
            "require_offline_vault": require_offline,
            "fail_on_project_repos": fail_on_project,
            "max_direct_deps": max_deps,
            "strict_bom": strict_bom,
        },
        "modules": modules_out,
        "findings": findings,
        "duplicate_modules_skipped": dup_skipped,
        "status": status,
    }


@pytest.fixture(scope="session", autouse=True)
def _snapshot_immutable() -> None:
    for path in sorted(POLICY.rglob("*")):
        if path.is_file():
            IMMUTABLE_SHA256[str(path)] = _sha256_file(path)
    for path in sorted(ROOT.rglob("*")):
        if path.is_file():
            IMMUTABLE_SHA256[str(path)] = _sha256_file(path)


@pytest.fixture(scope="session")
def expected_report() -> dict[str, Any]:
    return build_expected()


@pytest.fixture(scope="session")
def report(expected_report: dict[str, Any]) -> dict[str, Any]:
    assert BINARY.exists(), "gridknit binary missing"
    subprocess.run([str(BINARY)], check=True, cwd="/app")
    raw = REPORT_PATH.read_bytes()
    assert raw.endswith(b"\n"), "report must end with newline"
    assert b"\n\n" not in raw, "report must be compact single trailing newline"
    data = json.loads(raw.decode())
    # ensure compact re-encode would match oracle style separators
    compact = (json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    # Go encoder may differ slightly on key order already validated separately
    assert data == expected_report
    _ = compact
    return data


def test_full_report_equivalence(report: dict[str, Any], expected_report: dict[str, Any]) -> None:
    """Full report must match independent policy replay."""
    assert report == expected_report


def test_report_schema_key_order(report: dict[str, Any]) -> None:
    """Root workspace module capture and finding key orders are fixed."""
    assert list(report.keys()) == ROOT_KEYS
    assert list(report["workspace"].keys()) == WORKSPACE_KEYS
    for mod in report["modules"]:
        assert list(mod.keys()) == MODULE_KEYS
        assert list(mod["capture"].keys()) == CAPTURE_KEYS
    for finding in report["findings"]:
        assert list(finding.keys()) == FINDING_KEYS


def test_report_compact_json_byte_identical_reruns(report: dict[str, Any]) -> None:
    """Rerunning gridknit on unchanged inputs yields byte-identical report."""
    first = REPORT_PATH.read_bytes()
    subprocess.run([str(BINARY)], check=True, cwd="/app")
    second = REPORT_PATH.read_bytes()
    assert first == second
    assert first.endswith(b"\n")
    _ = report


def test_immutable_policy_and_meshgrid() -> None:
    """Policy docs and meshgrid fixtures must remain unmodified."""
    for path, digest in IMMUTABLE_SHA256.items():
        assert _sha256_file(Path(path)) == digest, path


def test_build_dir_only_binary_and_report() -> None:
    """Build directory contains only gridknit and the stabilization report."""
    names = sorted(p.name for p in Path("/app/build").iterdir())
    assert names == ["gradle_stabilization_report.json", "gridknit"]


def test_duplicate_module_skipped_exact(report: dict[str, Any]) -> None:
    """Duplicate depknit manifest entry increments skip counter once; module_count is unique."""
    assert report["duplicate_modules_skipped"] == 1
    ids = [m["module_id"] for m in report["modules"]]
    assert ids.count("depknit") == 1
    assert report["workspace"]["module_count"] == len(report["modules"]) == 6


def test_direct_deps_are_sorted_string_lists(report: dict[str, Any]) -> None:
    """direct_deps is a sorted string array of dependency module ids, never an int count."""
    for mod in report["modules"]:
        deps = mod["direct_deps"]
        assert isinstance(deps, list)
        assert all(isinstance(d, str) for d in deps)
        assert deps == sorted(deps)
    wire = next(m for m in report["modules"] if m["module_id"] == "wireloom")
    assert wire["direct_deps"] == ["depknit", "pluginbridge"]



def test_plugin_artifactseal_incompatible_numeric(report: dict[str, Any]) -> None:
    """Plugin min_gradle 8.11 is incompatible with numeric Gradle 8.10."""
    hits = [
        f
        for f in report["findings"]
        if f["kind"] == "PLUGIN_INCOMPATIBLE" and f["entity_id"] == "com.meshgrid.artifactseal"
    ]
    assert len(hits) == 1
    assert hits[0]["detail"] == "3.0.1"
    assert hits[0]["event_seq"] == 0


def test_catalog_alias_conflict_guava_detail_bundle(report: dict[str, Any]) -> None:
    """Shared guava alias between libraries and bundles emits conflict."""
    hits = [f for f in report["findings"] if f["kind"] == "CATALOG_ALIAS_CONFLICT"]
    assert any(f["entity_id"] == "guava" and f["detail"] == "bundle" for f in hits)


def test_catalog_version_drift_jackson_core(report: dict[str, Any]) -> None:
    """Inline jackson-core version disagrees with versions table alias."""
    hits = [f for f in report["findings"] if f["kind"] == "CATALOG_VERSION_DRIFT"]
    assert any(f["entity_id"] == "jackson-core" and f["detail"] == "2.16.0" for f in hits)


def test_offline_publish_findings_exact(report: dict[str, Any]) -> None:
    """Broken offline vault settings emit project repo vault and unsigned findings."""
    kinds = {f["kind"]: f for f in report["findings"] if f["module_id"] == "meshgrid"}
    assert kinds["PROJECT_REPO_FORBIDDEN"]["detail"] == "PREFER_PROJECT"
    assert kinds["OFFLINE_REPO_MISCONFIG"]["detail"] == "/tmp/wrong-vault"
    assert kinds["PUBLISH_UNSIGNED"]["detail"] == ""


def test_releasemesh_dependency_fanout_strictly_gt(report: dict[str, Any]) -> None:
    """Four direct deps exceeds max_direct_deps three."""
    hits = [
        f
        for f in report["findings"]
        if f["kind"] == "DEPENDENCY_FANOUT" and f["module_id"] == "releasemesh"
    ]
    assert len(hits) == 1
    assert hits[0]["detail"] == "4"


def test_artifactseal_bom_and_lock_finding_ids_distinct(report: dict[str, Any]) -> None:
    """BOM override and lock drift on the same guava coordinate use kind in finding_id."""
    arts = [f for f in report["findings"] if f["module_id"] == "artifactseal"]
    bom = next(f for f in arts if f["kind"] == "BOM_OVERRIDE_FORBIDDEN")
    drift = next(f for f in arts if f["kind"] == "LOCK_VERSION_DRIFT")
    assert bom["entity_id"] == drift["entity_id"] == "com.google.guava:guava"
    assert bom["event_seq"] == drift["event_seq"] == 0
    assert bom["finding_id"] == "artifactseal::com.google.guava:guava::BOM_OVERRIDE_FORBIDDEN::0000"
    assert drift["finding_id"] == "artifactseal::com.google.guava:guava::LOCK_VERSION_DRIFT::0000"
    assert bom["detail"] == "32.0.0"
    assert drift["detail"] == "33.0.0"
    ids = [f["finding_id"] for f in report["findings"]]
    assert len(ids) == len(set(ids))


def test_artifactseal_bom_override_forbidden_first_key(report: dict[str, Any]) -> None:
    """BOM consumer cannot keep version overrides under strict_bom."""
    hits = [
        f
        for f in report["findings"]
        if f["kind"] == "BOM_OVERRIDE_FORBIDDEN" and f["module_id"] == "artifactseal"
    ]
    assert len(hits) == 1
    assert hits[0]["entity_id"] == "com.google.guava:guava"
    assert hits[0]["detail"] == "32.0.0"


def test_depknit_lock_version_drift(report: dict[str, Any]) -> None:
    """Lock version must match module override for jackson-databind."""
    hits = [
        f
        for f in report["findings"]
        if f["kind"] == "LOCK_VERSION_DRIFT" and f["module_id"] == "depknit"
    ]
    assert len(hits) == 1
    assert hits[0]["entity_id"] == "com.fasterxml.jackson.core:jackson-databind"
    assert hits[0]["detail"] == "2.16.1"


def test_artifactseal_orphan_lock_entry(report: dict[str, Any]) -> None:
    """Required lock coordinates unused by the module are orphaned."""
    hits = [
        f
        for f in report["findings"]
        if f["kind"] == "ORPHAN_LOCK_ENTRY" and f["module_id"] == "artifactseal"
    ]
    assert any(f["entity_id"] == "org.example:orphan-lib" for f in hits)


def test_pluginbridge_bad_checksum_capture_counters(report: dict[str, Any]) -> None:
    """Bad checksum lines are rejected and excluded from valid lock records."""
    mod = next(m for m in report["modules"] if m["module_id"] == "pluginbridge")
    cap = mod["capture"]
    assert cap["format_version"] == 1
    assert cap["records_total"] == 2
    assert cap["records_valid"] == 1
    assert cap["records_rejected"] == 1


def test_cataloghub_unknown_dependency_ghostmod(report: dict[str, Any]) -> None:
    """Unknown dependency module ids emit UNKNOWN_DEPENDENCY."""
    hits = [
        f
        for f in report["findings"]
        if f["kind"] == "UNKNOWN_DEPENDENCY" and f["module_id"] == "cataloghub"
    ]
    assert len(hits) == 1
    assert hits[0]["entity_id"] == "ghostmod"
    assert hits[0]["detail"] == "UNKNOWN_DEPENDENCY"


def test_module_cycle_wireloom_pluginbridge(report: dict[str, Any]) -> None:
    """Mutual module edges form a cycle reported at audit sequence."""
    hits = [f for f in report["findings"] if f["kind"] == "MODULE_CYCLE"]
    mods = {f["module_id"] for f in hits}
    assert "wireloom" in mods and "pluginbridge" in mods
    assert all(f["event_seq"] == report["duplicate_modules_skipped"] + 6 for f in hits) or all(
        f["event_seq"] == 7 for f in hits
    )


def test_unresolved_ref_post_mesh(report: dict[str, Any]) -> None:
    """Missing version.ref names emit CATALOG_UNRESOLVED_REF at max_ord plus one."""
    hits = [f for f in report["findings"] if f["kind"] == "CATALOG_UNRESOLVED_REF"]
    assert len(hits) == 1
    assert hits[0]["entity_id"] == "does-not-exist"
    assert hits[0]["event_seq"] == 7


def test_root_status_drift_when_findings(report: dict[str, Any]) -> None:
    """Root status is DRIFT when findings are present."""
    assert report["findings"]
    assert report["status"] == "DRIFT"


def test_perturbed_lock_changes_report_then_restores(report: dict[str, Any]) -> None:
    """Changing a lock file must change findings then restore after revert."""
    lock = ROOT / "locks" / "wireloom.lock"
    original = lock.read_bytes()
    first = REPORT_PATH.read_bytes()
    try:
        lock.write_text(
            "LOCK1\n1\n1\n"
            "com.google.guava:guava\t99.0.0\t"
            + _sha256_coord("com.google.guava:guava", "99.0.0")
            + "\t0\n"
        )
        # meshgrid is immutable for agents but verifier may perturb temporarily
        # Restore digest tracker expectation by reverting after
        subprocess.run([str(BINARY)], check=True, cwd="/app")
        second = REPORT_PATH.read_bytes()
        assert second != first
    finally:
        lock.write_bytes(original)
        subprocess.run([str(BINARY)], check=True, cwd="/app")
        assert REPORT_PATH.read_bytes() == first
    _ = report
