//! Bounded per-request graph resolution, patch overlay, replacement
//! projection, lock-entry reuse, and full report assembly.

use std::cell::RefCell;
use std::collections::{BTreeSet, HashMap, HashSet};

use crate::models::{
    lock_package_digest, registry_source_digest, BuildRequest, DepSpec, Dataset, FatalError,
    LockPackage, Member, PatchSet, PatchedPackage, PreviousLock, ReplacementSet, Requirement,
    Result, Version,
};
use crate::report::{
    ConflictRow, InvalidationRow, LockEntryRow, PackageSelectionRow, PatchRow, Report, RequestRow,
    SourceReplacementRow, Summary,
};

#[allow(dead_code)]
pub const REJECTION_ORDER: [&str; 10] = [
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
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Origin {
    Registry,
    Patched,
}

#[derive(Debug, Clone)]
pub struct Candidate {
    pub package_name: String,
    pub version: String,
    pub rust_version: String,
    pub yanked: bool,
    pub dependencies: Vec<DepSpec>,
    pub origin: Origin,
    pub source_id: String,
    pub source_kind: String,
    pub source_reference: String,
    pub source_digest: String,
    pub checksum: String,
    #[allow(dead_code)]
    pub patched_package_id: Option<String>,
}

#[derive(Debug, Clone)]
pub struct Selection {
    pub candidate: Candidate,
    pub selection_source: String,
    pub source_reference: String,
    pub source_digest: String,
    pub checksum: String,
    pub lock_status: String,
    pub locked_version_or_null: Option<String>,
}

struct PatchRowInternal {
    source_id: String,
    package_name: String,
    patched_package_id: String,
    patched_version: String,
    status: String,
    reason_or_null: Option<String>,
    candidate_key: Option<(String, String, String)>,
}

struct ReplRowInternal {
    package_name: String,
    version: String,
    original_source_id: String,
    replacement_source_id: String,
    original_checksum: String,
    replacement_checksum_or_null: Option<String>,
    status: String,
}

fn member_map(ds: &Dataset) -> HashMap<&str, &Member> {
    ds.members.iter().map(|m| (m.member_id.as_str(), m)).collect()
}

fn lock_map(ds: &Dataset) -> HashMap<&str, &PreviousLock> {
    ds.previous_locks.iter().map(|l| (l.lock_id.as_str(), l)).collect()
}

fn patch_map(ds: &Dataset) -> HashMap<&str, &PatchSet> {
    ds.patch_sets.iter().map(|p| (p.patch_set_id.as_str(), p)).collect()
}

fn repl_map(ds: &Dataset) -> HashMap<&str, &ReplacementSet> {
    ds.replacement_sets
        .iter()
        .map(|r| (r.replacement_set_id.as_str(), r))
        .collect()
}

fn patched_map(ds: &Dataset) -> HashMap<&str, &PatchedPackage> {
    ds.patched_packages
        .iter()
        .map(|p| (p.patched_package_id.as_str(), p))
        .collect()
}

fn dep_names(c: &Candidate) -> Vec<String> {
    let set: BTreeSet<String> = c.dependencies.iter().map(|d| d.package_name.clone()).collect();
    set.into_iter().collect()
}

fn sorted_unique_names(names: &[String]) -> Vec<String> {
    let set: BTreeSet<String> = names.iter().cloned().collect();
    set.into_iter().collect()
}

/// Returns the first candidate with the numerically greatest version,
/// matching Python `max()` first-element-wins tie-breaking (Rust's
/// `Iterator::max_by_key` would instead keep the *last* tied element).
fn pick_max_version(cands: &[Candidate]) -> &Candidate {
    let mut best = &cands[0];
    let mut best_v = Version::parse(&best.version).expect("version validated at load time");
    for c in &cands[1..] {
        let v = Version::parse(&c.version).expect("version validated at load time");
        if v > best_v {
            best = c;
            best_v = v;
        }
    }
    best
}

#[allow(clippy::type_complexity)]
fn build_overlay_candidates(
    ds: &Dataset,
    patch_set_id: &str,
) -> Result<(HashMap<String, Vec<Candidate>>, Vec<PatchRowInternal>, Option<String>)> {
    let patches_by_set = patch_map(ds);
    let ps = patches_by_set
        .get(patch_set_id)
        .expect("patch_set_id existence checked by caller");
    let patched_by_id = patched_map(ds);

    let mut patch_rows: Vec<PatchRowInternal> = Vec::new();
    let mut replacements: HashMap<(String, String, String), Candidate> = HashMap::new();
    let mut replacements_order: Vec<(String, String, String)> = Vec::new();
    let mut target_seen: HashSet<(String, String, String)> = HashSet::new();
    let mut conflict = false;

    for entry in &ps.patches {
        let pp = patched_by_id
            .get(entry.patched_package_id.as_str())
            .expect("patched_package_id existence checked at load time");

        let mut status = "unused".to_string();
        let mut reason: Option<String> = None;
        let mut cand_key: Option<(String, String, String)> = None;

        if pp.package_name != entry.package_name {
            status = "rejected".to_string();
            reason = Some("package_mismatch".to_string());
        } else if pp.patched_source_id != entry.source_id {
            status = "rejected".to_string();
            reason = Some("source_mismatch".to_string());
        } else {
            let key = (entry.source_id.clone(), entry.package_name.clone(), pp.version.clone());
            if target_seen.contains(&key) {
                conflict = true;
                status = "rejected".to_string();
                reason = Some("duplicate_target".to_string());
            } else {
                target_seen.insert(key.clone());
                let source_kind = if pp.source_kind == "path_snapshot" {
                    "patched_path"
                } else {
                    "patched_git_snapshot"
                };
                let cand = Candidate {
                    package_name: pp.package_name.clone(),
                    version: pp.version.clone(),
                    rust_version: pp.rust_version.clone(),
                    yanked: false,
                    dependencies: pp.dependencies.clone(),
                    origin: Origin::Patched,
                    source_id: entry.source_id.clone(),
                    source_kind: source_kind.to_string(),
                    source_reference: pp.source_reference.clone(),
                    source_digest: pp.source_digest.clone(),
                    checksum: pp.source_digest.clone(),
                    patched_package_id: Some(entry.patched_package_id.clone()),
                };
                replacements.insert(key.clone(), cand);
                replacements_order.push(key.clone());
                cand_key = Some(key);
            }
        }

        patch_rows.push(PatchRowInternal {
            source_id: entry.source_id.clone(),
            package_name: entry.package_name.clone(),
            patched_package_id: entry.patched_package_id.clone(),
            patched_version: pp.version.clone(),
            status,
            reason_or_null: reason,
            candidate_key: cand_key,
        });
    }

    if conflict {
        for row in patch_rows.iter_mut() {
            if row.status != "rejected" {
                row.status = "rejected".to_string();
                row.reason_or_null = Some("duplicate_target".to_string());
            }
        }
        return Ok((HashMap::new(), patch_rows, Some("patch_conflict".to_string())));
    }

    let mut by_name: HashMap<String, Vec<Candidate>> = HashMap::new();
    for reg in &ds.registry_packages {
        let key = (reg.source_id.clone(), reg.package_name.clone(), reg.version.clone());
        let cand = if let Some(c) = replacements.get(&key) {
            c.clone()
        } else {
            Candidate {
                package_name: reg.package_name.clone(),
                version: reg.version.clone(),
                rust_version: reg.rust_version.clone(),
                yanked: reg.yanked,
                dependencies: reg.dependencies.clone(),
                origin: Origin::Registry,
                source_id: reg.source_id.clone(),
                source_kind: "registry".to_string(),
                source_reference: reg.source_id.clone(),
                source_digest: registry_source_digest(&reg.package_name, &reg.version, &reg.source_id, &reg.checksum),
                checksum: reg.checksum.clone(),
                patched_package_id: None,
            }
        };
        by_name.entry(reg.package_name.clone()).or_default().push(cand);
    }

    // Patched versions that do not replace an existing registry record still join.
    for key in &replacements_order {
        let cand = replacements.get(key).expect("key present");
        let (source_id, name, version) = key;
        let list = by_name.entry(name.clone()).or_default();
        let existing_versions: HashSet<String> = list.iter().map(|c| c.version.clone()).collect();
        if !existing_versions.contains(version) {
            list.push(cand.clone());
        } else if !list
            .iter()
            .any(|c| c.version == *version && c.origin == Origin::Patched)
        {
            list.retain(|c| !(c.version == *version && c.source_id == *source_id));
            list.push(cand.clone());
        }
    }

    Ok((by_name, patch_rows, None))
}

fn satisfies(cands: &[Candidate], reqs: &[Requirement]) -> Result<Vec<Candidate>> {
    let mut out = Vec::new();
    for c in cands {
        let v = Version::parse(&c.version)?;
        if reqs.iter().all(|r| r.matches(&v)) {
            out.push(c.clone());
        }
    }
    Ok(out)
}

fn locked_yank_ok(lock: Option<&PreviousLock>, name: &str, version: &str) -> bool {
    match lock {
        None => false,
        Some(l) => l
            .selected_packages
            .iter()
            .any(|p| p.package_name == name && p.version == version),
    }
}

fn pick_candidate(
    valid: &[Candidate],
    lock: Option<&PreviousLock>,
    name: &str,
    resolver_mode: &str,
    msrv: &Version,
) -> Option<Candidate> {
    if valid.is_empty() {
        return None;
    }
    if let Some(lock) = lock {
        for lp in &lock.selected_packages {
            if lp.package_name != name {
                continue;
            }
            for c in valid {
                if c.version == lp.version {
                    return Some(c.clone());
                }
            }
        }
    }
    if resolver_mode == "allow" {
        return Some(pick_max_version(valid).clone());
    }
    let compatible: Vec<Candidate> = valid
        .iter()
        .filter(|c| Version::parse(&c.rust_version).map(|v| v <= *msrv).unwrap_or(false))
        .cloned()
        .collect();
    let pool: &[Candidate] = if !compatible.is_empty() { &compatible } else { valid };
    Some(pick_max_version(pool).clone())
}

#[allow(clippy::type_complexity)]
fn resolve_graph(
    ds: &Dataset,
    member_ids: &[String],
    patch_set_id: &str,
    lock: Option<&PreviousLock>,
) -> Result<(Option<HashMap<String, Candidate>>, Vec<PatchRowInternal>, Option<String>, String)> {
    let members = member_map(ds);

    let mut msrv: Option<Version> = None;
    for mid in member_ids {
        let m = members.get(mid.as_str()).expect("member existence checked by caller");
        let v = Version::parse(&m.rust_version)?;
        msrv = Some(match msrv {
            None => v,
            Some(cur) => {
                if v < cur {
                    v
                } else {
                    cur
                }
            }
        });
    }
    let msrv = msrv.ok_or_else(|| FatalError("empty member_ids in request".to_string()))?;

    let (by_name, mut patch_rows, conflict) = build_overlay_candidates(ds, patch_set_id)?;
    if let Some(c) = conflict {
        return Ok((None, patch_rows, Some(c), msrv.to_string()));
    }

    let mut active: HashMap<String, Vec<Requirement>> = HashMap::new();
    for mid in member_ids {
        let m = members[mid.as_str()];
        for dep in &m.dependencies {
            active
                .entry(dep.package_name.clone())
                .or_default()
                .push(Requirement::parse(&dep.requirement)?);
        }
    }

    let mut selected: HashMap<String, Candidate> = HashMap::new();
    for _round in 0..ds.policy.maximum_resolution_rounds.max(0) {
        let mut changed = false;
        let mut names: Vec<String> = active.keys().cloned().collect();
        names.sort();
        for name in &names {
            let reqs = active.get(name).cloned().unwrap_or_default();
            let cands = by_name.get(name).cloned().unwrap_or_default();
            let mut eligible = Vec::with_capacity(cands.len());
            for c in cands {
                if c.yanked && !locked_yank_ok(lock, name, &c.version) {
                    continue;
                }
                eligible.push(c);
            }
            let valid = satisfies(&eligible, &reqs)?;
            if valid.is_empty() {
                return Ok((
                    None,
                    patch_rows,
                    Some("package_version_conflict".to_string()),
                    msrv.to_string(),
                ));
            }
            let pick = pick_candidate(&valid, lock, name, &ds.resolver_mode, &msrv).expect("valid non-empty");
            let changed_here = match selected.get(name) {
                Some(prev) => prev.version != pick.version || prev.source_digest != pick.source_digest,
                None => true,
            };
            if changed_here {
                for dep in &pick.dependencies {
                    active
                        .entry(dep.package_name.clone())
                        .or_default()
                        .push(Requirement::parse(&dep.requirement)?);
                }
                selected.insert(name.clone(), pick);
                changed = true;
            }
        }
        if !changed {
            let selected_keys: HashSet<(String, String, String)> = selected
                .values()
                .filter(|c| c.origin == Origin::Patched)
                .map(|c| (c.source_id.clone(), c.package_name.clone(), c.version.clone()))
                .collect();
            for row in patch_rows.iter_mut() {
                if row.status == "rejected" {
                    continue;
                }
                let is_selected = row
                    .candidate_key
                    .as_ref()
                    .map(|k| selected_keys.contains(k))
                    .unwrap_or(false);
                row.status = if is_selected { "selected".to_string() } else { "unused".to_string() };
                row.reason_or_null = None;
            }
            return Ok((Some(selected), patch_rows, None, msrv.to_string()));
        }
    }
    Ok((
        None,
        patch_rows,
        Some("resolution_round_limit".to_string()),
        msrv.to_string(),
    ))
}

fn project_selection(
    c: &Candidate,
    replacement_set: &ReplacementSet,
) -> (String, String, String, String, Vec<ReplRowInternal>, Option<String>) {
    if c.origin == Origin::Patched {
        return (
            c.source_kind.clone(),
            c.source_reference.clone(),
            c.source_digest.clone(),
            c.checksum.clone(),
            Vec::new(),
            None,
        );
    }

    let mapping = replacement_set
        .mappings
        .iter()
        .find(|m| m.original_source_id == c.source_id);
    let mapping = match mapping {
        None => {
            return (
                "registry".to_string(),
                c.source_reference.clone(),
                c.source_digest.clone(),
                c.checksum.clone(),
                Vec::new(),
                None,
            )
        }
        Some(m) => m,
    };

    let matched = replacement_set.replacement_records.iter().find(|r| {
        r.replacement_source_id == mapping.replacement_source_id
            && r.package_name == c.package_name
            && r.version == c.version
    });

    match matched {
        None => {
            let row = ReplRowInternal {
                package_name: c.package_name.clone(),
                version: c.version.clone(),
                original_source_id: c.source_id.clone(),
                replacement_source_id: mapping.replacement_source_id.clone(),
                original_checksum: c.checksum.clone(),
                replacement_checksum_or_null: None,
                status: "missing".to_string(),
            };
            (
                String::new(),
                String::new(),
                String::new(),
                String::new(),
                vec![row],
                Some("source_replacement_missing".to_string()),
            )
        }
        Some(rec) if rec.checksum != c.checksum => {
            let row = ReplRowInternal {
                package_name: c.package_name.clone(),
                version: c.version.clone(),
                original_source_id: c.source_id.clone(),
                replacement_source_id: mapping.replacement_source_id.clone(),
                original_checksum: c.checksum.clone(),
                replacement_checksum_or_null: Some(rec.checksum.clone()),
                status: "checksum_mismatch".to_string(),
            };
            (
                String::new(),
                String::new(),
                String::new(),
                String::new(),
                vec![row],
                Some("source_replacement_mismatch".to_string()),
            )
        }
        Some(rec) => {
            let new_digest = registry_source_digest(&c.package_name, &c.version, &mapping.replacement_source_id, &c.checksum);
            let row = ReplRowInternal {
                package_name: c.package_name.clone(),
                version: c.version.clone(),
                original_source_id: c.source_id.clone(),
                replacement_source_id: mapping.replacement_source_id.clone(),
                original_checksum: c.checksum.clone(),
                replacement_checksum_or_null: Some(rec.checksum.clone()),
                status: "equivalent".to_string(),
            };
            (
                "replacement_registry".to_string(),
                rec.source_reference.clone(),
                new_digest,
                c.checksum.clone(),
                vec![row],
                None,
            )
        }
    }
}

fn reverse_deps(selected: &HashMap<String, Selection>) -> HashMap<String, Vec<String>> {
    let mut rev: HashMap<String, Vec<String>> = selected.keys().map(|k| (k.clone(), Vec::new())).collect();
    for (name, sel) in selected {
        for dep in &sel.candidate.dependencies {
            if let Some(v) = rev.get_mut(&dep.package_name) {
                v.push(name.clone());
            }
        }
    }
    for v in rev.values_mut() {
        let set: BTreeSet<String> = v.drain(..).collect();
        *v = set.into_iter().collect();
    }
    rev
}

/// Recursive reuse check with Python's memoization semantics. A `visiting`
/// guard is added purely to keep this terminating on a cyclic dependency
/// graph (the Python reference has no such guard and would instead exhaust
/// the call stack); ordinary acyclic fixtures behave identically either way.
#[allow(clippy::too_many_arguments)]
fn is_reusable(
    name: &str,
    selections: &HashMap<String, Selection>,
    prior: &HashMap<&str, &LockPackage>,
    digests_match_context: bool,
    memo: &RefCell<HashMap<String, bool>>,
    visiting: &RefCell<HashSet<String>>,
) -> bool {
    if let Some(v) = memo.borrow().get(name) {
        return *v;
    }
    if visiting.borrow().contains(name) {
        return false;
    }
    let sel = match selections.get(name) {
        Some(s) => s,
        None => {
            memo.borrow_mut().insert(name.to_string(), false);
            return false;
        }
    };
    let lp = match prior.get(name) {
        Some(l) => *l,
        None => {
            memo.borrow_mut().insert(name.to_string(), false);
            return false;
        }
    };
    if !digests_match_context {
        memo.borrow_mut().insert(name.to_string(), false);
        return false;
    }
    if lp.version != sel.candidate.version
        || lp.source_kind != sel.selection_source
        || lp.source_reference != sel.source_reference
        || lp.source_digest != sel.source_digest
        || lp.checksum != sel.checksum
    {
        memo.borrow_mut().insert(name.to_string(), false);
        return false;
    }
    let lp_deps = sorted_unique_names(&lp.dependency_names);
    if lp_deps != dep_names(&sel.candidate) {
        memo.borrow_mut().insert(name.to_string(), false);
        return false;
    }
    visiting.borrow_mut().insert(name.to_string());
    for dep in &lp_deps {
        if !is_reusable(dep, selections, prior, digests_match_context, memo, visiting) {
            visiting.borrow_mut().remove(name);
            memo.borrow_mut().insert(name.to_string(), false);
            return false;
        }
    }
    visiting.borrow_mut().remove(name);
    memo.borrow_mut().insert(name.to_string(), true);
    true
}

#[allow(clippy::too_many_arguments)]
fn invalidation_cause(
    lp: &LockPackage,
    sel: &Selection,
    digests_match_context: bool,
    selections: &HashMap<String, Selection>,
    prior: &HashMap<&str, &LockPackage>,
    memo: &RefCell<HashMap<String, bool>>,
    visiting: &RefCell<HashSet<String>>,
) -> (String, String) {
    if !digests_match_context {
        return ("source_changed".to_string(), "context_digest".to_string());
    }
    if lp.version != sel.candidate.version {
        return ("selection_changed".to_string(), lp.version.clone());
    }
    if lp.source_kind != sel.selection_source
        || lp.source_reference != sel.source_reference
        || lp.source_digest != sel.source_digest
        || lp.checksum != sel.checksum
    {
        return ("source_changed".to_string(), lp.source_reference.clone());
    }
    let lp_deps = sorted_unique_names(&lp.dependency_names);
    let sel_deps = dep_names(&sel.candidate);
    if lp_deps != sel_deps {
        return ("dependency_changed".to_string(), sel_deps.join(","));
    }
    for dep in &lp_deps {
        if !is_reusable(dep, selections, prior, digests_match_context, memo, visiting) {
            return ("upstream_invalidated".to_string(), dep.clone());
        }
    }
    ("source_changed".to_string(), lp.package_name.clone())
}

#[allow(clippy::type_complexity)]
fn evaluate_lock_reuse(
    ds: &Dataset,
    lock: &PreviousLock,
    patch_set_id: &str,
    replacement_set_id: &str,
    selections: &HashMap<String, Selection>,
    request_id: &str,
) -> (HashMap<String, String>, Vec<LockEntryRow>, Vec<InvalidationRow>, bool) {
    let prior: HashMap<&str, &LockPackage> = lock
        .selected_packages
        .iter()
        .map(|p| (p.package_name.as_str(), p))
        .collect();
    let digests_match_context = lock.workspace_digest == ds.workspace_digest
        && ds
            .patch_digests
            .get(patch_set_id)
            .map(|d| *d == lock.patch_set_digest)
            .unwrap_or(false)
        && ds
            .replacement_digests
            .get(replacement_set_id)
            .map(|d| *d == lock.replacement_set_digest)
            .unwrap_or(false);

    let memo: RefCell<HashMap<String, bool>> = RefCell::new(HashMap::new());
    let visiting: RefCell<HashSet<String>> = RefCell::new(HashSet::new());

    let rev = reverse_deps(selections);
    let mut statuses: HashMap<String, String> = HashMap::new();
    let mut invalidations: Vec<InvalidationRow> = Vec::new();
    let mut lock_rows: Vec<LockEntryRow> = Vec::new();

    let mut name_set: BTreeSet<String> = selections.keys().cloned().collect();
    for k in prior.keys() {
        name_set.insert(k.to_string());
    }
    let names: Vec<String> = name_set.into_iter().collect();

    for name in &names {
        if let Some(sel) = selections.get(name) {
            let computed = lock_package_digest(
                name,
                &sel.candidate.version,
                &sel.selection_source,
                &sel.source_reference,
                &sel.source_digest,
                &sel.checksum,
                &dep_names(&sel.candidate),
            );
            if let Some(lp) = prior.get(name.as_str()) {
                let lp = *lp;
                let prior_digest = lock_package_digest(
                    &lp.package_name,
                    &lp.version,
                    &lp.source_kind,
                    &lp.source_reference,
                    &lp.source_digest,
                    &lp.checksum,
                    &lp.dependency_names,
                );
                let reusable = is_reusable(name, selections, &prior, digests_match_context, &memo, &visiting);
                let (status, reason) = if reusable {
                    ("reused".to_string(), None)
                } else {
                    let (cause_kind, cause_subject) =
                        invalidation_cause(lp, sel, digests_match_context, selections, &prior, &memo, &visiting);
                    let reason = if cause_kind == "upstream_invalidated" {
                        "upstream_invalidated".to_string()
                    } else {
                        "digest_mismatch".to_string()
                    };
                    invalidations.push(InvalidationRow {
                        request_id: request_id.to_string(),
                        package_name: name.clone(),
                        cause_kind,
                        cause_subject,
                        dependent_packages: rev.get(name).cloned().unwrap_or_default(),
                    });
                    ("recomputed".to_string(), Some(reason))
                };
                statuses.insert(name.clone(), status.clone());
                lock_rows.push(LockEntryRow {
                    request_id: request_id.to_string(),
                    package_name: name.clone(),
                    prior_digest_or_null: Some(prior_digest),
                    computed_digest: computed,
                    status,
                    reason_or_null: reason,
                });
            } else {
                statuses.insert(name.clone(), "recomputed".to_string());
                invalidations.push(InvalidationRow {
                    request_id: request_id.to_string(),
                    package_name: name.clone(),
                    cause_kind: "missing_lock_entry".to_string(),
                    cause_subject: name.clone(),
                    dependent_packages: rev.get(name).cloned().unwrap_or_default(),
                });
                lock_rows.push(LockEntryRow {
                    request_id: request_id.to_string(),
                    package_name: name.clone(),
                    prior_digest_or_null: None,
                    computed_digest: computed,
                    status: "recomputed".to_string(),
                    reason_or_null: Some("missing_lock_entry".to_string()),
                });
            }
        } else {
            let lp = *prior.get(name.as_str()).expect("name from union of keys");
            let prior_digest = lock_package_digest(
                &lp.package_name,
                &lp.version,
                &lp.source_kind,
                &lp.source_reference,
                &lp.source_digest,
                &lp.checksum,
                &lp.dependency_names,
            );
            lock_rows.push(LockEntryRow {
                request_id: request_id.to_string(),
                package_name: name.clone(),
                prior_digest_or_null: Some(prior_digest),
                computed_digest: String::new(),
                status: "not_selected".to_string(),
                reason_or_null: None,
            });
        }
    }

    let any_stale = selections
        .keys()
        .any(|n| statuses.get(n).map(|s| s != "reused").unwrap_or(true));

    (statuses, lock_rows, invalidations, any_stale)
}

struct RequestOutcome {
    request_id: String,
    lockfile_mode: String,
    resolver_mode: String,
    request_msrv: Option<String>,
    status: String,
    reason_or_null: Option<String>,
    selected: HashMap<String, Selection>,
    patch_rows: Vec<PatchRow>,
    replacement_rows: Vec<SourceReplacementRow>,
    lock_rows: Vec<LockEntryRow>,
    invalidation_rows: Vec<InvalidationRow>,
    conflict_rows: Vec<ConflictRow>,
    reused: usize,
    recomputed: usize,
}

impl RequestOutcome {
    fn new(req: &BuildRequest, resolver_mode: &str) -> Self {
        RequestOutcome {
            request_id: req.request_id.clone(),
            lockfile_mode: req.lockfile_mode.clone(),
            resolver_mode: resolver_mode.to_string(),
            request_msrv: None,
            status: "rejected".to_string(),
            reason_or_null: None,
            selected: HashMap::new(),
            patch_rows: Vec::new(),
            replacement_rows: Vec::new(),
            lock_rows: Vec::new(),
            invalidation_rows: Vec::new(),
            conflict_rows: Vec::new(),
            reused: 0,
            recomputed: 0,
        }
    }

    fn reject(&mut self, reason: &str, row: ConflictRow) {
        self.status = "rejected".to_string();
        self.reason_or_null = Some(reason.to_string());
        self.conflict_rows.push(row);
    }
}

fn process_request(ds: &Dataset, req: &BuildRequest) -> Result<RequestOutcome> {
    let members = member_map(ds);
    let locks = lock_map(ds);
    let patches = patch_map(ds);
    let repls = repl_map(ds);

    let mut outcome = RequestOutcome::new(req, &ds.resolver_mode);

    for mid in &req.member_ids {
        if !members.contains_key(mid.as_str()) {
            outcome.reject(
                "unknown_member",
                ConflictRow {
                    request_id: req.request_id.clone(),
                    conflict_type: "unknown_member".to_string(),
                    subject: mid.clone(),
                    reason_code: "unknown_member".to_string(),
                    related_values: sorted_unique_names(&req.member_ids),
                },
            );
            return Ok(outcome);
        }
    }
    if !locks.contains_key(req.lock_id.as_str()) {
        outcome.reject(
            "unknown_lock",
            ConflictRow {
                request_id: req.request_id.clone(),
                conflict_type: "unknown_lock".to_string(),
                subject: req.lock_id.clone(),
                reason_code: "unknown_lock".to_string(),
                related_values: vec![req.lock_id.clone()],
            },
        );
        return Ok(outcome);
    }
    if !patches.contains_key(req.patch_set_id.as_str()) {
        outcome.reject(
            "unknown_patch_set",
            ConflictRow {
                request_id: req.request_id.clone(),
                conflict_type: "unknown_patch_set".to_string(),
                subject: req.patch_set_id.clone(),
                reason_code: "unknown_patch_set".to_string(),
                related_values: vec![req.patch_set_id.clone()],
            },
        );
        return Ok(outcome);
    }
    if !repls.contains_key(req.replacement_set_id.as_str()) {
        outcome.reject(
            "unknown_replacement_set",
            ConflictRow {
                request_id: req.request_id.clone(),
                conflict_type: "unknown_replacement_set".to_string(),
                subject: req.replacement_set_id.clone(),
                reason_code: "unknown_replacement_set".to_string(),
                related_values: vec![req.replacement_set_id.clone()],
            },
        );
        return Ok(outcome);
    }

    let lock = *locks.get(req.lock_id.as_str()).expect("checked above");
    let replacement_set = *repls.get(req.replacement_set_id.as_str()).expect("checked above");

    let (selected_raw, patch_rows_internal, reason, msrv) =
        resolve_graph(ds, &req.member_ids, &req.patch_set_id, Some(lock))?;
    outcome.request_msrv = Some(msrv);

    let clean_patches: Vec<PatchRow> = patch_rows_internal
        .iter()
        .map(|row| PatchRow {
            request_id: req.request_id.clone(),
            source_id: row.source_id.clone(),
            package_name: row.package_name.clone(),
            patched_package_id: row.patched_package_id.clone(),
            patched_version: row.patched_version.clone(),
            status: row.status.clone(),
            reason_or_null: row.reason_or_null.clone(),
        })
        .collect();
    outcome.patch_rows = clean_patches.clone();

    if let Some(reason) = reason {
        match reason.as_str() {
            "patch_conflict" => {
                let mut related: Vec<String> = clean_patches.iter().map(|p| p.patched_package_id.clone()).collect();
                related.sort();
                related.dedup();
                outcome.reject(
                    "patch_conflict",
                    ConflictRow {
                        request_id: req.request_id.clone(),
                        conflict_type: "patch_conflict".to_string(),
                        subject: req.patch_set_id.clone(),
                        reason_code: "patch_conflict".to_string(),
                        related_values: related,
                    },
                );
                return Ok(outcome);
            }
            "package_version_conflict" | "resolution_round_limit" => {
                outcome.reject(
                    &reason,
                    ConflictRow {
                        request_id: req.request_id.clone(),
                        conflict_type: reason.clone(),
                        subject: req.request_id.clone(),
                        reason_code: reason.clone(),
                        related_values: sorted_unique_names(&req.member_ids),
                    },
                );
                return Ok(outcome);
            }
            _ => {}
        }
    }

    let selected_raw = selected_raw.expect("selected present when no rejection reason");
    let mut names: Vec<String> = selected_raw.keys().cloned().collect();
    names.sort();

    let mut selections: HashMap<String, Selection> = HashMap::new();
    let mut all_repl_rows: Vec<SourceReplacementRow> = Vec::new();
    for name in &names {
        let c = &selected_raw[name];
        let (sel_source, src_ref, src_digest, checksum, repl_rows, repl_reason) = project_selection(c, replacement_set);
        for rr in repl_rows {
            all_repl_rows.push(SourceReplacementRow {
                request_id: req.request_id.clone(),
                package_name: rr.package_name,
                version: rr.version,
                original_source_id: rr.original_source_id,
                replacement_source_id: rr.replacement_source_id,
                original_checksum: rr.original_checksum,
                replacement_checksum_or_null: rr.replacement_checksum_or_null,
                status: rr.status,
            });
        }
        if let Some(repl_reason) = repl_reason {
            outcome.replacement_rows = all_repl_rows;
            outcome.reject(
                &repl_reason,
                ConflictRow {
                    request_id: req.request_id.clone(),
                    conflict_type: repl_reason.clone(),
                    subject: name.clone(),
                    reason_code: repl_reason.clone(),
                    related_values: vec![name.clone(), c.version.clone()],
                },
            );
            return Ok(outcome);
        }
        let locked_ver = lock
            .selected_packages
            .iter()
            .find(|lp| lp.package_name == *name)
            .map(|lp| lp.version.clone());
        selections.insert(
            name.clone(),
            Selection {
                candidate: c.clone(),
                selection_source: sel_source,
                source_reference: src_ref,
                source_digest: src_digest,
                checksum,
                lock_status: "recomputed".to_string(),
                locked_version_or_null: locked_ver,
            },
        );
    }

    outcome.replacement_rows = all_repl_rows;
    let (statuses, lock_rows, invalidations, any_stale) =
        evaluate_lock_reuse(ds, lock, &req.patch_set_id, &req.replacement_set_id, &selections, &req.request_id);
    for (name, sel) in selections.iter_mut() {
        if let Some(st) = statuses.get(name) {
            sel.lock_status = st.clone();
        }
    }

    if req.lockfile_mode == "frozen" && any_stale {
        let mut related: Vec<String> = statuses
            .iter()
            .filter(|(_, s)| s.as_str() != "reused")
            .map(|(n, _)| n.clone())
            .collect();
        related.sort();
        outcome.reject(
            "lockfile_stale",
            ConflictRow {
                request_id: req.request_id.clone(),
                conflict_type: "lockfile_stale".to_string(),
                subject: req.lock_id.clone(),
                reason_code: "lockfile_stale".to_string(),
                related_values: related,
            },
        );
        outcome.replacement_rows = Vec::new();
        return Ok(outcome);
    }

    outcome.status = "accepted".to_string();
    outcome.reason_or_null = None;
    outcome.lock_rows = lock_rows;
    for row in invalidations {
        if statuses.get(&row.package_name).map(|s| s == "reused").unwrap_or(false) {
            continue;
        }
        if !selections.contains_key(&row.package_name) {
            continue;
        }
        outcome.invalidation_rows.push(row);
    }
    outcome.reused = statuses.values().filter(|s| s.as_str() == "reused").count();
    outcome.recomputed = statuses.values().filter(|s| s.as_str() == "recomputed").count();
    outcome.selected = selections;
    Ok(outcome)
}

pub fn build_report(ds: &Dataset) -> Result<Report> {
    let mut request_rows: Vec<RequestRow> = Vec::new();
    let mut package_selection_rows: Vec<PackageSelectionRow> = Vec::new();
    let mut patch_rows: Vec<PatchRow> = Vec::new();
    let mut source_replacement_rows: Vec<SourceReplacementRow> = Vec::new();
    let mut lock_entry_rows: Vec<LockEntryRow> = Vec::new();
    let mut invalidation_rows: Vec<InvalidationRow> = Vec::new();
    let mut conflict_rows: Vec<ConflictRow> = Vec::new();

    let mut reqs: Vec<&BuildRequest> = ds.build_requests.iter().collect();
    reqs.sort_by(|a, b| a.request_id.cmp(&b.request_id));

    for req in reqs {
        let outcome = process_request(ds, req)?;

        request_rows.push(RequestRow {
            request_id: outcome.request_id.clone(),
            lockfile_mode: outcome.lockfile_mode.clone(),
            resolver_mode: outcome.resolver_mode.clone(),
            request_msrv: outcome.request_msrv.clone(),
            status: outcome.status.clone(),
            reason_or_null: outcome.reason_or_null.clone(),
            selected_package_count: outcome.selected.len(),
            reused_lock_entry_count: if outcome.status == "accepted" { outcome.reused } else { 0 },
            recomputed_lock_entry_count: if outcome.status == "accepted" { outcome.recomputed } else { 0 },
        });

        let mut names: Vec<String> = outcome.selected.keys().cloned().collect();
        names.sort();
        if !names.is_empty() {
            let msrv_v = Version::parse(outcome.request_msrv.as_deref().unwrap_or(""))?;
            for name in &names {
                let sel = &outcome.selected[name];
                let rust_v = Version::parse(&sel.candidate.rust_version)?;
                package_selection_rows.push(PackageSelectionRow {
                    request_id: outcome.request_id.clone(),
                    package_name: name.clone(),
                    selected_version: sel.candidate.version.clone(),
                    selection_source: sel.selection_source.clone(),
                    source_reference: sel.source_reference.clone(),
                    source_digest: sel.source_digest.clone(),
                    checksum: sel.checksum.clone(),
                    rust_version: sel.candidate.rust_version.clone(),
                    msrv_compatible: rust_v <= msrv_v,
                    yanked: sel.candidate.yanked,
                    locked_version_or_null: sel.locked_version_or_null.clone(),
                    lock_status: sel.lock_status.clone(),
                });
            }
        }

        patch_rows.extend(outcome.patch_rows);
        if outcome.status == "accepted" {
            source_replacement_rows.extend(outcome.replacement_rows);
            lock_entry_rows.extend(outcome.lock_rows);
            invalidation_rows.extend(outcome.invalidation_rows);
        }
        conflict_rows.extend(outcome.conflict_rows);
    }

    package_selection_rows.sort_by(|a, b| (&a.request_id, &a.package_name).cmp(&(&b.request_id, &b.package_name)));
    patch_rows.sort_by(|a, b| {
        (&a.request_id, &a.source_id, &a.package_name, &a.patched_version)
            .cmp(&(&b.request_id, &b.source_id, &b.package_name, &b.patched_version))
    });
    source_replacement_rows.sort_by(|a, b| {
        (&a.request_id, &a.original_source_id, &a.package_name, &a.version)
            .cmp(&(&b.request_id, &b.original_source_id, &b.package_name, &b.version))
    });
    lock_entry_rows.sort_by(|a, b| (&a.request_id, &a.package_name).cmp(&(&b.request_id, &b.package_name)));
    invalidation_rows.sort_by(|a, b| {
        (&a.request_id, &a.package_name, &a.cause_kind, &a.cause_subject)
            .cmp(&(&b.request_id, &b.package_name, &b.cause_kind, &b.cause_subject))
    });
    conflict_rows.sort_by(|a, b| {
        (&a.request_id, &a.conflict_type, &a.subject, &a.reason_code)
            .cmp(&(&b.request_id, &b.conflict_type, &b.subject, &b.reason_code))
    });

    let summary = Summary {
        request_count: request_rows.len(),
        accepted_request_count: request_rows.iter().filter(|r| r.status == "accepted").count(),
        rejected_request_count: request_rows.iter().filter(|r| r.status == "rejected").count(),
        package_selection_row_count: package_selection_rows.len(),
        selected_patch_count: patch_rows.iter().filter(|r| r.status == "selected").count(),
        replacement_row_count: source_replacement_rows.len(),
        reused_lock_entry_count: lock_entry_rows.iter().filter(|r| r.status == "reused").count(),
        recomputed_lock_entry_count: lock_entry_rows.iter().filter(|r| r.status == "recomputed").count(),
        conflict_count: conflict_rows.len(),
    };

    Ok(Report {
        request_rows,
        package_selection_rows,
        patch_rows,
        source_replacement_rows,
        lock_entry_rows,
        invalidation_rows,
        conflict_rows,
        summary,
    })
}
