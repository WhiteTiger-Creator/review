"""Private self-checks for the Python reference implementation.

These validate that `reference.planner` / `reference.models` faithfully
implement `/app/docs/cargo_recovery_profile.md` *before* the reference is
trusted to bootstrap mutated datasets (tests 18/21). They are intentionally
not exposed as pytest test functions; `run_self_checks()` is called once from
a session-scoped fixture in `test_outputs.py`.
"""

from __future__ import annotations

import random

from .canonical import sha256_hex
from .models import (
    BuildRequest,
    Dataset,
    DepSpec,
    LockPackage,
    Member,
    PatchedPackage,
    PatchEntry,
    PatchSet,
    Policy,
    PreviousLock,
    RegistryPackage,
    ReplacementMapping,
    ReplacementRecord,
    ReplacementSet,
    patch_set_digest_value,
    registry_source_digest,
    replacement_set_digest_value,
    workspace_digest_value,
)
from .planner import build_report, process_request
from .versions import Requirement, Version


def _policy(**overrides: int) -> Policy:
    base = {
        "maximum_packages": 64,
        "maximum_dependency_edges": 256,
        "maximum_resolution_rounds": 32,
        "maximum_requests": 16,
        "maximum_workspace_members_per_request": 8,
    }
    base.update(overrides)
    return Policy(**base)


def _empty_lock(lock_id: str = "lock-none") -> PreviousLock:
    return PreviousLock(lock_id, "0" * 64, "0" * 64, "0" * 64, [])


def _reg(
    name: str,
    version: str,
    *,
    rust_version: str = "1.0.0",
    yanked: bool = False,
    deps: list[DepSpec] | None = None,
) -> RegistryPackage:
    checksum = sha256_hex(f"{name}-{version}")
    return RegistryPackage(name, version, "crates-io", checksum, rust_version, yanked, deps or [])


def _req(
    request_id: str,
    member_ids: list[str],
    *,
    lock_id: str = "lock-none",
    patch_set_id: str = "ps-empty",
    replacement_set_id: str = "rs-empty",
    mode: str = "update",
) -> BuildRequest:
    return BuildRequest(request_id, lock_id, patch_set_id, replacement_set_id, mode, member_ids)


def _dataset(
    *,
    resolver_mode: str = "fallback",
    members: list[Member],
    registry: list[RegistryPackage],
    patched: list[PatchedPackage] | None = None,
    patch_sets: list[PatchSet] | None = None,
    replacement_sets: list[ReplacementSet] | None = None,
    previous_locks: list[PreviousLock] | None = None,
    build_requests: list[BuildRequest],
    policy: Policy | None = None,
) -> Dataset:
    patched = patched or []
    patch_sets = patch_sets or [PatchSet("ps-empty", [])]
    replacement_sets = replacement_sets or [ReplacementSet("rs-empty", [], [])]
    previous_locks = previous_locks if previous_locks is not None else [_empty_lock()]
    ds = Dataset(
        "self-check-ws",
        resolver_mode,
        members,
        registry,
        patched,
        patch_sets,
        replacement_sets,
        previous_locks,
        build_requests,
        policy or _policy(),
    )
    ds.workspace_digest = workspace_digest_value(ds.workspace_name, ds.resolver_mode, ds.members)
    ds.patch_digests = {p.patch_set_id: patch_set_digest_value(p) for p in patch_sets}
    ds.replacement_digests = {
        r.replacement_set_id: replacement_set_digest_value(r) for r in replacement_sets
    }
    return ds


def check_caret_upper_bounds() -> None:
    """All three caret upper-bound families and exact matching are correct."""
    big = Requirement.parse("^1.4.2")
    assert not big.matches(Version.parse("1.4.1"))
    assert big.matches(Version.parse("1.4.2"))
    assert big.matches(Version.parse("1.9.9"))
    assert not big.matches(Version.parse("2.0.0"))

    mid = Requirement.parse("^0.3.1")
    assert not mid.matches(Version.parse("0.3.0"))
    assert mid.matches(Version.parse("0.3.9"))
    assert not mid.matches(Version.parse("0.4.0"))

    tiny = Requirement.parse("^0.0.5")
    assert tiny.matches(Version.parse("0.0.5"))
    assert not tiny.matches(Version.parse("0.0.4"))
    assert not tiny.matches(Version.parse("0.0.6"))

    exact = Requirement.parse("=2.3.4")
    assert exact.matches(Version.parse("2.3.4"))
    assert not exact.matches(Version.parse("2.3.5"))


def check_fixed_point_convergence() -> None:
    """A transitively introduced exact requirement re-tightens an already
    selected package across resolution rounds."""
    members = [
        Member(
            "mem",
            "root",
            "0.1.0",
            "1.0.0",
            [DepSpec("top", "crates-io", "^1.0.0"), DepSpec("shared", "crates-io", "^1.0.0")],
        )
    ]
    registry = [
        RegistryPackage(
            "top",
            "1.0.0",
            "crates-io",
            sha256_hex("top-1.0.0"),
            "1.0.0",
            False,
            [DepSpec("shared", "crates-io", "=1.2.0")],
        ),
        _reg("shared", "1.0.0"),
        _reg("shared", "1.2.0"),
        _reg("shared", "1.5.0"),
    ]
    req = _req("req", ["mem"])
    ds = _dataset(resolver_mode="allow", members=members, registry=registry, build_requests=[req])
    result = process_request(ds, req)
    assert result.status == "accepted"
    assert result.selected["shared"].candidate.version == "1.2.0"


def check_existing_lock_preference() -> None:
    """A still-valid locked candidate wins over a numerically greater one."""
    members = [Member("mem", "root", "0.1.0", "1.90.0", [DepSpec("pkgl", "crates-io", "^1.0.0")])]
    registry = [_reg("pkgl", v) for v in ("1.0.0", "1.1.0", "1.2.0")]
    src_digest = registry_source_digest("pkgl", "1.1.0", "crates-io", sha256_hex("pkgl-1.1.0"))
    lock_pkg = LockPackage(
        "pkgl", "1.1.0", "registry", "crates-io", src_digest, sha256_hex("pkgl-1.1.0"), []
    )
    lock = PreviousLock("lock-pref", "0" * 64, "0" * 64, "0" * 64, [lock_pkg])
    req = _req("req", ["mem"], lock_id="lock-pref")
    ds = _dataset(members=members, registry=registry, previous_locks=[lock], build_requests=[req])
    result = process_request(ds, req)
    assert result.status == "accepted"
    assert result.selected["pkgl"].candidate.version == "1.1.0"


def check_locked_yanked_eligibility_and_exclusion() -> None:
    """A yanked candidate is eligible only via the selected prior lock."""
    members = [Member("mem", "root", "0.1.0", "1.0.0", [DepSpec("yp", "crates-io", "^1.0.0")])]
    registry = [_reg("yp", "1.0.0"), _reg("yp", "1.1.0", yanked=True)]
    src_digest = registry_source_digest("yp", "1.1.0", "crates-io", sha256_hex("yp-1.1.0"))
    lock_pkg = LockPackage(
        "yp", "1.1.0", "registry", "crates-io", src_digest, sha256_hex("yp-1.1.0"), []
    )
    lock = PreviousLock("lock-yp", "0" * 64, "0" * 64, "0" * 64, [lock_pkg])

    req_locked = _req("req-locked", ["mem"], lock_id="lock-yp")
    ds_locked = _dataset(
        members=members, registry=registry, previous_locks=[lock], build_requests=[req_locked]
    )
    result_locked = process_request(ds_locked, req_locked)
    assert result_locked.status == "accepted"
    assert result_locked.selected["yp"].candidate.version == "1.1.0"

    req_unlocked = _req("req-unlocked", ["mem"])
    ds_unlocked = _dataset(members=members, registry=registry, build_requests=[req_unlocked])
    result_unlocked = process_request(ds_unlocked, req_unlocked)
    assert result_unlocked.status == "accepted"
    assert result_unlocked.selected["yp"].candidate.version == "1.0.0"


def check_patch_same_version_replacement_and_unused_projection() -> None:
    """A same-version patch fully replaces the registry candidate; a valid
    patch excluded by resolution is projected as unused, not rejected."""
    members = [
        Member(
            "mem",
            "root",
            "0.1.0",
            "1.0.0",
            [DepSpec("pkgq", "crates-io", "^1.0.0"), DepSpec("pkgr", "crates-io", "=1.0.0")],
        )
    ]
    registry = [
        _reg("pkgq", "1.0.0"),
        _reg("pkgq", "2.0.0"),
        _reg("pkgr", "1.0.0"),
        _reg("pkgr", "5.0.0"),
    ]
    patched = [
        PatchedPackage(
            "pp-q",
            "pkgq",
            "1.0.0",
            "crates-io",
            "path_snapshot",
            "path+file:///q",
            sha256_hex("patched-q"),
            "1.0.0",
            [],
        ),
        PatchedPackage(
            "pp-r",
            "pkgr",
            "5.0.0",
            "crates-io",
            "path_snapshot",
            "path+file:///r",
            sha256_hex("patched-r"),
            "1.0.0",
            [],
        ),
    ]
    patch_set = PatchSet(
        "ps-mixed",
        [PatchEntry("crates-io", "pkgq", "pp-q"), PatchEntry("crates-io", "pkgr", "pp-r")],
    )
    req = _req("req", ["mem"], patch_set_id="ps-mixed")
    ds = _dataset(
        members=members,
        registry=registry,
        patched=patched,
        patch_sets=[patch_set],
        build_requests=[req],
    )
    result = process_request(ds, req)
    assert result.status == "accepted"
    assert result.selected["pkgq"].candidate.origin == "patched"
    assert result.selected["pkgq"].candidate.version == "1.0.0"
    assert result.selected["pkgr"].candidate.origin == "registry"
    by_pkg = {row["package_name"]: row for row in result.patch_rows}
    assert by_pkg["pkgq"]["status"] == "selected"
    assert by_pkg["pkgr"]["status"] == "unused"
    assert by_pkg["pkgr"]["reason_or_null"] is None


def check_replacement_checksum_equivalence() -> None:
    """An identical-checksum replacement record projects `equivalent` and
    leaves the selected version unchanged, only rewriting the source."""
    members = [Member("mem", "root", "0.1.0", "1.0.0", [DepSpec("pkge", "crates-io", "=1.0.0")])]
    checksum = sha256_hex("pkge-1.0.0")
    registry = [RegistryPackage("pkge", "1.0.0", "crates-io", checksum, "1.0.0", False, [])]
    replacement_set = ReplacementSet(
        "rs-e",
        [ReplacementMapping("crates-io", "mirror")],
        [ReplacementRecord("mirror", "pkge", "1.0.0", checksum, "sparse+file:///mirror/pkge")],
    )
    req = _req("req", ["mem"], replacement_set_id="rs-e")
    ds = _dataset(
        members=members,
        registry=registry,
        replacement_sets=[replacement_set],
        build_requests=[req],
    )
    result = process_request(ds, req)
    assert result.status == "accepted"
    assert result.selected["pkge"].candidate.version == "1.0.0"
    assert result.selected["pkge"].selection_source == "replacement_registry"
    row = result.replacement_rows[0]
    assert row["status"] == "equivalent"
    assert row["replacement_checksum_or_null"] == row["original_checksum"]


def check_allow_versus_fallback_msrv() -> None:
    """`allow` always takes the greatest candidate; `fallback` prefers the
    greatest MSRV-compatible one when any exists."""
    members = [Member("mem", "root", "0.1.0", "1.70.0", [DepSpec("helper", "crates-io", "^1.0.0")])]
    registry = [
        _reg("helper", "1.0.0", rust_version="1.55.0"),
        _reg("helper", "1.1.0", rust_version="1.65.0"),
        _reg("helper", "1.2.0", rust_version="1.90.0"),
    ]
    req = _req("req", ["mem"])

    ds_allow = _dataset(
        resolver_mode="allow", members=members, registry=registry, build_requests=[req]
    )
    result_allow = process_request(ds_allow, req)
    assert result_allow.selected["helper"].candidate.version == "1.2.0"

    ds_fallback = _dataset(
        resolver_mode="fallback", members=members, registry=registry, build_requests=[req]
    )
    result_fallback = process_request(ds_fallback, req)
    assert result_fallback.selected["helper"].candidate.version == "1.1.0"


def check_transitive_invalidation_locality() -> None:
    """Invalidating a leaf package invalidates only its reverse dependents,
    not unrelated selected packages in the same request."""
    members = [
        Member(
            "mem",
            "root",
            "0.1.0",
            "1.0.0",
            [DepSpec("pkgc", "crates-io", "^1.0.0"), DepSpec("pkgd", "crates-io", "^1.0.0")],
        )
    ]

    def make_registry(pkgb_checksum: str) -> list[RegistryPackage]:
        return [
            RegistryPackage(
                "pkgc",
                "1.0.0",
                "crates-io",
                sha256_hex("pkgc-1.0.0"),
                "1.0.0",
                False,
                [DepSpec("pkgb", "crates-io", "^1.0.0")],
            ),
            RegistryPackage("pkgb", "1.0.0", "crates-io", pkgb_checksum, "1.0.0", False, []),
            _reg("pkgd", "1.0.0"),
        ]

    original_checksum = sha256_hex("pkgb-1.0.0")
    baseline_req = _req("req", ["mem"])
    ds0 = _dataset(
        members=members, registry=make_registry(original_checksum), build_requests=[baseline_req]
    )
    baseline_result = process_request(ds0, ds0.build_requests[0])
    assert baseline_result.status == "accepted"

    lock_packages = []
    for name, sel in baseline_result.selected.items():
        dep_names = sorted({d.package_name for d in sel.candidate.dependencies})
        lock_packages.append(
            LockPackage(
                name,
                sel.candidate.version,
                sel.selection_source,
                sel.source_reference,
                sel.source_digest,
                sel.checksum,
                dep_names,
            )
        )
    lock = PreviousLock(
        "lock-real",
        ds0.workspace_digest,
        ds0.patch_digests["ps-empty"],
        ds0.replacement_digests["rs-empty"],
        lock_packages,
    )
    req = _req("req", ["mem"], lock_id="lock-real")
    ds1 = _dataset(
        members=members,
        registry=make_registry(original_checksum),
        previous_locks=[lock],
        build_requests=[req],
    )
    reused_result = process_request(ds1, req)
    assert all(sel.lock_status == "reused" for sel in reused_result.selected.values())

    mutated_checksum = sha256_hex("pkgb-1.0.0-mutated")
    ds2 = _dataset(
        members=members,
        registry=make_registry(mutated_checksum),
        previous_locks=[lock],
        build_requests=[req],
    )
    mutated_result = process_request(ds2, req)
    assert mutated_result.selected["pkgb"].lock_status == "recomputed"
    assert mutated_result.selected["pkgc"].lock_status == "recomputed"
    assert mutated_result.selected["pkgd"].lock_status == "reused"


def check_frozen_versus_update() -> None:
    """`frozen` rejects a stale required lock entry; `update` recomputes and
    accepts under the same stale input."""
    members = [Member("mem", "root", "0.1.0", "1.0.0", [DepSpec("pkgf", "crates-io", "^1.0.0")])]
    registry = [_reg("pkgf", "1.0.0")]
    stale_lock_pkg = LockPackage(
        "pkgf",
        "1.0.0",
        "registry",
        "crates-io",
        sha256_hex("stale-digest"),
        sha256_hex("pkgf-1.0.0"),
        [],
    )
    stale_lock = PreviousLock("lock-stale", "0" * 64, "0" * 64, "0" * 64, [stale_lock_pkg])

    req_frozen = _req("req-frozen", ["mem"], lock_id="lock-stale", mode="frozen")
    ds_frozen = _dataset(
        members=members, registry=registry, previous_locks=[stale_lock], build_requests=[req_frozen]
    )
    result_frozen = process_request(ds_frozen, req_frozen)
    assert result_frozen.status == "rejected"
    assert result_frozen.reason_or_null == "lockfile_stale"

    req_update = _req("req-update", ["mem"], lock_id="lock-stale")
    ds_update = _dataset(
        members=members, registry=registry, previous_locks=[stale_lock], build_requests=[req_update]
    )
    result_update = process_request(ds_update, req_update)
    assert result_update.status == "accepted"
    assert result_update.selected["pkgf"].lock_status == "recomputed"


def check_five_seed_invariance() -> None:
    """Reordering members/registry/dependencies must not change selections,
    across five independent shuffle seeds."""
    base_members = [
        Member(
            "mem-a",
            "app-a",
            "0.1.0",
            "1.0.0",
            [DepSpec("pkgx", "crates-io", "^1.0.0"), DepSpec("pkgy", "crates-io", "^1.0.0")],
        ),
        Member("mem-b", "app-b", "0.1.0", "1.0.0", [DepSpec("pkgx", "crates-io", "^1.1.0")]),
    ]
    base_registry = [
        _reg("pkgx", "1.0.0"),
        _reg("pkgx", "1.1.0"),
        RegistryPackage(
            "pkgy",
            "1.0.0",
            "crates-io",
            sha256_hex("pkgy-1.0.0"),
            "1.0.0",
            False,
            [DepSpec("pkgx", "crates-io", "^1.0.0")],
        ),
    ]
    req = _req("req", ["mem-a", "mem-b"])
    ds_baseline = _dataset(members=base_members, registry=base_registry, build_requests=[req])
    baseline = build_report(ds_baseline)

    for seed in (7, 19, 41, 83, 127):
        rng = random.Random(seed)
        members = [
            Member(
                m.member_id,
                m.package_name,
                m.package_version,
                m.rust_version,
                list(m.dependencies),
            )
            for m in base_members
        ]
        for m in members:
            rng.shuffle(m.dependencies)
        rng.shuffle(members)
        registry = list(base_registry)
        rng.shuffle(registry)
        req_seed = _req("req", ["mem-a", "mem-b"])
        ds_seed = _dataset(members=members, registry=registry, build_requests=[req_seed])
        report = build_report(ds_seed)
        assert report["package_selection_rows"] == baseline["package_selection_rows"], seed
        assert report["request_rows"] == baseline["request_rows"], seed


def check_summary_recomputation() -> None:
    """`summary` fields are exactly derived from the emitted row families."""
    members = [
        Member("mem-a", "app-a", "0.1.0", "1.0.0", [DepSpec("pkgok", "crates-io", "^1.0.0")]),
        Member("mem-b", "app-b", "0.1.0", "1.0.0", [DepSpec("missing-req", "crates-io", "=9.9.9")]),
    ]
    registry = [_reg("pkgok", "1.0.0")]
    req_ok = _req("req-ok", ["mem-a"])
    req_bad = _req("req-bad", ["mem-b"])
    ds = _dataset(members=members, registry=registry, build_requests=[req_ok, req_bad])
    report = build_report(ds)
    summary = report["summary"]

    assert summary["request_count"] == len(report["request_rows"]) == 2
    assert summary["accepted_request_count"] == sum(
        1 for r in report["request_rows"] if r["status"] == "accepted"
    )
    assert summary["rejected_request_count"] == sum(
        1 for r in report["request_rows"] if r["status"] == "rejected"
    )
    assert summary["accepted_request_count"] == 1
    assert summary["rejected_request_count"] == 1
    assert summary["package_selection_row_count"] == len(report["package_selection_rows"])
    assert summary["selected_patch_count"] == sum(
        1 for r in report["patch_rows"] if r["status"] == "selected"
    )
    assert summary["replacement_row_count"] == len(report["source_replacement_rows"])
    assert summary["reused_lock_entry_count"] == sum(
        1 for r in report["lock_entry_rows"] if r["status"] == "reused"
    )
    assert summary["recomputed_lock_entry_count"] == sum(
        1 for r in report["lock_entry_rows"] if r["status"] == "recomputed"
    )
    assert summary["conflict_count"] == len(report["conflict_rows"])


_ALL_CHECKS = (
    check_caret_upper_bounds,
    check_fixed_point_convergence,
    check_existing_lock_preference,
    check_locked_yanked_eligibility_and_exclusion,
    check_patch_same_version_replacement_and_unused_projection,
    check_replacement_checksum_equivalence,
    check_allow_versus_fallback_msrv,
    check_transitive_invalidation_locality,
    check_frozen_versus_update,
    check_five_seed_invariance,
    check_summary_recomputation,
)


def _invoke_check(check) -> None:
    try:
        check()
    except Exception as exc:
        raise AssertionError(f"reference self-check failed: {check.__name__}: {exc}") from exc


def run_self_checks() -> None:
    """Run every private reference self-check, raising on the first failure."""
    for check in _ALL_CHECKS:
        _invoke_check(check)
