"""Independent Python reference planner for MSRV/patch/lock recovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import (
    Dataset,
    DepSpec,
    LockPackage,
    PatchedPackage,
    PreviousLock,
    lock_package_digest,
    registry_source_digest,
)
from .versions import Requirement, Version

REJECTION_ORDER = [
    "unknown_member",
    "unknown_lock",
    "unknown_patch_set",
    "unknown_replacement_set",
    "patch_conflict",
    "package_version_conflict",
    "resolution_round_limit",
    "source_replacement_missing",
    "source_replacement_mismatch",
    "lockfile_stale",
]


@dataclass
class Candidate:
    package_name: str
    version: str
    rust_version: str
    yanked: bool
    dependencies: list[DepSpec]
    origin: str  # registry | patched
    source_id: str
    source_kind: str
    source_reference: str
    source_digest: str
    checksum: str
    patched_package_id: str | None = None


@dataclass
class Selection:
    candidate: Candidate
    selection_source: str
    source_reference: str
    source_digest: str
    checksum: str
    lock_status: str
    locked_version_or_null: str | None


@dataclass
class RequestResult:
    request_id: str
    lockfile_mode: str
    resolver_mode: str
    request_msrv: str | None
    status: str
    reason_or_null: str | None
    selected: dict[str, Selection] = field(default_factory=dict)
    patch_rows: list[dict[str, Any]] = field(default_factory=list)
    replacement_rows: list[dict[str, Any]] = field(default_factory=list)
    lock_rows: list[dict[str, Any]] = field(default_factory=list)
    invalidation_rows: list[dict[str, Any]] = field(default_factory=list)
    conflict_rows: list[dict[str, Any]] = field(default_factory=list)
    reused: int = 0
    recomputed: int = 0


def _member_map(ds: Dataset) -> dict[str, Any]:
    return {m.member_id: m for m in ds.members}


def _lock_map(ds: Dataset) -> dict[str, PreviousLock]:
    return {lock.lock_id: lock for lock in ds.previous_locks}


def _patch_map(ds: Dataset) -> dict[str, Any]:
    return {p.patch_set_id: p for p in ds.patch_sets}


def _repl_map(ds: Dataset) -> dict[str, Any]:
    return {r.replacement_set_id: r for r in ds.replacement_sets}


def _patched_map(ds: Dataset) -> dict[str, PatchedPackage]:
    return {p.patched_package_id: p for p in ds.patched_packages}


def build_overlay_candidates(
    ds: Dataset, patch_set_id: str
) -> tuple[dict[str, list[Candidate]], list[dict[str, Any]], str | None]:
    """Return candidates by package name, patch projection rows shell, or conflict."""
    ps = _patch_map(ds)[patch_set_id]
    patched_by_id = _patched_map(ds)
    patch_rows: list[dict[str, Any]] = []
    # Map (source_id, name, version) -> patched candidate replacing registry
    replacements: dict[tuple[str, str, str], Candidate] = {}
    target_seen: dict[tuple[str, str, str], str] = {}

    conflict = False
    for entry in ps.patches:
        pp = patched_by_id[entry.patched_package_id]
        status = "unused"
        reason = None
        cand_key = None
        if pp.package_name != entry.package_name:
            status = "rejected"
            reason = "package_mismatch"
        elif pp.patched_source_id != entry.source_id:
            status = "rejected"
            reason = "source_mismatch"
        else:
            key = (entry.source_id, entry.package_name, pp.version)
            if key in target_seen:
                conflict = True
                status = "rejected"
                reason = "duplicate_target"
            else:
                target_seen[key] = entry.patched_package_id
                sk = "patched_path" if pp.source_kind == "path_snapshot" else "patched_git_snapshot"
                cand = Candidate(
                    pp.package_name,
                    pp.version,
                    pp.rust_version,
                    False,
                    list(pp.dependencies),
                    "patched",
                    entry.source_id,
                    sk,
                    pp.source_reference,
                    pp.source_digest,
                    pp.source_digest,
                    pp.patched_package_id,
                )
                replacements[key] = cand
                cand_key = key
        patch_rows.append(
            {
                "source_id": entry.source_id,
                "package_name": entry.package_name,
                "patched_package_id": entry.patched_package_id,
                "patched_version": pp.version,
                "status": status,
                "reason_or_null": reason,
                "_candidate_key": cand_key,
            }
        )
    if conflict:
        for row in patch_rows:
            if row["status"] != "rejected":
                row["status"] = "rejected"
                row["reason_or_null"] = "duplicate_target"
        return {}, patch_rows, "patch_conflict"

    by_name: dict[str, list[Candidate]] = {}
    for reg in ds.registry_packages:
        key = (reg.source_id, reg.package_name, reg.version)
        if key in replacements:
            cand = replacements[key]
        else:
            cand = Candidate(
                reg.package_name,
                reg.version,
                reg.rust_version,
                reg.yanked,
                list(reg.dependencies),
                "registry",
                reg.source_id,
                "registry",
                reg.source_id,
                registry_source_digest(reg.package_name, reg.version, reg.source_id, reg.checksum),
                reg.checksum,
            )
        by_name.setdefault(reg.package_name, []).append(cand)

    # Patched versions that do not replace an existing registry record still join.
    for key, cand in replacements.items():
        _source_id, name, version = key
        existing_versions = {c.version for c in by_name.get(name, [])}
        if version not in existing_versions:
            by_name.setdefault(name, []).append(cand)
        elif not any(c.version == version and c.origin == "patched" for c in by_name.get(name, [])):
            # Ensure replaced candidate is present (already handled above when
            # iterating registry). If registry lacked it somehow, add.
            lst = by_name.setdefault(name, [])
            lst = [c for c in lst if not (c.version == version and c.source_id == key[0])]
            lst.append(cand)
            by_name[name] = lst

    return by_name, patch_rows, None


def _satisfies(cands: list[Candidate], reqs: list[Requirement]) -> list[Candidate]:
    out = []
    for c in cands:
        ver = Version.parse(c.version)
        if all(r.matches(ver) for r in reqs):
            out.append(c)
    return out


def _locked_yank_ok(lock: PreviousLock | None, name: str, version: str) -> bool:
    if lock is None:
        return False
    return any(p.package_name == name and p.version == version for p in lock.selected_packages)


def _pick_candidate(
    valid: list[Candidate],
    lock: PreviousLock | None,
    name: str,
    resolver_mode: str,
    msrv: Version,
) -> Candidate | None:
    if not valid:
        return None
    if lock is not None:
        for lp in lock.selected_packages:
            if lp.package_name != name:
                continue
            for c in valid:
                if c.version == lp.version:
                    return c
    if resolver_mode == "allow":
        return max(valid, key=lambda c: Version.parse(c.version))
    compatible = [c for c in valid if Version.parse(c.rust_version) <= msrv]
    pool = compatible or valid
    return max(pool, key=lambda c: Version.parse(c.version))


def resolve_graph(
    ds: Dataset,
    member_ids: list[str],
    patch_set_id: str,
    lock: PreviousLock | None,
) -> tuple[dict[str, Candidate] | None, list[dict[str, Any]], str | None, str | None]:
    members = _member_map(ds)
    msrv = min(
        (Version.parse(members[mid].rust_version) for mid in member_ids),
        default=None,
    )
    assert msrv is not None
    by_name, patch_rows, conflict = build_overlay_candidates(ds, patch_set_id)
    if conflict:
        return None, patch_rows, conflict, str(msrv)

    active: dict[str, list[Requirement]] = {}
    for mid in member_ids:
        for dep in members[mid].dependencies:
            active.setdefault(dep.package_name, []).append(Requirement.parse(dep.requirement))

    selected: dict[str, Candidate] = {}
    for round_i in range(ds.policy.maximum_resolution_rounds):
        changed = False
        names = sorted(active.keys())
        for name in names:
            reqs = active[name]
            cands = by_name.get(name, [])
            eligible = []
            for c in cands:
                if c.yanked and not _locked_yank_ok(lock, name, c.version):
                    continue
                eligible.append(c)
            valid = _satisfies(eligible, reqs)
            if not valid:
                return None, patch_rows, "package_version_conflict", str(msrv)
            pick = _pick_candidate(valid, lock, name, ds.resolver_mode, msrv)
            assert pick is not None
            prev = selected.get(name)
            if (
                prev is None
                or prev.version != pick.version
                or prev.source_digest != pick.source_digest
            ):
                selected[name] = pick
                changed = True
                for dep in pick.dependencies:
                    active.setdefault(dep.package_name, []).append(
                        Requirement.parse(dep.requirement)
                    )
        if not changed:
            # Mark selected patches
            selected_keys = {
                (c.source_id, c.package_name, c.version)
                for c in selected.values()
                if c.origin == "patched"
            }
            for row in patch_rows:
                if row["status"] == "rejected":
                    continue
                key = row["_candidate_key"]
                if key in selected_keys:
                    row["status"] = "selected"
                    row["reason_or_null"] = None
                else:
                    row["status"] = "unused"
                    row["reason_or_null"] = None
            return selected, patch_rows, None, str(msrv)
        _ = round_i
    return None, patch_rows, "resolution_round_limit", str(msrv)


def _dep_names(c: Candidate) -> list[str]:
    return sorted({d.package_name for d in c.dependencies})


def _project_selection(
    c: Candidate,
    replacement_set,
) -> tuple[str, str, str, str, list[dict[str, Any]], str | None]:
    """Project selection source fields and optional replacement rows."""
    repl_rows: list[dict[str, Any]] = []
    if c.origin == "patched":
        return (
            c.source_kind,
            c.source_reference,
            c.source_digest,
            c.checksum,
            repl_rows,
            None,
        )

    # registry
    mapping = None
    for m in replacement_set.mappings:
        if m.original_source_id == c.source_id:
            mapping = m
            break
    if mapping is None:
        return (
            "registry",
            c.source_reference,
            c.source_digest,
            c.checksum,
            repl_rows,
            None,
        )

    match = None
    for r in replacement_set.replacement_records:
        if (
            r.replacement_source_id == mapping.replacement_source_id
            and r.package_name == c.package_name
            and r.version == c.version
        ):
            match = r
            break
    if match is None:
        repl_rows.append(
            {
                "package_name": c.package_name,
                "version": c.version,
                "original_source_id": c.source_id,
                "replacement_source_id": mapping.replacement_source_id,
                "original_checksum": c.checksum,
                "replacement_checksum_or_null": None,
                "status": "missing",
            }
        )
        return "", "", "", "", repl_rows, "source_replacement_missing"
    if match.checksum != c.checksum:
        repl_rows.append(
            {
                "package_name": c.package_name,
                "version": c.version,
                "original_source_id": c.source_id,
                "replacement_source_id": mapping.replacement_source_id,
                "original_checksum": c.checksum,
                "replacement_checksum_or_null": match.checksum,
                "status": "checksum_mismatch",
            }
        )
        return "", "", "", "", repl_rows, "source_replacement_mismatch"
    new_digest = registry_source_digest(
        c.package_name, c.version, mapping.replacement_source_id, c.checksum
    )
    repl_rows.append(
        {
            "package_name": c.package_name,
            "version": c.version,
            "original_source_id": c.source_id,
            "replacement_source_id": mapping.replacement_source_id,
            "original_checksum": c.checksum,
            "replacement_checksum_or_null": match.checksum,
            "status": "equivalent",
        }
    )
    return (
        "replacement_registry",
        match.source_reference,
        new_digest,
        c.checksum,
        repl_rows,
        None,
    )


def _reverse_deps(selected: dict[str, Selection]) -> dict[str, list[str]]:
    rev: dict[str, list[str]] = {name: [] for name in selected}
    for name, sel in selected.items():
        for dep in sel.candidate.dependencies:
            if dep.package_name in rev:
                rev[dep.package_name].append(name)
    for k, deps in rev.items():
        rev[k] = sorted(set(deps))
    return rev


def _try_reuse(
    lp: LockPackage,
    sel: Selection,
    ds: Dataset,
    lock: PreviousLock,
    patch_set_id: str,
    replacement_set_id: str,
    reusable: dict[str, bool],
    visiting: set[str],
) -> bool:
    name = lp.package_name
    if name in reusable:
        return reusable[name]
    if name in visiting:
        return False
    visiting.add(name)
    ok = not (
        lock.workspace_digest != ds.workspace_digest
        or lock.patch_set_digest != ds.patch_digests[patch_set_id]
        or lock.replacement_set_digest != ds.replacement_digests[replacement_set_id]
        or lp.version != sel.candidate.version
        or lp.source_kind != sel.selection_source
        or lp.source_reference != sel.source_reference
        or lp.source_digest != sel.source_digest
        or lp.checksum != sel.checksum
        or sorted(set(lp.dependency_names)) != _dep_names(sel.candidate)
    )
    if ok:
        for dep_name in sorted(set(lp.dependency_names)):
            if dep_name not in selected_lock_packages(lock):
                # dependency must be selected and reusable
                pass
            dep_lp = next(
                (p for p in lock.selected_packages if p.package_name == dep_name),
                None,
            )
            if dep_lp is None or (dep_name not in reusable and dep_name not in visiting):
                # need sel for dep - caller provides selected map via closure
                pass
    visiting.discard(name)
    reusable[name] = ok
    return ok


def selected_lock_packages(lock: PreviousLock) -> dict[str, LockPackage]:
    return {p.package_name: p for p in lock.selected_packages}


def evaluate_lock_reuse(
    ds: Dataset,
    lock: PreviousLock,
    patch_set_id: str,
    replacement_set_id: str,
    selected: dict[str, Selection],
) -> tuple[dict[str, str], list[dict[str, Any]], list[dict[str, Any]], bool]:
    """Return lock_status by name, lock_rows, invalidation_rows, any_stale_required."""
    prior = selected_lock_packages(lock)
    digests_match_context = (
        lock.workspace_digest == ds.workspace_digest
        and lock.patch_set_digest == ds.patch_digests[patch_set_id]
        and lock.replacement_set_digest == ds.replacement_digests[replacement_set_id]
    )

    memo: dict[str, bool] = {}

    def is_reusable(name: str) -> bool:
        if name in memo:
            return memo[name]
        if name not in selected:
            memo[name] = False
            return False
        if name not in prior:
            memo[name] = False
            return False
        if not digests_match_context:
            memo[name] = False
            return False
        lp = prior[name]
        sel = selected[name]
        if lp.version != sel.candidate.version:
            memo[name] = False
            return False
        if lp.source_kind != sel.selection_source:
            memo[name] = False
            return False
        if lp.source_reference != sel.source_reference:
            memo[name] = False
            return False
        if lp.source_digest != sel.source_digest:
            memo[name] = False
            return False
        if lp.checksum != sel.checksum:
            memo[name] = False
            return False
        if sorted(set(lp.dependency_names)) != _dep_names(sel.candidate):
            memo[name] = False
            return False
        for dep in sorted(set(lp.dependency_names)):
            if not is_reusable(dep):
                memo[name] = False
                return False
        memo[name] = True
        return True

    rev = _reverse_deps(selected)
    status: dict[str, str] = {}
    invalidations: list[dict[str, Any]] = []
    lock_rows: list[dict[str, Any]] = []

    names = sorted(set(selected) | set(prior))
    for name in names:
        if name in selected:
            sel = selected[name]
            computed = lock_package_digest(
                name,
                sel.candidate.version,
                sel.selection_source,
                sel.source_reference,
                sel.source_digest,
                sel.checksum,
                _dep_names(sel.candidate),
            )
            if name in prior:
                lp = prior[name]
                prior_digest = lock_package_digest(
                    lp.package_name,
                    lp.version,
                    lp.source_kind,
                    lp.source_reference,
                    lp.source_digest,
                    lp.checksum,
                    lp.dependency_names,
                )
                if is_reusable(name):
                    status[name] = "reused"
                    reason = None
                else:
                    status[name] = "recomputed"
                    cause_kind, cause_subject = _invalidation_cause(
                        lp, sel, digests_match_context, prior, selected, is_reusable
                    )
                    invalidations.append(
                        {
                            "package_name": name,
                            "cause_kind": cause_kind,
                            "cause_subject": cause_subject,
                            "dependent_packages": rev.get(name, []),
                        }
                    )
                    reason = (
                        "upstream_invalidated"
                        if cause_kind == "upstream_invalidated"
                        else "digest_mismatch"
                    )
                lock_rows.append(
                    {
                        "package_name": name,
                        "prior_digest_or_null": prior_digest,
                        "computed_digest": computed,
                        "status": status[name],
                        "reason_or_null": reason,
                    }
                )
            else:
                status[name] = "recomputed"
                invalidations.append(
                    {
                        "package_name": name,
                        "cause_kind": "missing_lock_entry",
                        "cause_subject": name,
                        "dependent_packages": rev.get(name, []),
                    }
                )
                lock_rows.append(
                    {
                        "package_name": name,
                        "prior_digest_or_null": None,
                        "computed_digest": computed,
                        "status": "recomputed",
                        "reason_or_null": "missing_lock_entry",
                    }
                )
        else:
            lp = prior[name]
            prior_digest = lock_package_digest(
                lp.package_name,
                lp.version,
                lp.source_kind,
                lp.source_reference,
                lp.source_digest,
                lp.checksum,
                lp.dependency_names,
            )
            lock_rows.append(
                {
                    "package_name": name,
                    "prior_digest_or_null": prior_digest,
                    "computed_digest": "",
                    "status": "not_selected",
                    "reason_or_null": None,
                }
            )

    any_stale = any(status.get(n) != "reused" for n in selected)
    return status, lock_rows, invalidations, any_stale


def _invalidation_cause(
    lp: LockPackage,
    sel: Selection,
    digests_match_context: bool,
    prior: dict[str, LockPackage],
    selected: dict[str, Selection],
    is_reusable,
) -> tuple[str, str]:
    if not digests_match_context:
        return "source_changed", "context_digest"
    if lp.version != sel.candidate.version:
        return "selection_changed", lp.version
    if (
        lp.source_kind != sel.selection_source
        or lp.source_reference != sel.source_reference
        or lp.source_digest != sel.source_digest
        or lp.checksum != sel.checksum
    ):
        return "source_changed", lp.source_reference
    if sorted(set(lp.dependency_names)) != _dep_names(sel.candidate):
        return "dependency_changed", ",".join(_dep_names(sel.candidate))
    for dep in sorted(set(lp.dependency_names)):
        if not is_reusable(dep):
            return "upstream_invalidated", dep
    return "source_changed", lp.package_name


def process_request(ds: Dataset, req) -> RequestResult:
    result = RequestResult(
        request_id=req.request_id,
        lockfile_mode=req.lockfile_mode,
        resolver_mode=ds.resolver_mode,
        request_msrv=None,
        status="rejected",
        reason_or_null=None,
    )
    members = _member_map(ds)
    locks = _lock_map(ds)
    patches = _patch_map(ds)
    repls = _repl_map(ds)

    for mid in req.member_ids:
        if mid not in members:
            result.reason_or_null = "unknown_member"
            result.conflict_rows.append(
                {
                    "conflict_type": "unknown_member",
                    "subject": mid,
                    "reason_code": "unknown_member",
                    "related_values": sorted(req.member_ids),
                }
            )
            return result
    if req.lock_id not in locks:
        result.reason_or_null = "unknown_lock"
        result.conflict_rows.append(
            {
                "conflict_type": "unknown_lock",
                "subject": req.lock_id,
                "reason_code": "unknown_lock",
                "related_values": [req.lock_id],
            }
        )
        return result
    if req.patch_set_id not in patches:
        result.reason_or_null = "unknown_patch_set"
        result.conflict_rows.append(
            {
                "conflict_type": "unknown_patch_set",
                "subject": req.patch_set_id,
                "reason_code": "unknown_patch_set",
                "related_values": [req.patch_set_id],
            }
        )
        return result
    if req.replacement_set_id not in repls:
        result.reason_or_null = "unknown_replacement_set"
        result.conflict_rows.append(
            {
                "conflict_type": "unknown_replacement_set",
                "subject": req.replacement_set_id,
                "reason_code": "unknown_replacement_set",
                "related_values": [req.replacement_set_id],
            }
        )
        return result

    lock = locks[req.lock_id]
    replacement_set = repls[req.replacement_set_id]
    selected_raw, patch_rows, reason, msrv = resolve_graph(
        ds, req.member_ids, req.patch_set_id, lock
    )
    result.request_msrv = msrv
    # strip internal keys from patch rows
    clean_patches = [
        {
            "request_id": req.request_id,
            "source_id": row["source_id"],
            "package_name": row["package_name"],
            "patched_package_id": row["patched_package_id"],
            "patched_version": row["patched_version"],
            "status": row["status"],
            "reason_or_null": row["reason_or_null"],
        }
        for row in patch_rows
    ]
    result.patch_rows = clean_patches
    if reason == "patch_conflict":
        result.reason_or_null = "patch_conflict"
        result.conflict_rows.append(
            {
                "conflict_type": "patch_conflict",
                "subject": req.patch_set_id,
                "reason_code": "patch_conflict",
                "related_values": sorted({p["patched_package_id"] for p in clean_patches}),
            }
        )
        return result
    if reason in ("package_version_conflict", "resolution_round_limit"):
        result.reason_or_null = reason
        result.conflict_rows.append(
            {
                "conflict_type": reason,
                "subject": req.request_id,
                "reason_code": reason,
                "related_values": sorted(req.member_ids),
            }
        )
        return result

    assert selected_raw is not None
    selections: dict[str, Selection] = {}
    all_repl_rows: list[dict[str, Any]] = []
    for name in sorted(selected_raw):
        c = selected_raw[name]
        (
            sel_source,
            src_ref,
            src_digest,
            checksum,
            repl_rows,
            repl_reason,
        ) = _project_selection(c, replacement_set)
        for repl_row in repl_rows:
            enriched = dict(repl_row)
            enriched["request_id"] = req.request_id
            all_repl_rows.append(enriched)
        if repl_reason:
            result.replacement_rows = all_repl_rows
            result.reason_or_null = repl_reason
            result.conflict_rows.append(
                {
                    "conflict_type": repl_reason,
                    "subject": name,
                    "reason_code": repl_reason,
                    "related_values": [name, c.version],
                }
            )
            return result
        locked_ver = None
        for lp in lock.selected_packages:
            if lp.package_name == name:
                locked_ver = lp.version
                break
        selections[name] = Selection(
            c,
            sel_source,
            src_ref,
            src_digest,
            checksum,
            "recomputed",
            locked_ver,
        )

    result.replacement_rows = all_repl_rows
    statuses, lock_rows, invalidations, any_stale = evaluate_lock_reuse(
        ds, lock, req.patch_set_id, req.replacement_set_id, selections
    )
    for name, sel in selections.items():
        sel.lock_status = statuses[name]

    if req.lockfile_mode == "frozen" and any_stale:
        result.reason_or_null = "lockfile_stale"
        result.conflict_rows.append(
            {
                "conflict_type": "lockfile_stale",
                "subject": req.lock_id,
                "reason_code": "lockfile_stale",
                "related_values": sorted(n for n, st in statuses.items() if st != "reused"),
            }
        )
        # frozen: do not emit selection/lock/invalidation detail
        result.replacement_rows = []
        return result

    result.status = "accepted"
    result.reason_or_null = None
    result.selected = selections
    for lock_row in lock_rows:
        enriched = dict(lock_row)
        enriched["request_id"] = req.request_id
        result.lock_rows.append(enriched)
    for inv_row in invalidations:
        if statuses.get(inv_row["package_name"]) == "reused":
            continue
        if inv_row["package_name"] not in selections:
            continue
        enriched = dict(inv_row)
        enriched["request_id"] = req.request_id
        result.invalidation_rows.append(enriched)
    result.reused = sum(1 for s in statuses.values() if s == "reused")
    result.recomputed = sum(1 for s in statuses.values() if s == "recomputed")
    return result


def build_report(ds: Dataset) -> dict[str, Any]:
    request_rows = []
    package_selection_rows = []
    patch_rows = []
    source_replacement_rows = []
    lock_entry_rows = []
    invalidation_rows = []
    conflict_rows = []

    for req in sorted(ds.build_requests, key=lambda r: r.request_id):
        result = process_request(ds, req)
        request_rows.append(
            {
                "request_id": result.request_id,
                "lockfile_mode": result.lockfile_mode,
                "resolver_mode": result.resolver_mode,
                "request_msrv": result.request_msrv,
                "status": result.status,
                "reason_or_null": result.reason_or_null,
                "selected_package_count": len(result.selected),
                "reused_lock_entry_count": result.reused if result.status == "accepted" else 0,
                "recomputed_lock_entry_count": (
                    result.recomputed if result.status == "accepted" else 0
                ),
            }
        )
        for name, sel in sorted(result.selected.items()):
            msrv = Version.parse(result.request_msrv)
            package_selection_rows.append(
                {
                    "request_id": result.request_id,
                    "package_name": name,
                    "selected_version": sel.candidate.version,
                    "selection_source": sel.selection_source,
                    "source_reference": sel.source_reference,
                    "source_digest": sel.source_digest,
                    "checksum": sel.checksum,
                    "rust_version": sel.candidate.rust_version,
                    "msrv_compatible": Version.parse(sel.candidate.rust_version) <= msrv,
                    "yanked": sel.candidate.yanked,
                    "locked_version_or_null": sel.locked_version_or_null,
                    "lock_status": sel.lock_status,
                }
            )
        patch_rows.extend(result.patch_rows)
        if result.status == "accepted":
            source_replacement_rows.extend(result.replacement_rows)
            lock_entry_rows.extend(result.lock_rows)
            invalidation_rows.extend(result.invalidation_rows)
        for conflict in result.conflict_rows:
            enriched = dict(conflict)
            enriched["request_id"] = result.request_id
            conflict_rows.append(enriched)

    def sort_rows(rows, keys):
        return sorted(rows, key=lambda r: tuple(r[k] for k in keys))

    package_selection_rows = sort_rows(package_selection_rows, ["request_id", "package_name"])
    patch_rows = sort_rows(
        patch_rows, ["request_id", "source_id", "package_name", "patched_version"]
    )
    source_replacement_rows = sort_rows(
        source_replacement_rows,
        ["request_id", "original_source_id", "package_name", "version"],
    )
    lock_entry_rows = sort_rows(lock_entry_rows, ["request_id", "package_name"])
    invalidation_rows = sort_rows(
        invalidation_rows,
        ["request_id", "package_name", "cause_kind", "cause_subject"],
    )
    conflict_rows = sort_rows(
        conflict_rows, ["request_id", "conflict_type", "subject", "reason_code"]
    )

    summary = {
        "request_count": len(request_rows),
        "accepted_request_count": sum(1 for r in request_rows if r["status"] == "accepted"),
        "rejected_request_count": sum(1 for r in request_rows if r["status"] == "rejected"),
        "package_selection_row_count": len(package_selection_rows),
        "selected_patch_count": sum(1 for r in patch_rows if r["status"] == "selected"),
        "replacement_row_count": len(source_replacement_rows),
        "reused_lock_entry_count": sum(1 for r in lock_entry_rows if r["status"] == "reused"),
        "recomputed_lock_entry_count": sum(
            1 for r in lock_entry_rows if r["status"] == "recomputed"
        ),
        "conflict_count": len(conflict_rows),
    }

    return {
        "request_rows": request_rows,
        "package_selection_rows": package_selection_rows,
        "patch_rows": patch_rows,
        "source_replacement_rows": source_replacement_rows,
        "lock_entry_rows": lock_entry_rows,
        "invalidation_rows": invalidation_rows,
        "conflict_rows": conflict_rows,
        "summary": summary,
    }
