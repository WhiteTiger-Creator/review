"""Verifier for pixilock pixi Pixi resolve lock release task."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
from collections import defaultdict, deque
from pathlib import Path

import pytest
import tomllib

APP = Path("/app")
DIST = APP / "dist"
MATRIX = APP / "config" / "release_matrix.csv"
BASE_SRC = Path("/tests/baselines")
PRIVATE_ROOT = Path("/opt/harbor-verifier")
BASE = PRIVATE_ROOT / "pixilock-baselines"

PIN_DIGESTS = {
    "fmt": ("10.2.1", "16de8120e52729f6199371abe65cf9be293fd1461d73727bb187934db6e43313"),
    "zlib": ("1.3.1", "f5639a1dc21583311e433c27c086f6009700df2c60ef12a7362d830be5f63907"),
    "spdlog": ("1.13.0", "a6796ab08339bdb8a7b9be12d9baec92f38cb58434ea3f1ad3f1df991dfc0f4d"),
}

REQUIRED_BUNDLE_FILES = (
    "bin/pixilock",
    "LICENSES.txt",
    "VERSION",
    "share/lane-policy.json",
    "share/edges.csv",
    "share/artifacts.csv",
    "share/deps.csv",
    "share/xor.csv",
    "share/mirrors.csv",
    "share/pins.csv",
    "share/bans.csv",
    "share/forbidden-hosts.csv",
    "share/version-caps.csv",
    "share/risk-policy.csv",
    "share/cascade-policy.csv",
    "share/cascade-route-blocks.csv",
    "share/run-smoke.sh",
    "share/inspect-preview.json",
)


@pytest.fixture(scope="session")
def release_dist() -> Path:
    """Build the release package once from the task workspace."""
    run_release()
    return DIST


def run_release(*, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["CARGO_NET_OFFLINE"] = "true"
    env["SOURCE_DATE_EPOCH"] = "1700000000"
    return subprocess.run(
        ["bash", "/app/scripts/release.sh"],
        cwd=APP,
        env=env,
        check=check,
        timeout=360,
        text=True,
        capture_output=True,
    )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def strip_sha(s: str) -> str:
    return s.strip().removeprefix("sha256:")


def basename_of(url: str) -> str:
    return Path(url.rstrip("/")).name


def matrix_rows() -> list[dict[str, str]]:
    with MATRIX.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def ensure_baseline_cache() -> None:
    """Always refresh private baselines from /tests/baselines; never trust a pre-existing tree."""
    if not BASE_SRC.exists():
        raise FileNotFoundError("missing /tests/baselines")
    PRIVATE_ROOT.mkdir(parents=True, exist_ok=True)
    if BASE.exists():
        shutil.rmtree(BASE)
    shutil.copytree(BASE_SRC, BASE)


def expected_inspect(lane: str, retention_hops: int, data_dir: Path | None = None) -> dict:
    """Reference inspector over a CSV directory (defaults to verifier baseline cache)."""
    ensure_baseline_cache()
    root = data_dir if data_dir is not None else BASE

    def csv_path(name: str) -> Path:
        path = root / name
        if name == "deps.csv" and not path.exists():
            alt = root / "deps.expected.csv"
            if alt.exists():
                return alt
        return path

    edges = [
        r for r in csv.DictReader(csv_path("edges.csv").open(encoding="utf-8")) if r["lane"] == lane
    ]
    artifacts = [
        r["coordinate"]
        for r in csv.DictReader(csv_path("artifacts.csv").open(encoding="utf-8"))
        if r["lane"] == lane
    ]
    deps = [
        r for r in csv.DictReader(csv_path("deps.csv").open(encoding="utf-8")) if r["lane"] == lane
    ]
    mirrors = {r["basename"] for r in csv.DictReader(csv_path("mirrors.csv").open(encoding="utf-8"))}
    pins = {
        f"dep:{r['wrap']}": r for r in csv.DictReader(csv_path("pins.csv").open(encoding="utf-8"))
    }
    xor_rows = [
        r for r in csv.DictReader(csv_path("xor.csv").open(encoding="utf-8")) if r["lane"] == lane
    ]
    bans = {r["coordinate"] for r in csv.DictReader(csv_path("bans.csv").open(encoding="utf-8"))}
    forbidden = [
        r["host"] for r in csv.DictReader(csv_path("forbidden-hosts.csv").open(encoding="utf-8"))
    ]
    version_caps = {
        r["coordinate"]: r["max_version"]
        for r in csv.DictReader(csv_path("version-caps.csv").open(encoding="utf-8"))
    }

    art_set = set(artifacts)
    holds: dict[str, dict[str, int]] = {a: {} for a in artifacts}

    risks = {
        r["kind"]: int(r["risk"])
        for r in csv.DictReader(csv_path("risk-policy.csv").open(encoding="utf-8"))
    }
    cascade_policy = {
        r["prefix"]: (int(r["decay"]), int(r["max_hops"]))
        for r in csv.DictReader(csv_path("cascade-policy.csv").open(encoding="utf-8"))
        if r["lane"] == lane
    }
    route_blocks: dict[str, list[str]] = defaultdict(list)
    for r in csv.DictReader(csv_path("cascade-route-blocks.csv").open(encoding="utf-8")):
        if r["lane"] == lane:
            route_blocks[r["prefix"]].append(r["block_match"])

    def add(coord: str, reason: str, risk: int) -> None:
        if coord not in holds:
            return
        holds[coord][reason] = max(holds[coord].get(reason, 0), risk)

    def parse_ver(v: str) -> tuple[int, int, int]:
        parts = [*v.split("."), "0", "0", "0"][:3]
        return tuple(int(x) for x in parts)  # type: ignore[return-value]

    def ver_gt(a: str, b: str) -> bool:
        return parse_ver(a) > parse_ver(b)

    for w in deps:
        if w["coordinate"] not in art_set:
            continue
        src = w["source_url"]
        remote_src = (not src.startswith("file:///")) or any(h in src for h in forbidden)
        if remote_src:
            add(w["coordinate"], f"remote:{w['coordinate']}:source", risks["remote"])
        patch = w.get("patch_url") or ""
        if patch:
            remote_p = (not patch.startswith("file:///")) or any(h in patch for h in forbidden)
            if remote_p:
                add(w["coordinate"], f"remote:{w['coordinate']}:patch", risks["remote"])
        pin = pins.get(w["coordinate"])
        if pin is None:
            add(w["coordinate"], f"missingpin:{w['coordinate']}", risks["missingpin"])
        else:
            exp = strip_sha(pin["sha256"])
            act = strip_sha(w["source_hash"])
            if exp != act:
                add(w["coordinate"], f"hashdrift:{w['coordinate']}:{exp}:{act}", risks["hashdrift"])
            if pin["version"] != w["version"]:
                add(
                    w["coordinate"],
                    f"versiondrift:{w['coordinate']}:{pin['version']}:{w['version']}",
                    risks["versiondrift"],
                )
        base = basename_of(src)
        if base and base not in mirrors:
            add(w["coordinate"], f"mirrormiss:{w['coordinate']}:{base}", risks["mirrormiss"])

    by_provide: dict[str, set[str]] = defaultdict(set)
    for w in deps:
        if w["coordinate"] in art_set:
            by_provide[w["provide"]].add(w["coordinate"])
    for provide, coords in by_provide.items():
        if len(coords) < 2:
            continue
        joined = "|".join(sorted(coords))
        hold = f"provcollide:{provide}:{joined}"
        for c in coords:
            add(c, hold, risks["provcollide"])

    provide_to_deps: dict[str, set[str]] = defaultdict(set)
    for w in deps:
        if w["coordinate"] in art_set:
            provide_to_deps[w["provide"]].add(w["coordinate"])
    by_group: dict[str, set[str]] = defaultdict(set)
    for row in xor_rows:
        if row["provide"] in provide_to_deps:
            by_group[row["group"]].add(row["provide"])
    for group, provides in by_group.items():
        if len(provides) < 2:
            continue
        joined = "|".join(sorted(provides))
        hold = f"xor:{group}:{joined}"
        for p in provides:
            for coord in provide_to_deps[p]:
                add(coord, hold, risks["xor"])

    for a in artifacts:
        if a in bans:
            add(a, f"ban:{a}", risks["ban"])

    for w in deps:
        if w["coordinate"] not in art_set:
            continue
        maxv = version_caps.get(w["coordinate"])
        if maxv is not None and ver_gt(w["version"], maxv):
            add(w["coordinate"], f"cap:{w['coordinate']}:{w['version']}:{maxv}", risks["cap"])

    origin_holds: dict[str, list[tuple[str, int]]] = {}
    for coord, hmap in holds.items():
        for reason, risk in hmap.items():
            if reason.startswith(("ban:", "remote:", "xor:", "provcollide:", "cap:")):
                origin_holds.setdefault(coord, []).append((reason, risk))
    rev: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        if e["edge_kind"] == "hard":
            rev[e["child"]].append(e["parent"])
    for parents in rev.values():
        parents.sort()

    for prefix, (decay, max_hops) in cascade_policy.items():
        origins = {
            origin
            for origin, hs in origin_holds.items()
            if any(reason.split(":", 1)[0] == prefix for reason, _ in hs)
        }
        route_hops = min(retention_hops, max_hops)
        blocked = route_blocks.get(prefix, [])
        best_routes: dict[str, dict[str, tuple[int, str]]] = defaultdict(dict)
        for origin in origins:
            best: dict[str, tuple[int, str]] = {origin: (0, "")}
            q = deque([origin])
            while q:
                node = q.popleft()
                dist, via = best[node]
                if dist >= route_hops:
                    continue
                for parent in rev.get(node, []):
                    nd = dist + 1
                    if dist == 0:
                        nvia = "-"
                    elif via == "-":
                        nvia = node
                    else:
                        nvia = f"{via}/{node}"
                    cand = (nd, nvia)
                    prev = best.get(parent)
                    if prev is None or cand < prev:
                        best[parent] = cand
                        if parent != origin:
                            best_routes[parent][origin] = cand
                        if not any(parent.startswith(b) for b in blocked):
                            q.append(parent)
        for parent, origin_map in best_routes.items():
            for origin, (nd, nvia) in origin_map.items():
                for reason, risk in origin_holds[origin]:
                    if reason.split(":", 1)[0] != prefix:
                        continue
                    attenuated = max(1, risk - decay * nd)
                    add(parent, f"cascade:{nd}:{origin}@{nvia}:{reason}", attenuated)

    reports = []
    totals = {
        "release": 0,
        "hold": 0,
        "remotes": 0,
        "hashdrifts": 0,
        "versiondrifts": 0,
        "mirrormisses": 0,
        "provcollides": 0,
        "xors": 0,
        "missingpins": 0,
        "bans": 0,
        "caps": 0,
        "cascades": 0,
        "risk_score_total": 0,
    }
    for coord in sorted(artifacts):
        hmap = holds.get(coord, {})
        hold_list = sorted(hmap)
        score = sum(hmap[h] for h in hold_list)
        for h in hold_list:
            if h.startswith("remote:"):
                totals["remotes"] += 1
            elif h.startswith("hashdrift:"):
                totals["hashdrifts"] += 1
            elif h.startswith("versiondrift:"):
                totals["versiondrifts"] += 1
            elif h.startswith("mirrormiss:"):
                totals["mirrormisses"] += 1
            elif h.startswith("provcollide:"):
                totals["provcollides"] += 1
            elif h.startswith("xor:"):
                totals["xors"] += 1
            elif h.startswith("missingpin:"):
                totals["missingpins"] += 1
            elif h.startswith("ban:"):
                totals["bans"] += 1
            elif h.startswith("cap:"):
                totals["caps"] += 1
            elif h.startswith("cascade:"):
                totals["cascades"] += 1
        status = "release" if not hold_list else "hold"
        totals[status] += 1
        totals["risk_score_total"] += score
        reports.append(
            {"coordinate": coord, "status": status, "holds": hold_list, "risk_score": score}
        )
    return {
        "lane": lane,
        "retention_hops": retention_hops,
        "artifacts": reports,
        "totals": totals,
    }




def test_release_sh_mentions_pixi(release_dist: Path) -> None:
    """Enforce pixi-contract's requirement that validation is visible in release.sh itself."""
    _ = release_dist
    text = (APP / "scripts" / "release.sh").read_text(encoding="utf-8")
    assert "pixi" in text

def test_version(release_dist: Path) -> None:
    """Packaged binary prints exact pixilock 12.6.3."""
    lane = matrix_rows()[0]["lane"]
    binary = release_dist / "bundles" / f"pixilock-{lane}" / "bin" / "pixilock"
    assert subprocess.check_output([str(binary), "--version"], text=True).strip() == "pixilock 12.6.3"


def test_pixi_layout(release_dist: Path) -> None:
    """Repaired pins, freeze file, pixi.project, and pixi-report schema."""
    _ = release_dist
    freeze = (APP / "pixi.toml").read_text(encoding="utf-8")
    assert re.search(r"(?m)^\s*offline\s*=\s*true\s*$", freeze)
    assert re.search(r"(?m)^\s*cache-dir\s*=\s*/app/pixi-cache\s*$", freeze)
    assert (APP / "legacy-pixi-notes.txt").read_text(encoding="utf-8").strip() == "# emptied for pixi"
    for name, (verd, pin) in PIN_DIGESTS.items():
        data = json.loads((APP / "conda" / "deps" / f"{name}.json").read_text(encoding="utf-8"))
        assert data["provide"] == name
        assert data["version"] == verd
        assert data["resolved"] == f"file:///app/pixi-cache/{name}-{verd}.conda"
        assert data["integrity"] == f"sha256:{pin}"
        assert data.get("packaging") == "conda"
        assert "https://" not in json.dumps(data)
        archive = APP / "pixi-cache" / f"{name}-{verd}.conda"
        assert sha256(archive) == pin
        assert archive.stat().st_size > 32
    with (APP / "config" / "deps.csv").open(encoding="utf-8") as handle:
        for drow in csv.DictReader(handle):
            if drow["coordinate"] == "dep:spdlog":
                assert drow["version"] == "1.13.0"
                assert drow["provide"] == "spdlog"
                assert not (drow.get("patch_url") or "").strip()
    pkg = json.loads((APP / "pixi.project").read_text(encoding="utf-8"))
    assert "pixi" in pkg
    for decoy in ("pants", "cabal", "buck"):
        assert decoy not in pkg, decoy
    lock = (APP / "pixi.lock").read_text(encoding="utf-8")
    for name, (verd, pin) in PIN_DIGESTS.items():
        assert pkg["pixi"][name] == f"file:///app/pixi-cache/{name}-{verd}.conda"
        assert f"file:///app/pixi-cache/{name}-{verd}.conda" in lock
        assert f"sha256:{pin}" in lock
    assert lock.startswith("# pixi lockfile v1")
    report = json.loads((DIST / "pixi-report.json").read_text(encoding="utf-8"))
    assert report["format_version"] == 1
    assert isinstance(report["format_version"], int)
    assert report["legacy_cleared"] is True
    assert report["offline_pixi_mode"] is True
    assert isinstance(report["legacy_cleared"], bool)
    assert isinstance(report["offline_pixi_mode"], bool)
    deps = report["deps"]
    assert isinstance(deps, list)
    assert deps == sorted(deps, key=lambda d: d["name"])
    assert [d["name"] for d in deps] == ["fmt", "spdlog", "zlib"]
    dep_keys = {"name", "provide", "version", "source_url", "source_hash", "mirror_ok"}
    for d in deps:
        assert set(d) == dep_keys
        assert isinstance(d["mirror_ok"], bool)
        assert d["mirror_ok"] is True
        verd, pin = PIN_DIGESTS[d["name"]]
        assert d["provide"] == d["name"]
        assert d["version"] == verd
        assert d["source_url"] == f"file:///app/pixi-cache/{d['name']}-{verd}.conda"
        assert d["source_hash"] == f"sha256:{pin}"
        assert d["source_hash"].startswith("sha256:")
        assert len(d["source_hash"]) == 71
        assert d["source_hash"] == "sha256:" + d["source_hash"][7:].lower()
        assert d["source_url"].startswith("file:///app/pixi-cache/")
        assert ":" not in d["name"]
        assert "/" not in d["name"]
        assert not d["name"].startswith("dep:")
        path = Path(d["source_url"][len("file://") :])
        assert path.is_file()
        assert path.stat().st_size > 32
        assert sha256(path) == d["source_hash"][7:]
    assert report["cargo_packages"] == [
        "pixilock-graph",
        "pixilock-cli",
        "pixilock-core",
        "pixilock-index",
    ]


def test_offline_cargo(release_dist: Path) -> None:
    """Cargo remains offline."""
    _ = release_dist
    assert "offline = true" in (APP / ".cargo" / "config.toml").read_text(encoding="utf-8")


def test_bundles_manifest(release_dist: Path) -> None:
    """Each lane has share/ layout, archive at dist root, and typed manifest digests."""
    manifest = json.loads((release_dist / "release-manifest.json").read_text(encoding="utf-8"))
    assert set(manifest) == {"format_version", "package", "workspace", "fetch", "bundles"}
    report = json.loads((release_dist / "pixi-report.json").read_text(encoding="utf-8"))
    assert manifest["fetch"] == report
    assert manifest["package"] == {
        "name": "pixilock-cli",
        "version": "12.6.3",
        "target": "x86_64-unknown-linux-gnu",
    }
    rows = matrix_rows()
    assert [b["lane"] for b in manifest["bundles"]] == [r["lane"] for r in rows]
    for entry, row in zip(manifest["bundles"], rows, strict=True):
        lane = row["lane"]
        bundle = release_dist / "bundles" / f"pixilock-{lane}"
        archive = release_dist / f"pixilock-{lane}-linux-x86_64.tar.gz"
        for rel in REQUIRED_BUNDLE_FILES:
            assert (bundle / rel).exists(), rel
        assert (bundle / "VERSION").read_text(encoding="utf-8") == "pixilock 12.6.3\n"
        smoke = (bundle / "share" / "run-smoke.sh").read_text(encoding="utf-8")
        assert "OUT=${1:-" in smoke
        assert 'OUT="${1:-' not in smoke
        assert "--edges" in smoke
        assert "--version-caps" in smoke
        assert "--risk-policy" in smoke
        assert "--cascade-policy" in smoke
        assert "--cascade-route-blocks" in smoke
        policy = json.loads((bundle / "share" / "lane-policy.json").read_text(encoding="utf-8"))
        assert policy == {"lane": lane, "retention_hops": int(row["retention_hops"])}
        expected_keys = {
            "lane",
            "archive",
            "archive_sha256",
            "binary_sha256",
            "policy_sha256",
            "inspect_preview_sha256",
            "artifact_count",
            "hold_count",
            "risk_score_total",
        }
        assert set(entry) == expected_keys
        assert entry["archive"] == archive.name
        assert entry["archive_sha256"] == sha256(archive)
        assert entry["binary_sha256"] == sha256(bundle / "bin" / "pixilock")
        assert entry["policy_sha256"] == sha256(bundle / "share" / "lane-policy.json")
        assert entry["inspect_preview_sha256"] == sha256(bundle / "share" / "inspect-preview.json")
        insp = expected_inspect(lane, int(row["retention_hops"]))
        assert entry["artifact_count"] == len(insp["artifacts"])
        assert entry["hold_count"] == insp["totals"]["hold"]
        assert entry["risk_score_total"] == insp["totals"]["risk_score_total"]
        expected_lic = b""
        for lf in sorted((APP / "licenses").iterdir(), key=lambda p: p.name):
            if lf.is_file():
                expected_lic += lf.read_bytes() + b"\n"
        assert (bundle / "LICENSES.txt").read_bytes() == expected_lic
    assert not (release_dist / "bundles" / "pixilock-nightly").exists()


def test_workspace(release_dist: Path) -> None:
    """Workspace inventory follows sorted crates/*/Cargo.toml path order."""
    manifest = json.loads((release_dist / "release-manifest.json").read_text(encoding="utf-8"))
    expected_names = [
        tomllib.loads(path.read_text(encoding="utf-8"))["package"]["name"]
        for path in sorted((APP / "crates").glob("*/Cargo.toml"))
    ]
    assert [e["name"] for e in manifest["workspace"]] == expected_names == [
        "pixilock-graph",
        "pixilock-cli",
        "pixilock-core",
        "pixilock-index",
    ]
    ws_pkg = tomllib.loads((APP / "Cargo.toml").read_text(encoding="utf-8"))["workspace"]["package"]
    for entry in manifest["workspace"]:
        assert set(entry) == {"name", "version", "license", "dependencies"}
        assert entry["version"] == "12.6.3"
        assert entry["license"] == ws_pkg["license"]
        assert entry["dependencies"] == sorted(entry["dependencies"])


def test_checksums(release_dist: Path) -> None:
    """checksums.sha256 lists every dist file except itself with two spaces."""
    text = (release_dist / "checksums.sha256").read_text(encoding="utf-8")
    mapping = {}
    for ln in text.splitlines():
        if not ln.strip():
            continue
        digest, rel = ln.split("  ", 1)
        mapping[rel] = digest
    expected_rels = []
    for path in sorted(release_dist.rglob("*")):
        if path.is_file() and path.name != "checksums.sha256":
            rel = path.relative_to(release_dist).as_posix()
            expected_rels.append(rel)
            assert mapping[rel] == sha256(path)
    assert list(mapping) == sorted(expected_rels)


def test_archive_reproducible(release_dist: Path) -> None:
    """Archives keep pixilock-<lane> root and stable digests across reruns."""
    lane = matrix_rows()[0]["lane"]
    archive = release_dist / f"pixilock-{lane}-linux-x86_64.tar.gz"
    first = sha256(archive)
    with tarfile.open(archive, "r:gz") as tar:
        names = tar.getnames()
    assert any(n == f"pixilock-{lane}" or n.startswith(f"pixilock-{lane}/") for n in names)
    run_release()
    assert first == sha256(DIST / f"pixilock-{lane}-linux-x86_64.tar.gz")


@pytest.mark.parametrize("row", matrix_rows(), ids=lambda r: r["lane"])
def test_inspect_preview(release_dist: Path, row: dict[str, str], tmp_path: Path) -> None:
    """Inspect preview and live smoke output match protected baseline oracle."""
    lane = row["lane"]
    hops = int(row["retention_hops"])
    bundle = release_dist / "bundles" / f"pixilock-{lane}"
    preview = json.loads((bundle / "share" / "inspect-preview.json").read_text(encoding="utf-8"))
    expected = expected_inspect(lane, hops)
    assert preview == expected
    smoke = bundle / "share" / "run-smoke.sh"
    fresh = tmp_path / f"inspect-{lane}.json"
    proc = subprocess.run(
        [str(smoke), str(fresh)],
        cwd=bundle,
        check=False,
        timeout=60,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert fresh.is_file(), "run-smoke.sh must write caller $1 via pixilock inspect --out"
    live = json.loads(fresh.read_text(encoding="utf-8"))
    assert live == expected
    assert live == preview


def test_deps_csv_matches_baseline(release_dist: Path) -> None:
    """Repaired deps.csv field values match baseline; row order/serialization are not normative."""
    _ = release_dist
    fields = [
        "lane",
        "coordinate",
        "provide",
        "version",
        "source_url",
        "source_hash",
        "patch_url",
    ]

    def load_rows(csv_path: Path) -> list[tuple[str, ...]]:
        with csv_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        out = []
        for row in rows:
            out.append(tuple((row.get(f) or "").strip() for f in fields))
        return out

    expected = load_rows(Path("/tests") / "baselines" / "deps.expected.csv")
    actual = load_rows(APP / "config" / "deps.csv")
    assert sorted(actual) == sorted(expected)
    with (APP / "config" / "deps.csv").open(encoding="utf-8") as handle:
        for drow in csv.DictReader(handle):
            if drow["coordinate"] == "dep:spdlog":
                assert drow["provide"] == "spdlog"
                assert not drow["version"].startswith("v")
            if drow["coordinate"] in {"dep:fmt", "dep:zlib", "dep:spdlog"}:
                assert drow["provide"] == drow["coordinate"].split(":", 1)[1]
                assert not (drow.get("patch_url") or "").strip()


def test_soft_edges_ignored(release_dist: Path) -> None:
    """Soft edges do not cascade; ban attenuation uses selected-lane cascade-policy decay."""
    preview = json.loads(
        (release_dist / "bundles" / "pixilock-edge" / "share" / "inspect-preview.json").read_text(
            encoding="utf-8"
        )
    )
    by = {a["coordinate"]: a for a in preview["artifacts"]}
    assert not any(h.startswith("cascade:") for h in by["trace:soft"]["holds"])
    assert "cascade:1:dep:legacy@-:ban:dep:legacy" in by["mid:alpha"]["holds"]
    assert "cascade:1:dep:legacy@-:ban:dep:legacy" in by["mid:zeta"]["holds"]
    assert "cascade:2:dep:legacy@mid:zeta:ban:dep:legacy" not in by["svc:app"]["holds"]
    assert "cascade:2:dep:legacy@mid:alpha:ban:dep:legacy" in by["svc:app"]["holds"]
    # spine: is route-blocked for ban: targets may emit, but spine never expands into via.
    assert not any("spine:" in h for h in by["svc:app"]["holds"] if h.startswith("cascade:"))
    decay = {
        r["prefix"]: int(r["decay"])
        for r in csv.DictReader((APP / "config" / "cascade-policy.csv").open(encoding="utf-8"))
        if r["lane"] == "edge"
    }["ban"]
    risks = {
        r["kind"]: int(r["risk"])
        for r in csv.DictReader((APP / "config" / "risk-policy.csv").open(encoding="utf-8"))
    }
    ban_risk = risks["ban"]
    ban_cascade_risks = {}
    for art in preview["artifacts"]:
        for h in art["holds"]:
            if h.startswith("cascade:") and h.endswith(":ban:dep:legacy"):
                d = int(h.split(":", 2)[1])
                ban_cascade_risks[art["coordinate"]] = max(1, ban_risk - decay * d)
    assert ban_risk == 241
    assert decay == 89
    assert ban_cascade_risks["mid:alpha"] == max(1, ban_risk - decay)
    assert ban_cascade_risks["mid:alpha"] == 152
    assert ban_cascade_risks["svc:app"] == max(1, ban_risk - decay * 2)
    assert ban_cascade_risks["svc:app"] == 63
    assert "cap:dep:legacy:0.1.0:0.0.9" in by["dep:legacy"]["holds"]
    assert "cascade:1:dep:legacy@-:cap:dep:legacy:0.1.0:0.0.9" in by["mid:alpha"]["holds"]
    assert "cascade:2:dep:legacy@mid:alpha:cap:dep:legacy:0.1.0:0.0.9" not in by["svc:app"]["holds"]


def _fail_closed_with_sentinel(mutate, restore, path: Path, expected_broken) -> None:
    """Mutate an input, assert release fails closed, leaves mutation + dist sentinel intact."""
    sentinel = DIST / "sentinel-keep.txt"
    sentinel.write_text("keep me", encoding="utf-8")
    try:
        mutate()
        proc = run_release(check=False)
        assert proc.returncode != 0
        if isinstance(expected_broken, bytes):
            assert path.read_bytes() == expected_broken
        else:
            assert path.read_text(encoding="utf-8") == expected_broken
        assert sentinel.is_file(), "release.sh must validate before clearing /app/dist"
        assert sentinel.read_text(encoding="utf-8") == "keep me"
    finally:
        restore()
        if sentinel.exists():
            sentinel.unlink()


def test_fail_closed_pixi_project_key(release_dist: Path) -> None:
    """pixi.project must keep top-level pixi map (cabal key is rejected)."""
    _ = release_dist
    pkg_path = APP / "pixi.project"
    original = pkg_path.read_text(encoding="utf-8")
    data = json.loads(original)
    data["cabal"] = data.pop("pixi")
    broken = json.dumps(data, indent=2) + "\n"
    _fail_closed_with_sentinel(
        lambda: pkg_path.write_text(broken, encoding="utf-8"),
        lambda: pkg_path.write_text(original, encoding="utf-8"),
        pkg_path,
        broken,
    )


def test_no_unpacked_at_root(release_dist: Path) -> None:
    """Unpacked bundles live only under dist/bundles."""
    for path in release_dist.iterdir():
        if path.is_dir():
            assert path.name == "bundles"


def test_fail_closed_pants_project_key(release_dist: Path) -> None:
    """pixi.project pants decoy key fails closed."""
    _ = release_dist
    pkg_path = APP / "pixi.project"
    original = pkg_path.read_text(encoding="utf-8")
    data = json.loads(original)
    data["pants"] = data.pop("pixi")
    broken = json.dumps(data, indent=2) + "\n"
    _fail_closed_with_sentinel(
        lambda: pkg_path.write_text(broken, encoding="utf-8"),
        lambda: pkg_path.write_text(original, encoding="utf-8"),
        pkg_path,
        broken,
    )


def test_licenses_byte_rule(release_dist: Path) -> None:
    """Each bundle LICENSES.txt matches sorted raw license files + extra newline each."""
    expected = b""
    for path in sorted((APP / "licenses").iterdir(), key=lambda p: p.name):
        if path.is_file():
            expected += path.read_bytes() + bytes([10])
    assert b"Apache" in expected or b"MIT" in expected or len(expected) > 16
    for row in matrix_rows():
        got = (release_dist / "bundles" / f"pixilock-{row['lane']}" / "LICENSES.txt").read_bytes()
        assert got == expected


def test_protected_risk_policy_unchanged(release_dist: Path) -> None:
    """risk-policy.csv must match verifier baseline after release."""
    _ = release_dist
    ensure_baseline_cache()
    assert sha256(APP / "config" / "risk-policy.csv") == sha256(BASE / "risk-policy.csv")


def test_fail_closed_risk_policy_zero(release_dist: Path) -> None:
    """Zero risk in risk-policy.csv fails closed at release validation."""
    _ = release_dist
    path = APP / "config" / "risk-policy.csv"
    original = path.read_text(encoding="utf-8")
    lines = []
    for ln in original.splitlines():
        if ln.startswith("ban,"):
            lines.append("ban,0")
        else:
            lines.append(ln)
    broken = chr(10).join(lines) + chr(10)
    _fail_closed_with_sentinel(
        lambda: path.write_text(broken, encoding="utf-8"),
        lambda: path.write_text(original, encoding="utf-8"),
        path,
        broken,
    )


def test_decoy_lane_policy_not_copied(release_dist: Path) -> None:
    """share/lane-policy must match matrix hops, not config/lanes decoy JSON."""
    for row in matrix_rows():
        lane = row["lane"]
        decoy = APP / "config" / "lanes" / f"{lane}.json"
        if not decoy.is_file():
            continue
        decoy_hops = json.loads(decoy.read_text(encoding="utf-8"))["retention_hops"]
        matrix_hops = int(row["retention_hops"])
        assert decoy_hops != matrix_hops, f"{lane} decoy should disagree with matrix"
        policy = json.loads(
            (release_dist / "bundles" / f"pixilock-{lane}" / "share" / "lane-policy.json").read_text(
                encoding="utf-8"
            )
        )
        assert policy == {"lane": lane, "retention_hops": matrix_hops}


def _stage_inspect_inputs(dest: Path) -> None:
    """Copy live app graph/config CSVs into an independent temp directory."""
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(APP / "data" / "graphs" / "edges.csv", dest / "edges.csv")
    shutil.copy(APP / "data" / "graphs" / "artifacts.csv", dest / "artifacts.csv")
    shutil.copy(APP / "config" / "deps.csv", dest / "deps.csv")
    for name in [
        "xor.csv",
        "mirrors.csv",
        "pins.csv",
        "bans.csv",
        "forbidden-hosts.csv",
        "version-caps.csv",
        "risk-policy.csv",
        "cascade-policy.csv",
        "cascade-route-blocks.csv",
    ]:
        shutil.copy(APP / "config" / name, dest / name)


def _run_inspect(binary: Path, work: Path, lane: str, hops: int, out: Path) -> dict:
    subprocess.run(
        [
            str(binary),
            "inspect",
            "--lane",
            lane,
            "--edges",
            str(work / "edges.csv"),
            "--artifacts",
            str(work / "artifacts.csv"),
            "--deps",
            str(work / "deps.csv"),
            "--mirrors",
            str(work / "mirrors.csv"),
            "--pins",
            str(work / "pins.csv"),
            "--xor",
            str(work / "xor.csv"),
            "--bans",
            str(work / "bans.csv"),
            "--forbidden-hosts",
            str(work / "forbidden-hosts.csv"),
            "--version-caps",
            str(work / "version-caps.csv"),
            "--risk-policy",
            str(work / "risk-policy.csv"),
            "--cascade-policy",
            str(work / "cascade-policy.csv"),
            "--cascade-route-blocks",
            str(work / "cascade-route-blocks.csv"),
            "--retention-hops",
            str(hops),
            "--out",
            str(out),
        ],
        check=True,
        timeout=120,
    )
    return json.loads(out.read_text(encoding="utf-8"))


def test_gate_xor_prefix_decay(release_dist: Path) -> None:
    """Gate XOR cascades use selected-lane xor decay; relay:b route-block stops expansion."""
    preview = json.loads(
        (release_dist / "bundles" / "pixilock-gate" / "share" / "inspect-preview.json").read_text(
            encoding="utf-8"
        )
    )
    by = {a["coordinate"]: a for a in preview["artifacts"]}
    assert "xor:json-codec:json|jsonalt" in by["dep:jsonA"]["holds"]
    assert "cascade:1:dep:jsonA@-:xor:json-codec:json|jsonalt" in by["relay:a"]["holds"]
    assert "cascade:1:dep:jsonA@-:xor:json-codec:json|jsonalt" in by["relay:b"]["holds"]
    assert "cascade:2:dep:jsonA@relay:a:xor:json-codec:json|jsonalt" in by["gw:edge"]["holds"]
    assert "cascade:2:dep:jsonA@relay:b:xor:json-codec:json|jsonalt" not in by["gw:edge"]["holds"]
    xor_decay = {
        r["prefix"]: int(r["decay"])
        for r in csv.DictReader((APP / "config" / "cascade-policy.csv").open(encoding="utf-8"))
        if r["lane"] == "gate"
    }["xor"]
    xor_risk = {
        r["kind"]: int(r["risk"])
        for r in csv.DictReader((APP / "config" / "risk-policy.csv").open(encoding="utf-8"))
    }["xor"]
    xor_risks = {}
    for art in preview["artifacts"]:
        for h in art["holds"]:
            if h.startswith("cascade:") and h.endswith(":xor:json-codec:json|jsonalt"):
                d = int(h.split(":", 2)[1])
                xor_risks[art["coordinate"]] = max(1, xor_risk - xor_decay * d)
    assert xor_risks["relay:a"] == max(1, xor_risk - xor_decay)
    assert xor_risks["gw:edge"] == max(1, xor_risk - xor_decay * 2)


def test_inspect_direct_on_mutated_csvs(release_dist: Path, tmp_path: Path) -> None:
    """pixilock inspect must evaluate verifier-generated CSV mutations, not only packaged previews."""
    binary = release_dist / "bundles" / "pixilock-edge" / "bin" / "pixilock"
    assert binary.is_file()
    work = tmp_path / "mutated-edge"
    _stage_inspect_inputs(work)
    deps_path = work / "deps.csv"
    rows = list(csv.DictReader(deps_path.open(encoding="utf-8")))
    fieldnames = list(rows[0].keys())
    for row in rows:
        if row["lane"] == "edge" and row["coordinate"] == "dep:fmt":
            row["source_hash"] = "sha256:" + ("a" * 64)
        if row["lane"] == "edge" and row["coordinate"] == "dep:zlib":
            row["source_hash"] = PIN_DIGESTS["zlib"][1]
        if row["lane"] == "edge" and row["coordinate"] == "dep:legacy":
            row["source_url"] = "https://evil.example/legacy.conda"
    with deps_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    out = tmp_path / "mutated-preview.json"
    hops = 2
    got = _run_inspect(binary, work, "edge", hops, out)
    assert got["lane"] == "edge"
    assert set(got) == {"lane", "retention_hops", "artifacts", "totals"}
    expected = expected_inspect("edge", hops, data_dir=work)
    assert got == expected
    by = {a["coordinate"]: a for a in got["artifacts"]}
    bad = "a" * 64
    good = PIN_DIGESTS["fmt"][1]
    assert f"hashdrift:dep:fmt:{good}:{bad}" in by["dep:fmt"]["holds"]
    assert not any(h.startswith("hashdrift:dep:zlib:") for h in by["dep:zlib"]["holds"])
    assert "remote:dep:legacy:source" in by["dep:legacy"]["holds"]


def test_inspect_direct_gate_xor_mutation(release_dist: Path, tmp_path: Path) -> None:
    """Mutating gate xor.csv must change inspect output (no stale packaged preview)."""
    binary = release_dist / "bundles" / "pixilock-gate" / "bin" / "pixilock"
    work = tmp_path / "mutated-gate"
    _stage_inspect_inputs(work)
    xor_path = work / "xor.csv"
    # drop jsonalt so xor group collapses
    rows = [
        r
        for r in csv.DictReader(xor_path.open(encoding="utf-8"))
        if not (r["lane"] == "gate" and r["provide"] == "jsonalt")
    ]
    fieldnames = ["lane", "group", "provide"]
    with xor_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    out = tmp_path / "gate-mut.json"
    got = _run_inspect(binary, work, "gate", 3, out)
    expected = expected_inspect("gate", 3, data_dir=work)
    assert got == expected
    by = {a["coordinate"]: a for a in got["artifacts"]}
    assert not any(h.startswith("xor:json-codec:") for h in by["dep:jsonA"]["holds"])


def test_protected_csvs_unchanged(release_dist: Path) -> None:
    """Protected matrix/graph/policy CSVs must match verifier baselines after release."""
    _ = release_dist
    ensure_baseline_cache()
    assert sha256(APP / "config" / "release_matrix.csv") == sha256(BASE / "release_matrix.csv")
    assert sha256(APP / "data" / "graphs" / "artifacts.csv") == sha256(BASE / "artifacts.csv")
    assert sha256(APP / "data" / "graphs" / "edges.csv") == sha256(BASE / "edges.csv")
    assert sha256(APP / "config" / "version-caps.csv") == sha256(BASE / "version-caps.csv")
    assert sha256(APP / "config" / "pins.csv") == sha256(BASE / "pins.csv")
    assert sha256(APP / "config" / "risk-policy.csv") == sha256(BASE / "risk-policy.csv")
    assert sha256(APP / "config" / "cascade-policy.csv") == sha256(BASE / "cascade-policy.csv")
    assert sha256(APP / "config" / "cascade-route-blocks.csv") == sha256(
        BASE / "cascade-route-blocks.csv"
    )
    assert sha256(APP / "config" / "xor.csv") == sha256(BASE / "xor.csv")


def test_inspect_totals_full_key_set(release_dist: Path) -> None:
    """Inspect totals expose the full counter key set."""
    preview = json.loads(
        (release_dist / "bundles" / "pixilock-edge" / "share" / "inspect-preview.json").read_text(
            encoding="utf-8"
        )
    )
    assert set(preview["totals"]) == {
        "release",
        "hold",
        "remotes",
        "hashdrifts",
        "versiondrifts",
        "mirrormisses",
        "provcollides",
        "xors",
        "missingpins",
        "bans",
        "caps",
        "cascades",
        "risk_score_total",
    }


def test_cap_hold_order_version_before_max(release_dist: Path) -> None:
    """Cap holds use cap:<coord>:<version>:<max> ordering."""
    preview = json.loads(
        (release_dist / "bundles" / "pixilock-edge" / "share" / "inspect-preview.json").read_text(
            encoding="utf-8"
        )
    )
    by = {a["coordinate"]: a for a in preview["artifacts"]}
    assert "cap:dep:legacy:0.1.0:0.0.9" in by["dep:legacy"]["holds"]


def test_fail_closed_packaging(release_dist: Path) -> None:
    """Non-conda packaging fails closed and preserves dist."""
    _ = release_dist
    pin = APP / "conda" / "deps" / "zlib.json"
    original = pin.read_text(encoding="utf-8")
    data = json.loads(original)
    data["packaging"] = "tar.gz"
    broken = json.dumps(data, indent=2) + "\n"
    _fail_closed_with_sentinel(
        lambda: pin.write_text(broken, encoding="utf-8"),
        lambda: pin.write_text(original, encoding="utf-8"),
        pin,
        broken,
    )


def test_fail_closed_missing_packaging(release_dist: Path) -> None:
    """Omitting packaging fails closed."""
    _ = release_dist
    pin = APP / "conda" / "deps" / "fmt.json"
    original = pin.read_text(encoding="utf-8")
    data = json.loads(original)
    data.pop("packaging", None)
    broken = json.dumps(data, indent=2) + "\n"
    _fail_closed_with_sentinel(
        lambda: pin.write_text(broken, encoding="utf-8"),
        lambda: pin.write_text(original, encoding="utf-8"),
        pin,
        broken,
    )


def test_fail_closed_patch_url(release_dist: Path) -> None:
    """Non-empty patch_url on a repaired row fails closed before dist clear."""
    _ = release_dist
    deps = APP / "config" / "deps.csv"
    original = deps.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    rewritten = []
    for raw in lines:
        out = raw
        if raw.startswith("edge,dep:fmt,"):
            parts = raw.rstrip("\n").rstrip("\r").split(",")
            parts[-1] = "https://evil.example/fmt.patch"
            out = ",".join(parts) + "\n"
        rewritten.append(out)
    broken = "".join(rewritten)
    assert broken != original
    _fail_closed_with_sentinel(
        lambda: deps.write_text(broken, encoding="utf-8"),
        lambda: deps.write_text(original, encoding="utf-8"),
        deps,
        broken,
    )


def test_fail_closed_pin_integrity(release_dist: Path) -> None:
    """Wrong conda/deps integrity fails closed even when archive bytes are correct."""
    _ = release_dist
    pin = APP / "conda" / "deps" / "fmt.json"
    original = pin.read_text(encoding="utf-8")
    broken = original.replace(PIN_DIGESTS["fmt"][1], "0" * 64)
    assert broken != original
    _fail_closed_with_sentinel(
        lambda: pin.write_text(broken, encoding="utf-8"),
        lambda: pin.write_text(original, encoding="utf-8"),
        pin,
        broken,
    )


def test_fail_closed_pin_https(release_dist: Path) -> None:
    """https resolved URL in pin fails closed."""
    _ = release_dist
    pin = APP / "conda" / "deps" / "zlib.json"
    original = pin.read_text(encoding="utf-8")
    data = json.loads(original)
    data["resolved"] = "https://example.invalid/zlib.conda"
    broken = json.dumps(data, indent=2) + "\n"
    _fail_closed_with_sentinel(
        lambda: pin.write_text(broken, encoding="utf-8"),
        lambda: pin.write_text(original, encoding="utf-8"),
        pin,
        broken,
    )


def test_fail_closed_bare_source_hash(release_dist: Path) -> None:
    """Bare hex source_hash on migrated legacy fails closed."""
    _ = release_dist
    deps = APP / "config" / "deps.csv"
    original = deps.read_text(encoding="utf-8")
    broken = original.replace(
        "sha256:8242c9efd58c3303245f10ccb28374af24fd96b7b1ff80f5326f14908d8f13dc",
        "8242c9efd58c3303245f10ccb28374af24fd96b7b1ff80f5326f14908d8f13dc",
        1,
    )
    assert broken != original
    _fail_closed_with_sentinel(
        lambda: deps.write_text(broken, encoding="utf-8"),
        lambda: deps.write_text(original, encoding="utf-8"),
        deps,
        broken,
    )


def test_fail_closed_pins_csv_sha256_prefix(release_dist: Path) -> None:
    """pins.csv sha256: prefix fails closed."""
    _ = release_dist
    path = APP / "config" / "pins.csv"
    original = path.read_text(encoding="utf-8")
    lines = []
    for ln in original.splitlines():
        if ln.startswith("fmt,"):
            parts = ln.split(",")
            parts[2] = "sha256:" + parts[2]
            lines.append(",".join(parts))
        else:
            lines.append(ln)
    broken = "\n".join(lines) + "\n"
    _fail_closed_with_sentinel(
        lambda: path.write_text(broken, encoding="utf-8"),
        lambda: path.write_text(original, encoding="utf-8"),
        path,
        broken,
    )


def test_fail_closed_spdlog_provide(release_dist: Path) -> None:
    """spdlog provide=fmt fails closed."""
    _ = release_dist
    deps = APP / "config" / "deps.csv"
    original = deps.read_text(encoding="utf-8")
    lines = []
    for ln in original.splitlines():
        if ",dep:spdlog," in ln:
            parts = ln.split(",")
            parts[2] = "fmt"
            lines.append(",".join(parts))
        else:
            lines.append(ln)
    broken = "\n".join(lines) + "\n"
    _fail_closed_with_sentinel(
        lambda: deps.write_text(broken, encoding="utf-8"),
        lambda: deps.write_text(original, encoding="utf-8"),
        deps,
        broken,
    )


def test_fail_closed_jsonB_provide(release_dist: Path) -> None:
    """gate jsonB provide=json fails closed."""
    _ = release_dist
    deps = APP / "config" / "deps.csv"
    original = deps.read_text(encoding="utf-8")
    lines = []
    for ln in original.splitlines():
        if ln.startswith("gate,dep:jsonB,"):
            parts = ln.split(",")
            parts[2] = "json"
            lines.append(",".join(parts))
        else:
            lines.append(ln)
    broken = "\n".join(lines) + "\n"
    _fail_closed_with_sentinel(
        lambda: deps.write_text(broken, encoding="utf-8"),
        lambda: deps.write_text(original, encoding="utf-8"),
        deps,
        broken,
    )


def test_fail_closed_jsonA_provide(release_dist: Path) -> None:
    """gate jsonA provide=jsonalt fails closed."""
    _ = release_dist
    deps = APP / "config" / "deps.csv"
    original = deps.read_text(encoding="utf-8")
    lines = []
    for ln in original.splitlines():
        if ln.startswith("gate,dep:jsonA,"):
            parts = ln.split(",")
            parts[2] = "jsonalt"
            lines.append(",".join(parts))
        else:
            lines.append(ln)
    broken = "\n".join(lines) + "\n"
    _fail_closed_with_sentinel(
        lambda: deps.write_text(broken, encoding="utf-8"),
        lambda: deps.write_text(original, encoding="utf-8"),
        deps,
        broken,
    )


def test_fail_closed_offline_pixiconfig(release_dist: Path) -> None:
    """offline=false fails closed."""
    _ = release_dist
    path = APP / "pixi.toml"
    original = path.read_text(encoding="utf-8")
    broken = "offline=false\ncache-dir=/app/pixi-cache\n"
    _fail_closed_with_sentinel(
        lambda: path.write_text(broken, encoding="utf-8"),
        lambda: path.write_text(original, encoding="utf-8"),
        path,
        broken,
    )


def test_fail_closed_cache_dir(release_dist: Path) -> None:
    """Wrong cache-dir fails closed."""
    _ = release_dist
    path = APP / "pixi.toml"
    original = path.read_text(encoding="utf-8")
    broken = "offline=true\ncache-dir=/var/empty\n"
    _fail_closed_with_sentinel(
        lambda: path.write_text(broken, encoding="utf-8"),
        lambda: path.write_text(original, encoding="utf-8"),
        path,
        broken,
    )


def test_fail_closed_legacy_notes(release_dist: Path) -> None:
    """Dirty legacy notes fail closed."""
    _ = release_dist
    path = APP / "legacy-pixi-notes.txt"
    original = path.read_text(encoding="utf-8")
    broken = "TODO still open\n"
    _fail_closed_with_sentinel(
        lambda: path.write_text(broken, encoding="utf-8"),
        lambda: path.write_text(original, encoding="utf-8"),
        path,
        broken,
    )


def test_fail_closed_lockfile_remote(release_dist: Path) -> None:
    """https in pixi.lock fails closed."""
    _ = release_dist
    path = APP / "pixi.lock"
    original = path.read_text(encoding="utf-8")
    broken = original + "\nhttps://evil.example/pkg\n"
    _fail_closed_with_sentinel(
        lambda: path.write_text(broken, encoding="utf-8"),
        lambda: path.write_text(original, encoding="utf-8"),
        path,
        broken,
    )


def test_fail_closed_lockfile_header(release_dist: Path) -> None:
    """Missing pixi lockfile v1 header fails closed."""
    _ = release_dist
    path = APP / "pixi.lock"
    original = path.read_text(encoding="utf-8")
    broken = original.replace("# pixi lockfile v1", "# pixi lockfile v2", 1)
    if broken == original:
        broken = original.replace("# pixi lockfile", "# other lockfile", 1)
    assert broken != original
    _fail_closed_with_sentinel(
        lambda: path.write_text(broken, encoding="utf-8"),
        lambda: path.write_text(original, encoding="utf-8"),
        path,
        broken,
    )


def test_fail_closed_cascade_policy_zero_decay(release_dist: Path) -> None:
    """cascade-policy edge ban with decay 0 is rejected; dist sentinel survives."""
    _ = release_dist
    policy = APP / "config" / "cascade-policy.csv"
    original = policy.read_text(encoding="utf-8")
    lines = []
    for ln in original.splitlines():
        if ln.startswith("edge,ban,"):
            parts = ln.split(",")
            parts[2] = "0"
            lines.append(",".join(parts))
        else:
            lines.append(ln)
    broken = "\n".join(lines) + "\n"
    _fail_closed_with_sentinel(
        lambda: policy.write_text(broken, encoding="utf-8"),
        lambda: policy.write_text(original, encoding="utf-8"),
        policy,
        broken,
    )


def test_fail_closed_duplicate_cascade_prefix(release_dist: Path) -> None:
    """Duplicate edge ban cascade-policy row fails closed; dist sentinel survives."""
    _ = release_dist
    policy = APP / "config" / "cascade-policy.csv"
    original = policy.read_text(encoding="utf-8")
    broken = original.rstrip("\n") + "\nedge,ban,12,3\n"
    _fail_closed_with_sentinel(
        lambda: policy.write_text(broken, encoding="utf-8"),
        lambda: policy.write_text(original, encoding="utf-8"),
        policy,
        broken,
    )


def test_decoy_nightly_not_packaged(release_dist: Path) -> None:
    assert not (release_dist / "bundles" / "pixilock-nightly").exists()


def test_report_exact_contract_keys(release_dist: Path) -> None:
    """pixi-report exposes the full public key set with boolean modes."""
    report = json.loads((release_dist / "pixi-report.json").read_text(encoding="utf-8"))
    assert set(report) == {
        "format_version",
        "deps",
        "legacy_cleared",
        "offline_pixi_mode",
        "cargo_packages",
    }
    assert report["format_version"] == 1
    assert report["legacy_cleared"] is True
    assert report["offline_pixi_mode"] is True
    assert [d["name"] for d in report["deps"]] == sorted(d["name"] for d in report["deps"])
    dep_keys = {"name", "provide", "version", "source_url", "source_hash", "mirror_ok"}
    for dep in report["deps"]:
        assert set(dep) == dep_keys, dep
        if dep["name"] in PIN_DIGESTS:
            assert dep["name"] == dep["provide"]


def test_inspect_direct_risk_policy_mutation(release_dist: Path, tmp_path: Path) -> None:
    """Mutating risk-policy ban score must change cascade attenuation (no hardcoded risks)."""
    binary = release_dist / "bundles" / "pixilock-edge" / "bin" / "pixilock"
    work = tmp_path / "risk-mut"
    _stage_inspect_inputs(work)
    risk_path = work / "risk-policy.csv"
    rows = list(csv.DictReader(risk_path.open(encoding="utf-8")))
    for row in rows:
        if row["kind"] == "ban":
            row["risk"] = "50"
    with risk_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["kind", "risk"])
        writer.writeheader()
        writer.writerows(rows)
    hops = 2
    got = _run_inspect(binary, work, "edge", hops, tmp_path / "risk-preview.json")
    expected = expected_inspect("edge", hops, data_dir=work)
    assert got == expected
    by = {a["coordinate"]: a for a in got["artifacts"]}
    assert "cascade:1:dep:legacy@-:ban:dep:legacy" in by["mid:alpha"]["holds"]
    protected_ban = {
        r["kind"]: int(r["risk"])
        for r in csv.DictReader((APP / "config" / "risk-policy.csv").open(encoding="utf-8"))
    }["ban"]
    decay = {
        r["prefix"]: int(r["decay"])
        for r in csv.DictReader((work / "cascade-policy.csv").open(encoding="utf-8"))
        if r["lane"] == "edge"
    }["ban"]
    assert max(1, 50 - decay) != max(1, protected_ban - decay)


def test_fail_closed_buck_project_key(release_dist: Path) -> None:
    """pixi.project buck decoy key fails closed."""
    _ = release_dist
    pkg_path = APP / "pixi.project"
    original = pkg_path.read_text(encoding="utf-8")
    data = json.loads(original)
    data["buck"] = data.pop("pixi")
    broken = json.dumps(data, indent=2) + "\n"
    _fail_closed_with_sentinel(
        lambda: pkg_path.write_text(broken, encoding="utf-8"),
        lambda: pkg_path.write_text(original, encoding="utf-8"),
        pkg_path,
        broken,
    )


def test_fail_closed_risk_policy_missing_kind(release_dist: Path) -> None:
    """Dropping a required risk-policy kind fails closed."""
    _ = release_dist
    path = APP / "config" / "risk-policy.csv"
    original = path.read_text(encoding="utf-8")
    lines = [ln for ln in original.splitlines() if not ln.startswith("xor,")]
    broken = "\n".join(lines) + "\n"
    assert broken != original
    _fail_closed_with_sentinel(
        lambda: path.write_text(broken, encoding="utf-8"),
        lambda: path.write_text(original, encoding="utf-8"),
        path,
        broken,
    )


def test_fail_closed_duplicate_route_block(release_dist: Path) -> None:
    """Duplicate cascade-route-blocks pair fails closed."""
    _ = release_dist
    path = APP / "config" / "cascade-route-blocks.csv"
    original = path.read_text(encoding="utf-8")
    broken = original.rstrip("\n") + "\nedge,ban,spine:\n"
    _fail_closed_with_sentinel(
        lambda: path.write_text(broken, encoding="utf-8"),
        lambda: path.write_text(original, encoding="utf-8"),
        path,
        broken,
    )


def test_fail_closed_cascade_policy_missing_prefix(release_dist: Path) -> None:
    """Removing an edge ban cascade-policy row fails closed (missing prefix)."""
    _ = release_dist
    path = APP / "config" / "cascade-policy.csv"
    original = path.read_text(encoding="utf-8")
    broken = "\n".join(ln for ln in original.splitlines() if not ln.startswith("edge,ban,")) + "\n"
    assert broken != original
    _fail_closed_with_sentinel(
        lambda: path.write_text(broken, encoding="utf-8"),
        lambda: path.write_text(original, encoding="utf-8"),
        path,
        broken,
    )


def test_fail_closed_cascade_policy_bad_headers(release_dist: Path) -> None:
    """cascade-policy.csv with a renamed header column fails closed."""
    _ = release_dist
    path = APP / "config" / "cascade-policy.csv"
    original = path.read_text(encoding="utf-8")
    broken = original.replace("lane,prefix,decay,max_hops", "lane,pfx,decay,max_hops", 1)
    assert broken != original
    _fail_closed_with_sentinel(
        lambda: path.write_text(broken, encoding="utf-8"),
        lambda: path.write_text(original, encoding="utf-8"),
        path,
        broken,
    )


def test_fail_closed_route_blocks_unknown_prefix(release_dist: Path) -> None:
    """cascade-route-blocks.csv with an unknown prefix fails closed."""
    _ = release_dist
    path = APP / "config" / "cascade-route-blocks.csv"
    original = path.read_text(encoding="utf-8")
    broken = original.rstrip("\n") + "\nedge,bogus,spine:\n"
    _fail_closed_with_sentinel(
        lambda: path.write_text(broken, encoding="utf-8"),
        lambda: path.write_text(original, encoding="utf-8"),
        path,
        broken,
    )


def test_fail_closed_route_blocks_empty_match(release_dist: Path) -> None:
    """cascade-route-blocks.csv with empty block_match fails closed."""
    _ = release_dist
    path = APP / "config" / "cascade-route-blocks.csv"
    original = path.read_text(encoding="utf-8")
    broken = original.rstrip("\n") + "\nedge,ban,\n"
    _fail_closed_with_sentinel(
        lambda: path.write_text(broken, encoding="utf-8"),
        lambda: path.write_text(original, encoding="utf-8"),
        path,
        broken,
    )


def test_fail_closed_archive_too_small(release_dist: Path) -> None:
    """Tiny stub archive fails closed even if digests are faked later."""
    _ = release_dist
    archive = APP / "pixi-cache" / "fmt-10.2.1.conda"
    original = archive.read_bytes()
    broken = b"tiny"
    _fail_closed_with_sentinel(
        lambda: archive.write_bytes(broken),
        lambda: archive.write_bytes(original),
        archive,
        broken,
    )


def test_lab_poison_stays_drifted(release_dist: Path) -> None:
    """Lab poison must remain drifted (hashdrift+versiondrift, no cascade at hops 0)."""
    preview = json.loads(
        (release_dist / "bundles" / "pixilock-lab" / "share" / "inspect-preview.json").read_text(
            encoding="utf-8"
        )
    )
    by = {a["coordinate"]: a for a in preview["artifacts"]}
    assert any(h.startswith("hashdrift:dep:poison:") for h in by["dep:poison"]["holds"])
    assert any(h.startswith("versiondrift:dep:poison:") for h in by["dep:poison"]["holds"])
    assert not any(h.startswith("cascade:") for a in preview["artifacts"] for h in a["holds"])


def test_pytest_not_cwd_shadowed() -> None:
    """Verify pytest loads from /opt/venv, not the shadow pytest.py in /app."""
    assert Path(pytest.__file__).resolve().is_relative_to(Path("/opt/venv").resolve())


def test_no_tmp_staging_in_release(release_dist: Path) -> None:
    """release.sh must not stage temps under /tmp (verifier /tmp may be unwritable)."""
    _ = release_dist
    text = (APP / "scripts" / "release.sh").read_text(encoding="utf-8")
    assert "mktemp" not in text
    assert "/tmp/" not in text
