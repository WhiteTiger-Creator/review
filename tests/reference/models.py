"""Load and validate the offline recovery cartridge."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .canonical import digest_of
from .versions import Requirement, Version, parse_sha256


class FatalError(Exception):
    """Whole-run fatal validation failure."""


@dataclass
class DepSpec:
    package_name: str
    source_id: str
    requirement: str


@dataclass
class Member:
    member_id: str
    package_name: str
    package_version: str
    rust_version: str
    dependencies: list[DepSpec]


@dataclass
class RegistryPackage:
    package_name: str
    version: str
    source_id: str
    checksum: str
    rust_version: str
    yanked: bool
    dependencies: list[DepSpec]


@dataclass
class PatchedPackage:
    patched_package_id: str
    package_name: str
    version: str
    patched_source_id: str
    source_kind: str
    source_reference: str
    source_digest: str
    rust_version: str
    dependencies: list[DepSpec]


@dataclass
class PatchEntry:
    source_id: str
    package_name: str
    patched_package_id: str


@dataclass
class PatchSet:
    patch_set_id: str
    patches: list[PatchEntry]


@dataclass
class ReplacementMapping:
    original_source_id: str
    replacement_source_id: str


@dataclass
class ReplacementRecord:
    replacement_source_id: str
    package_name: str
    version: str
    checksum: str
    source_reference: str


@dataclass
class ReplacementSet:
    replacement_set_id: str
    mappings: list[ReplacementMapping]
    replacement_records: list[ReplacementRecord]


@dataclass
class LockPackage:
    package_name: str
    version: str
    source_kind: str
    source_reference: str
    source_digest: str
    checksum: str
    dependency_names: list[str]


@dataclass
class PreviousLock:
    lock_id: str
    workspace_digest: str
    patch_set_digest: str
    replacement_set_digest: str
    selected_packages: list[LockPackage]


@dataclass
class BuildRequest:
    request_id: str
    lock_id: str
    patch_set_id: str
    replacement_set_id: str
    lockfile_mode: str
    member_ids: list[str]


@dataclass
class Policy:
    maximum_packages: int
    maximum_dependency_edges: int
    maximum_resolution_rounds: int
    maximum_requests: int
    maximum_workspace_members_per_request: int


@dataclass
class Dataset:
    workspace_name: str
    resolver_mode: str
    members: list[Member]
    registry_packages: list[RegistryPackage]
    patched_packages: list[PatchedPackage]
    patch_sets: list[PatchSet]
    replacement_sets: list[ReplacementSet]
    previous_locks: list[PreviousLock]
    build_requests: list[BuildRequest]
    policy: Policy
    workspace_digest: str = ""
    patch_digests: dict[str, str] = field(default_factory=dict)
    replacement_digests: dict[str, str] = field(default_factory=dict)


def _deps(raw: Any, ctx: str) -> list[DepSpec]:
    if not isinstance(raw, list):
        raise FatalError(f"{ctx}: dependencies must be array")
    out: list[DepSpec] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise FatalError(f"{ctx}: dependency {i} must be object")
        for key in ("package_name", "source_id", "requirement"):
            if key not in item or not isinstance(item[key], str):
                raise FatalError(f"{ctx}: dependency missing {key}")
        Requirement.parse(item["requirement"])
        name = item["package_name"]
        if name in seen:
            raise FatalError(f"{ctx}: duplicate dependency {name}")
        seen.add(name)
        out.append(DepSpec(name, item["source_id"], item["requirement"]))
    return out


def workspace_digest_value(workspace_name: str, resolver_mode: str, members: list[Member]) -> str:
    payload = {
        "members": [
            {
                "dependencies": [
                    {
                        "package_name": d.package_name,
                        "requirement": d.requirement,
                        "source_id": d.source_id,
                    }
                    for d in sorted(m.dependencies, key=lambda x: x.package_name)
                ],
                "member_id": m.member_id,
                "package_name": m.package_name,
                "package_version": m.package_version,
                "rust_version": m.rust_version,
            }
            for m in sorted(members, key=lambda x: x.member_id)
        ],
        "resolver_mode": resolver_mode,
        "workspace_name": workspace_name,
    }
    return digest_of(payload)


def patch_set_digest_value(ps: PatchSet) -> str:
    payload = {
        "patch_set_id": ps.patch_set_id,
        "patches": [
            {
                "package_name": p.package_name,
                "patched_package_id": p.patched_package_id,
                "source_id": p.source_id,
            }
            for p in sorted(
                ps.patches,
                key=lambda x: (x.source_id, x.package_name, x.patched_package_id),
            )
        ],
    }
    return digest_of(payload)


def replacement_set_digest_value(rs: ReplacementSet) -> str:
    payload = {
        "mappings": [
            {
                "original_source_id": m.original_source_id,
                "replacement_source_id": m.replacement_source_id,
            }
            for m in sorted(rs.mappings, key=lambda x: x.original_source_id)
        ],
        "replacement_records": [
            {
                "checksum": r.checksum,
                "package_name": r.package_name,
                "replacement_source_id": r.replacement_source_id,
                "source_reference": r.source_reference,
                "version": r.version,
            }
            for r in sorted(
                rs.replacement_records,
                key=lambda x: (
                    x.replacement_source_id,
                    x.package_name,
                    x.version,
                ),
            )
        ],
        "replacement_set_id": rs.replacement_set_id,
    }
    return digest_of(payload)


def registry_source_digest(package_name: str, version: str, source_id: str, checksum: str) -> str:
    return digest_of(
        {
            "checksum": checksum,
            "package_name": package_name,
            "source_id": source_id,
            "version": version,
        }
    )


def lock_package_digest(
    package_name: str,
    version: str,
    source_kind: str,
    source_reference: str,
    source_digest: str,
    checksum: str,
    dependency_names: list[str],
) -> str:
    return digest_of(
        {
            "checksum": checksum,
            "dependency_names": sorted(set(dependency_names)),
            "package_name": package_name,
            "source_digest": source_digest,
            "source_kind": source_kind,
            "source_reference": source_reference,
            "version": version,
        }
    )


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FatalError(f"unreadable json: {path.name}: {exc}") from exc


def load_dataset(data_dir: Path) -> Dataset:
    required = [
        "workspace.json",
        "registry_packages.json",
        "patched_packages.json",
        "patch_sets.json",
        "replacement_sources.json",
        "previous_locks.json",
        "build_requests.ndjson",
        "policy.json",
    ]
    for name in required:
        if not (data_dir / name).is_file():
            raise FatalError(f"missing required input file: {name}")

    ws_raw = _load_json(data_dir / "workspace.json")
    if not isinstance(ws_raw, dict):
        raise FatalError("workspace.json must be object")
    for key in ("workspace_name", "resolver_mode", "members"):
        if key not in ws_raw:
            raise FatalError(f"workspace.json missing {key}")
    if ws_raw["resolver_mode"] not in ("allow", "fallback"):
        raise FatalError("invalid resolver_mode")
    if not isinstance(ws_raw["members"], list):
        raise FatalError("members must be array")

    members: list[Member] = []
    member_ids: set[str] = set()
    for item in ws_raw["members"]:
        if not isinstance(item, dict):
            raise FatalError("member must be object")
        mid = item.get("member_id")
        if not isinstance(mid, str) or mid in member_ids:
            raise FatalError("duplicate or invalid member_id")
        member_ids.add(mid)
        Version.parse(item["package_version"])
        Version.parse(item["rust_version"])
        members.append(
            Member(
                mid,
                item["package_name"],
                item["package_version"],
                item["rust_version"],
                _deps(item.get("dependencies"), f"member {mid}"),
            )
        )

    reg_raw = _load_json(data_dir / "registry_packages.json")
    if not isinstance(reg_raw, list):
        raise FatalError("registry_packages.json must be array")
    registry: list[RegistryPackage] = []
    reg_ids: set[tuple[str, str, str]] = set()
    edge_count = 0
    for item in reg_raw:
        Version.parse(item["version"])
        Version.parse(item["rust_version"])
        checksum = parse_sha256(item["checksum"])
        key = (item["source_id"], item["package_name"], item["version"])
        if key in reg_ids:
            raise FatalError(f"duplicate registry package {key}")
        reg_ids.add(key)
        deps = _deps(item.get("dependencies"), f"registry {key}")
        edge_count += len(deps)
        registry.append(
            RegistryPackage(
                item["package_name"],
                item["version"],
                item["source_id"],
                checksum,
                item["rust_version"],
                bool(item["yanked"]),
                deps,
            )
        )

    pat_raw = _load_json(data_dir / "patched_packages.json")
    if not isinstance(pat_raw, list):
        raise FatalError("patched_packages.json must be array")
    patched: list[PatchedPackage] = []
    patched_ids: set[str] = set()
    for item in pat_raw:
        pid = item["patched_package_id"]
        if pid in patched_ids:
            raise FatalError(f"duplicate patched_package_id {pid}")
        patched_ids.add(pid)
        if item["source_kind"] not in ("path_snapshot", "git_snapshot"):
            raise FatalError("invalid source_kind")
        Version.parse(item["version"])
        Version.parse(item["rust_version"])
        parse_sha256(item["source_digest"])
        deps = _deps(item.get("dependencies"), f"patched {pid}")
        edge_count += len(deps)
        patched.append(
            PatchedPackage(
                pid,
                item["package_name"],
                item["version"],
                item["patched_source_id"],
                item["source_kind"],
                item["source_reference"],
                item["source_digest"],
                item["rust_version"],
                deps,
            )
        )

    ps_raw = _load_json(data_dir / "patch_sets.json")
    if not isinstance(ps_raw, list):
        raise FatalError("patch_sets.json must be array")
    patch_sets: list[PatchSet] = []
    ps_ids: set[str] = set()
    for item in ps_raw:
        sid = item["patch_set_id"]
        if sid in ps_ids:
            raise FatalError(f"duplicate patch_set_id {sid}")
        ps_ids.add(sid)
        patches = []
        for p in item.get("patches", []):
            if p["patched_package_id"] not in patched_ids:
                raise FatalError(f"unknown patched_package_id {p['patched_package_id']}")
            patches.append(PatchEntry(p["source_id"], p["package_name"], p["patched_package_id"]))
        patch_sets.append(PatchSet(sid, patches))

    rs_raw = _load_json(data_dir / "replacement_sources.json")
    if not isinstance(rs_raw, list):
        raise FatalError("replacement_sources.json must be array")
    replacement_sets: list[ReplacementSet] = []
    rs_ids: set[str] = set()
    for item in rs_raw:
        rid = item["replacement_set_id"]
        if rid in rs_ids:
            raise FatalError(f"duplicate replacement_set_id {rid}")
        rs_ids.add(rid)
        mappings = []
        seen_orig: set[str] = set()
        for m in item.get("mappings", []):
            if m["original_source_id"] in seen_orig:
                raise FatalError("duplicate original_source_id in replacement set")
            seen_orig.add(m["original_source_id"])
            mappings.append(ReplacementMapping(m["original_source_id"], m["replacement_source_id"]))
        records = []
        seen_rec: set[tuple[str, str, str]] = set()
        for r in item.get("replacement_records", []):
            key = (r["replacement_source_id"], r["package_name"], r["version"])
            if key in seen_rec:
                raise FatalError(f"duplicate replacement record {key}")
            seen_rec.add(key)
            Version.parse(r["version"])
            parse_sha256(r["checksum"])
            records.append(
                ReplacementRecord(
                    r["replacement_source_id"],
                    r["package_name"],
                    r["version"],
                    r["checksum"],
                    r["source_reference"],
                )
            )
        replacement_sets.append(ReplacementSet(rid, mappings, records))

    lock_raw = _load_json(data_dir / "previous_locks.json")
    if not isinstance(lock_raw, list):
        raise FatalError("previous_locks.json must be array")
    locks: list[PreviousLock] = []
    lock_ids: set[str] = set()
    for item in lock_raw:
        lid = item["lock_id"]
        if lid in lock_ids:
            raise FatalError(f"duplicate lock_id {lid}")
        lock_ids.add(lid)
        parse_sha256(item["workspace_digest"])
        parse_sha256(item["patch_set_digest"])
        parse_sha256(item["replacement_set_digest"])
        pkgs = []
        seen_pkg: set[str] = set()
        for p in item.get("selected_packages", []):
            if p["package_name"] in seen_pkg:
                raise FatalError("duplicate lock package")
            seen_pkg.add(p["package_name"])
            Version.parse(p["version"])
            parse_sha256(p["source_digest"])
            parse_sha256(p["checksum"])
            if p["source_kind"] not in (
                "registry",
                "patched_path",
                "patched_git_snapshot",
                "replacement_registry",
            ):
                raise FatalError("invalid lock source_kind")
            if not isinstance(p.get("dependency_names"), list):
                raise FatalError("dependency_names must be array")
            pkgs.append(
                LockPackage(
                    p["package_name"],
                    p["version"],
                    p["source_kind"],
                    p["source_reference"],
                    p["source_digest"],
                    p["checksum"],
                    list(p["dependency_names"]),
                )
            )
        locks.append(
            PreviousLock(
                lid,
                item["workspace_digest"],
                item["patch_set_digest"],
                item["replacement_set_digest"],
                pkgs,
            )
        )

    req_path = data_dir / "build_requests.ndjson"
    try:
        lines = req_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise FatalError(f"unreadable ndjson: {exc}") from exc
    requests: list[BuildRequest] = []
    req_ids: set[str] = set()
    for line_no, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FatalError(f"bad ndjson line {line_no}: {exc}") from exc
        if not isinstance(item, dict):
            raise FatalError(f"ndjson line {line_no} must be object")
        rid = item["request_id"]
        if rid in req_ids:
            raise FatalError(f"duplicate request_id {rid}")
        req_ids.add(rid)
        if item["lockfile_mode"] not in ("frozen", "update"):
            raise FatalError("invalid lockfile_mode")
        mids = item["member_ids"]
        if not isinstance(mids, list) or len(mids) != len(set(mids)):
            raise FatalError("member_ids must be unique array")
        requests.append(
            BuildRequest(
                rid,
                item["lock_id"],
                item["patch_set_id"],
                item["replacement_set_id"],
                item["lockfile_mode"],
                list(mids),
            )
        )

    pol_raw = _load_json(data_dir / "policy.json")
    if not isinstance(pol_raw, dict):
        raise FatalError("policy.json must be object")
    policy = Policy(
        int(pol_raw["maximum_packages"]),
        int(pol_raw["maximum_dependency_edges"]),
        int(pol_raw["maximum_resolution_rounds"]),
        int(pol_raw["maximum_requests"]),
        int(pol_raw["maximum_workspace_members_per_request"]),
    )

    member_edge_count = sum(len(m.dependencies) for m in members)
    total_edges = edge_count + member_edge_count
    if len(registry) + len(patched) > policy.maximum_packages:
        raise FatalError("policy maximum_packages exceeded")
    if total_edges > policy.maximum_dependency_edges:
        raise FatalError("policy maximum_dependency_edges exceeded")
    if len(requests) > policy.maximum_requests:
        raise FatalError("policy maximum_requests exceeded")
    for req in requests:
        if len(req.member_ids) > policy.maximum_workspace_members_per_request:
            raise FatalError("policy maximum_workspace_members_per_request exceeded")

    ds = Dataset(
        ws_raw["workspace_name"],
        ws_raw["resolver_mode"],
        members,
        registry,
        patched,
        patch_sets,
        replacement_sets,
        locks,
        requests,
        policy,
    )
    ds.workspace_digest = workspace_digest_value(ds.workspace_name, ds.resolver_mode, ds.members)
    ds.patch_digests = {p.patch_set_id: patch_set_digest_value(p) for p in patch_sets}
    ds.replacement_digests = {
        r.replacement_set_id: replacement_set_digest_value(r) for r in replacement_sets
    }
    return ds
