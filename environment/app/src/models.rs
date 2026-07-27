//! Bounded versions/requirements, typed dataset model, and whole-run input
//! validation for the offline recovery cartridge under `--data-dir`.

use std::collections::{HashMap, HashSet};
use std::path::Path;

use serde::Deserialize;
use serde_json::{json, Value};

use crate::canonical::digest_of;

#[derive(Debug)]
pub struct FatalError(pub String);

impl std::fmt::Display for FatalError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for FatalError {}

impl From<String> for FatalError {
    fn from(s: String) -> Self {
        FatalError(s)
    }
}

impl From<&str> for FatalError {
    fn from(s: &str) -> Self {
        FatalError(s.to_string())
    }
}

pub type Result<T> = std::result::Result<T, FatalError>;

fn fatal<T>(msg: impl Into<String>) -> Result<T> {
    Err(FatalError(msg.into()))
}

// ---------------------------------------------------------------------------
// Bounded N.N.N versions and =/^ requirements.
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct Version {
    pub major: u64,
    pub minor: u64,
    pub patch: u64,
}

impl Version {
    pub fn parse(text: &str) -> Result<Version> {
        let parts: Vec<&str> = text.split('.').collect();
        if parts.len() != 3 {
            return fatal(format!("malformed version: {text}"));
        }
        let mut nums = [0u64; 3];
        for (i, part) in parts.iter().enumerate() {
            if part.is_empty() || !part.bytes().all(|b| b.is_ascii_digit()) {
                return fatal(format!("malformed version: {text}"));
            }
            nums[i] = part
                .parse::<u64>()
                .map_err(|_| FatalError(format!("malformed version: {text}")))?;
        }
        Ok(Version {
            major: nums[0],
            minor: nums[1],
            patch: nums[2],
        })
    }
}

impl std::fmt::Display for Version {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}.{}.{}", self.major, self.minor, self.patch)
    }
}

#[derive(Debug, Clone, Copy)]
pub struct Requirement {
    pub kind: char,
    pub version: Version,
}

impl Requirement {
    pub fn parse(text: &str) -> Result<Requirement> {
        let mut chars = text.chars();
        let kind = match chars.next() {
            Some('=') => '=',
            Some('^') => '^',
            _ => return fatal(format!("malformed requirement: {text}")),
        };
        let rest: String = chars.collect();
        let parts: Vec<&str> = rest.split('.').collect();
        if parts.len() != 3 {
            return fatal(format!("malformed requirement: {text}"));
        }
        let version = Version::parse(&rest).map_err(|_| FatalError(format!("malformed requirement: {text}")))?;
        Ok(Requirement { kind, version })
    }

    pub fn matches(&self, candidate: &Version) -> bool {
        if self.kind == '=' {
            return *candidate == self.version;
        }
        let v = &self.version;
        if candidate < v {
            return false;
        }
        if v.major > 0 {
            return *candidate
                < Version {
                    major: v.major + 1,
                    minor: 0,
                    patch: 0,
                };
        }
        if v.minor > 0 {
            return *candidate
                < Version {
                    major: 0,
                    minor: v.minor + 1,
                    patch: 0,
                };
        }
        *candidate
            < Version {
                major: 0,
                minor: 0,
                patch: v.patch + 1,
            }
    }
}

pub fn parse_sha256(text: &str) -> Result<String> {
    let ok = text.len() == 64
        && text
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b));
    if ok {
        Ok(text.to_string())
    } else {
        fatal(format!("malformed sha256: {text}"))
    }
}

// ---------------------------------------------------------------------------
// Typed dataset model.
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct DepSpec {
    pub package_name: String,
    pub source_id: String,
    pub requirement: String,
}

#[derive(Debug, Clone)]
pub struct Member {
    pub member_id: String,
    pub package_name: String,
    pub package_version: String,
    pub rust_version: String,
    pub dependencies: Vec<DepSpec>,
}

#[derive(Debug, Clone)]
pub struct RegistryPackage {
    pub package_name: String,
    pub version: String,
    pub source_id: String,
    pub checksum: String,
    pub rust_version: String,
    pub yanked: bool,
    pub dependencies: Vec<DepSpec>,
}

#[derive(Debug, Clone)]
pub struct PatchedPackage {
    pub patched_package_id: String,
    pub package_name: String,
    pub version: String,
    pub patched_source_id: String,
    pub source_kind: String,
    pub source_reference: String,
    pub source_digest: String,
    pub rust_version: String,
    pub dependencies: Vec<DepSpec>,
}

#[derive(Debug, Clone)]
pub struct PatchEntry {
    pub source_id: String,
    pub package_name: String,
    pub patched_package_id: String,
}

#[derive(Debug, Clone)]
pub struct PatchSet {
    pub patch_set_id: String,
    pub patches: Vec<PatchEntry>,
}

#[derive(Debug, Clone)]
pub struct ReplacementMapping {
    pub original_source_id: String,
    pub replacement_source_id: String,
}

#[derive(Debug, Clone)]
pub struct ReplacementRecord {
    pub replacement_source_id: String,
    pub package_name: String,
    pub version: String,
    pub checksum: String,
    pub source_reference: String,
}

#[derive(Debug, Clone)]
pub struct ReplacementSet {
    pub replacement_set_id: String,
    pub mappings: Vec<ReplacementMapping>,
    pub replacement_records: Vec<ReplacementRecord>,
}

#[derive(Debug, Clone)]
pub struct LockPackage {
    pub package_name: String,
    pub version: String,
    pub source_kind: String,
    pub source_reference: String,
    pub source_digest: String,
    pub checksum: String,
    pub dependency_names: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct PreviousLock {
    pub lock_id: String,
    pub workspace_digest: String,
    pub patch_set_digest: String,
    pub replacement_set_digest: String,
    pub selected_packages: Vec<LockPackage>,
}

#[derive(Debug, Clone)]
pub struct BuildRequest {
    pub request_id: String,
    pub lock_id: String,
    pub patch_set_id: String,
    pub replacement_set_id: String,
    pub lockfile_mode: String,
    pub member_ids: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct Policy {
    pub maximum_packages: i64,
    pub maximum_dependency_edges: i64,
    pub maximum_resolution_rounds: i64,
    pub maximum_requests: i64,
    pub maximum_workspace_members_per_request: i64,
}

#[derive(Debug)]
pub struct Dataset {
    #[allow(dead_code)]
    pub workspace_name: String,
    pub resolver_mode: String,
    pub members: Vec<Member>,
    pub registry_packages: Vec<RegistryPackage>,
    pub patched_packages: Vec<PatchedPackage>,
    pub patch_sets: Vec<PatchSet>,
    pub replacement_sets: Vec<ReplacementSet>,
    pub previous_locks: Vec<PreviousLock>,
    pub build_requests: Vec<BuildRequest>,
    pub policy: Policy,
    pub workspace_digest: String,
    pub patch_digests: HashMap<String, String>,
    pub replacement_digests: HashMap<String, String>,
}

// ---------------------------------------------------------------------------
// Digest helpers (canonical JSON payload shapes per input_schema.md).
// ---------------------------------------------------------------------------

fn sorted_unique(values: &[String]) -> Vec<String> {
    let mut set: std::collections::BTreeSet<String> = std::collections::BTreeSet::new();
    for v in values {
        set.insert(v.clone());
    }
    set.into_iter().collect()
}

pub fn workspace_digest_value(workspace_name: &str, resolver_mode: &str, members: &[Member]) -> String {
    let mut sorted_members: Vec<&Member> = members.iter().collect();
    sorted_members.sort_by(|a, b| a.member_id.cmp(&b.member_id));
    let members_json: Vec<Value> = sorted_members
        .iter()
        .map(|m| {
            let mut deps = m.dependencies.clone();
            deps.sort_by(|a, b| a.package_name.cmp(&b.package_name));
            let deps_json: Vec<Value> = deps
                .iter()
                .map(|d| {
                    json!({
                        "package_name": d.package_name,
                        "requirement": d.requirement,
                        "source_id": d.source_id,
                    })
                })
                .collect();
            json!({
                "dependencies": deps_json,
                "member_id": m.member_id,
                "package_name": m.package_name,
                "package_version": m.package_version,
                "rust_version": m.rust_version,
            })
        })
        .collect();
    let payload = json!({
        "members": members_json,
        "resolver_mode": resolver_mode,
        "workspace_name": workspace_name,
    });
    digest_of(&payload)
}

pub fn patch_set_digest_value(ps: &PatchSet) -> String {
    let mut patches: Vec<&PatchEntry> = ps.patches.iter().collect();
    patches.sort_by(|a, b| {
        (&a.source_id, &a.package_name, &a.patched_package_id)
            .cmp(&(&b.source_id, &b.package_name, &b.patched_package_id))
    });
    let patches_json: Vec<Value> = patches
        .iter()
        .map(|p| {
            json!({
                "package_name": p.package_name,
                "patched_package_id": p.patched_package_id,
                "source_id": p.source_id,
            })
        })
        .collect();
    let payload = json!({
        "patch_set_id": ps.patch_set_id,
        "patches": patches_json,
    });
    digest_of(&payload)
}

pub fn replacement_set_digest_value(rs: &ReplacementSet) -> String {
    let mut mappings: Vec<&ReplacementMapping> = rs.mappings.iter().collect();
    mappings.sort_by(|a, b| a.original_source_id.cmp(&b.original_source_id));
    let mappings_json: Vec<Value> = mappings
        .iter()
        .map(|m| {
            json!({
                "original_source_id": m.original_source_id,
                "replacement_source_id": m.replacement_source_id,
            })
        })
        .collect();
    let mut records: Vec<&ReplacementRecord> = rs.replacement_records.iter().collect();
    records.sort_by(|a, b| {
        (&a.replacement_source_id, &a.package_name, &a.version)
            .cmp(&(&b.replacement_source_id, &b.package_name, &b.version))
    });
    let records_json: Vec<Value> = records
        .iter()
        .map(|r| {
            json!({
                "checksum": r.checksum,
                "package_name": r.package_name,
                "replacement_source_id": r.replacement_source_id,
                "source_reference": r.source_reference,
                "version": r.version,
            })
        })
        .collect();
    let payload = json!({
        "mappings": mappings_json,
        "replacement_records": records_json,
        "replacement_set_id": rs.replacement_set_id,
    });
    digest_of(&payload)
}

pub fn registry_source_digest(package_name: &str, version: &str, source_id: &str, checksum: &str) -> String {
    digest_of(&json!({
        "checksum": checksum,
        "package_name": package_name,
        "source_id": source_id,
        "version": version,
    }))
}

pub fn lock_package_digest(
    package_name: &str,
    version: &str,
    source_kind: &str,
    source_reference: &str,
    source_digest: &str,
    checksum: &str,
    dependency_names: &[String],
) -> String {
    digest_of(&json!({
        "checksum": checksum,
        "dependency_names": sorted_unique(dependency_names),
        "package_name": package_name,
        "source_digest": source_digest,
        "source_kind": source_kind,
        "source_reference": source_reference,
        "version": version,
    }))
}

// ---------------------------------------------------------------------------
// Raw (loosely typed) JSON shapes used only during load/validate.
// ---------------------------------------------------------------------------

#[derive(Debug, Deserialize)]
struct RawDepSpec {
    package_name: String,
    source_id: String,
    requirement: String,
}

#[derive(Debug, Deserialize)]
struct RawMember {
    member_id: String,
    package_name: String,
    package_version: String,
    rust_version: String,
    dependencies: Vec<RawDepSpec>,
}

#[derive(Debug, Deserialize)]
struct RawWorkspace {
    workspace_name: String,
    resolver_mode: String,
    members: Vec<RawMember>,
}

#[derive(Debug, Deserialize)]
struct RawRegistryPackage {
    package_name: String,
    version: String,
    source_id: String,
    checksum: String,
    rust_version: String,
    yanked: bool,
    dependencies: Vec<RawDepSpec>,
}

#[derive(Debug, Deserialize)]
struct RawPatchedPackage {
    patched_package_id: String,
    package_name: String,
    version: String,
    patched_source_id: String,
    source_kind: String,
    source_reference: String,
    source_digest: String,
    rust_version: String,
    dependencies: Vec<RawDepSpec>,
}

#[derive(Debug, Deserialize)]
struct RawPatchEntry {
    source_id: String,
    package_name: String,
    patched_package_id: String,
}

#[derive(Debug, Deserialize)]
struct RawPatchSet {
    patch_set_id: String,
    #[serde(default)]
    patches: Vec<RawPatchEntry>,
}

#[derive(Debug, Deserialize)]
struct RawMapping {
    original_source_id: String,
    replacement_source_id: String,
}

#[derive(Debug, Deserialize)]
struct RawReplRecord {
    replacement_source_id: String,
    package_name: String,
    version: String,
    checksum: String,
    source_reference: String,
}

#[derive(Debug, Deserialize)]
struct RawReplacementSet {
    replacement_set_id: String,
    #[serde(default)]
    mappings: Vec<RawMapping>,
    #[serde(default)]
    replacement_records: Vec<RawReplRecord>,
}

#[derive(Debug, Deserialize)]
struct RawLockPackage {
    package_name: String,
    version: String,
    source_kind: String,
    source_reference: String,
    source_digest: String,
    checksum: String,
    dependency_names: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct RawPreviousLock {
    lock_id: String,
    workspace_digest: String,
    patch_set_digest: String,
    replacement_set_digest: String,
    #[serde(default)]
    selected_packages: Vec<RawLockPackage>,
}

#[derive(Debug, Deserialize)]
struct RawBuildRequest {
    request_id: String,
    lock_id: String,
    patch_set_id: String,
    replacement_set_id: String,
    lockfile_mode: String,
    member_ids: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct RawPolicy {
    maximum_packages: i64,
    maximum_dependency_edges: i64,
    maximum_resolution_rounds: i64,
    maximum_requests: i64,
    maximum_workspace_members_per_request: i64,
}

fn validate_deps(raw: Vec<RawDepSpec>, ctx: &str) -> Result<Vec<DepSpec>> {
    let mut seen: HashSet<String> = HashSet::new();
    let mut out = Vec::with_capacity(raw.len());
    for d in raw {
        Requirement::parse(&d.requirement)?;
        if !seen.insert(d.package_name.clone()) {
            return fatal(format!("{ctx}: duplicate dependency {}", d.package_name));
        }
        out.push(DepSpec {
            package_name: d.package_name,
            source_id: d.source_id,
            requirement: d.requirement,
        });
    }
    Ok(out)
}

fn load_json(path: &Path) -> Result<Value> {
    let text = std::fs::read_to_string(path)
        .map_err(|e| FatalError(format!("unreadable json: {}: {e}", path.display())))?;
    serde_json::from_str(&text).map_err(|e| FatalError(format!("unreadable json: {}: {e}", path.display())))
}

fn from_value<T: for<'de> Deserialize<'de>>(value: Value, ctx: &str) -> Result<T> {
    serde_json::from_value(value).map_err(|e| FatalError(format!("{ctx}: {e}")))
}

pub fn load_dataset(data_dir: &Path) -> Result<Dataset> {
    let required = [
        "workspace.json",
        "registry_packages.json",
        "patched_packages.json",
        "patch_sets.json",
        "replacement_sources.json",
        "previous_locks.json",
        "build_requests.ndjson",
        "policy.json",
    ];
    for name in required {
        if !data_dir.join(name).is_file() {
            return fatal(format!("missing required input file: {name}"));
        }
    }

    // workspace.json
    let ws_value = load_json(&data_dir.join("workspace.json"))?;
    if !ws_value.is_object() {
        return fatal("workspace.json must be object");
    }
    let ws_raw: RawWorkspace = from_value(ws_value, "workspace.json")?;
    if ws_raw.resolver_mode != "allow" && ws_raw.resolver_mode != "fallback" {
        return fatal("invalid resolver_mode");
    }

    let mut members: Vec<Member> = Vec::new();
    let mut member_ids: HashSet<String> = HashSet::new();
    for item in ws_raw.members {
        if item.member_id.is_empty() || member_ids.contains(&item.member_id) {
            return fatal("duplicate or invalid member_id");
        }
        member_ids.insert(item.member_id.clone());
        Version::parse(&item.package_version)?;
        Version::parse(&item.rust_version)?;
        let deps = validate_deps(item.dependencies, &format!("member {}", item.member_id))?;
        members.push(Member {
            member_id: item.member_id,
            package_name: item.package_name,
            package_version: item.package_version,
            rust_version: item.rust_version,
            dependencies: deps,
        });
    }

    // registry_packages.json
    let reg_value = load_json(&data_dir.join("registry_packages.json"))?;
    if !reg_value.is_array() {
        return fatal("registry_packages.json must be array");
    }
    let reg_raw: Vec<RawRegistryPackage> = from_value(reg_value, "registry_packages.json")?;
    let mut registry: Vec<RegistryPackage> = Vec::new();
    let mut reg_ids: HashSet<(String, String, String)> = HashSet::new();
    let mut edge_count: i64 = 0;
    for item in reg_raw {
        Version::parse(&item.version)?;
        Version::parse(&item.rust_version)?;
        let checksum = parse_sha256(&item.checksum)?;
        let key = (item.source_id.clone(), item.package_name.clone(), item.version.clone());
        if reg_ids.contains(&key) {
            return fatal(format!(
                "duplicate registry package {:?}",
                key
            ));
        }
        reg_ids.insert(key);
        let deps = validate_deps(item.dependencies, "registry package")?;
        edge_count += deps.len() as i64;
        registry.push(RegistryPackage {
            package_name: item.package_name,
            version: item.version,
            source_id: item.source_id,
            checksum,
            rust_version: item.rust_version,
            yanked: item.yanked,
            dependencies: deps,
        });
    }

    // patched_packages.json
    let pat_value = load_json(&data_dir.join("patched_packages.json"))?;
    if !pat_value.is_array() {
        return fatal("patched_packages.json must be array");
    }
    let pat_raw: Vec<RawPatchedPackage> = from_value(pat_value, "patched_packages.json")?;
    let mut patched: Vec<PatchedPackage> = Vec::new();
    let mut patched_ids: HashSet<String> = HashSet::new();
    for item in pat_raw {
        if patched_ids.contains(&item.patched_package_id) {
            return fatal(format!("duplicate patched_package_id {}", item.patched_package_id));
        }
        patched_ids.insert(item.patched_package_id.clone());
        if item.source_kind != "path_snapshot" && item.source_kind != "git_snapshot" {
            return fatal("invalid source_kind");
        }
        Version::parse(&item.version)?;
        Version::parse(&item.rust_version)?;
        parse_sha256(&item.source_digest)?;
        let deps = validate_deps(item.dependencies, &format!("patched {}", item.patched_package_id))?;
        edge_count += deps.len() as i64;
        patched.push(PatchedPackage {
            patched_package_id: item.patched_package_id,
            package_name: item.package_name,
            version: item.version,
            patched_source_id: item.patched_source_id,
            source_kind: item.source_kind,
            source_reference: item.source_reference,
            source_digest: item.source_digest,
            rust_version: item.rust_version,
            dependencies: deps,
        });
    }

    // patch_sets.json
    let ps_value = load_json(&data_dir.join("patch_sets.json"))?;
    if !ps_value.is_array() {
        return fatal("patch_sets.json must be array");
    }
    let ps_raw: Vec<RawPatchSet> = from_value(ps_value, "patch_sets.json")?;
    let mut patch_sets: Vec<PatchSet> = Vec::new();
    let mut ps_ids: HashSet<String> = HashSet::new();
    for item in ps_raw {
        if ps_ids.contains(&item.patch_set_id) {
            return fatal(format!("duplicate patch_set_id {}", item.patch_set_id));
        }
        ps_ids.insert(item.patch_set_id.clone());
        let mut patches = Vec::with_capacity(item.patches.len());
        for p in item.patches {
            if !patched_ids.contains(&p.patched_package_id) {
                return fatal(format!("unknown patched_package_id {}", p.patched_package_id));
            }
            patches.push(PatchEntry {
                source_id: p.source_id,
                package_name: p.package_name,
                patched_package_id: p.patched_package_id,
            });
        }
        patch_sets.push(PatchSet {
            patch_set_id: item.patch_set_id,
            patches,
        });
    }

    // replacement_sources.json
    let rs_value = load_json(&data_dir.join("replacement_sources.json"))?;
    if !rs_value.is_array() {
        return fatal("replacement_sources.json must be array");
    }
    let rs_raw: Vec<RawReplacementSet> = from_value(rs_value, "replacement_sources.json")?;
    let mut replacement_sets: Vec<ReplacementSet> = Vec::new();
    let mut rs_ids: HashSet<String> = HashSet::new();
    for item in rs_raw {
        if rs_ids.contains(&item.replacement_set_id) {
            return fatal(format!("duplicate replacement_set_id {}", item.replacement_set_id));
        }
        rs_ids.insert(item.replacement_set_id.clone());
        let mut mappings = Vec::with_capacity(item.mappings.len());
        let mut seen_orig: HashSet<String> = HashSet::new();
        for m in item.mappings {
            if !seen_orig.insert(m.original_source_id.clone()) {
                return fatal("duplicate original_source_id in replacement set");
            }
            mappings.push(ReplacementMapping {
                original_source_id: m.original_source_id,
                replacement_source_id: m.replacement_source_id,
            });
        }
        let mut records = Vec::with_capacity(item.replacement_records.len());
        let mut seen_rec: HashSet<(String, String, String)> = HashSet::new();
        for r in item.replacement_records {
            let key = (
                r.replacement_source_id.clone(),
                r.package_name.clone(),
                r.version.clone(),
            );
            if !seen_rec.insert(key.clone()) {
                return fatal(format!("duplicate replacement record {:?}", key));
            }
            Version::parse(&r.version)?;
            let checksum = parse_sha256(&r.checksum)?;
            records.push(ReplacementRecord {
                replacement_source_id: r.replacement_source_id,
                package_name: r.package_name,
                version: r.version,
                checksum,
                source_reference: r.source_reference,
            });
        }
        replacement_sets.push(ReplacementSet {
            replacement_set_id: item.replacement_set_id,
            mappings,
            replacement_records: records,
        });
    }

    // previous_locks.json
    let lock_value = load_json(&data_dir.join("previous_locks.json"))?;
    if !lock_value.is_array() {
        return fatal("previous_locks.json must be array");
    }
    let lock_raw: Vec<RawPreviousLock> = from_value(lock_value, "previous_locks.json")?;
    let mut locks: Vec<PreviousLock> = Vec::new();
    let mut lock_ids: HashSet<String> = HashSet::new();
    for item in lock_raw {
        if lock_ids.contains(&item.lock_id) {
            return fatal(format!("duplicate lock_id {}", item.lock_id));
        }
        lock_ids.insert(item.lock_id.clone());
        let workspace_digest = parse_sha256(&item.workspace_digest)?;
        let patch_set_digest = parse_sha256(&item.patch_set_digest)?;
        let replacement_set_digest = parse_sha256(&item.replacement_set_digest)?;
        let mut pkgs = Vec::with_capacity(item.selected_packages.len());
        let mut seen_pkg: HashSet<String> = HashSet::new();
        for p in item.selected_packages {
            if !seen_pkg.insert(p.package_name.clone()) {
                return fatal("duplicate lock package");
            }
            Version::parse(&p.version)?;
            let source_digest = parse_sha256(&p.source_digest)?;
            let checksum = parse_sha256(&p.checksum)?;
            if !matches!(
                p.source_kind.as_str(),
                "registry" | "patched_path" | "patched_git_snapshot" | "replacement_registry"
            ) {
                return fatal("invalid lock source_kind");
            }
            pkgs.push(LockPackage {
                package_name: p.package_name,
                version: p.version,
                source_kind: p.source_kind,
                source_reference: p.source_reference,
                source_digest,
                checksum,
                dependency_names: p.dependency_names,
            });
        }
        locks.push(PreviousLock {
            lock_id: item.lock_id,
            workspace_digest,
            patch_set_digest,
            replacement_set_digest,
            selected_packages: pkgs,
        });
    }

    // build_requests.ndjson
    let req_path = data_dir.join("build_requests.ndjson");
    let req_text = std::fs::read_to_string(&req_path)
        .map_err(|e| FatalError(format!("unreadable ndjson: {e}")))?;
    let mut requests: Vec<BuildRequest> = Vec::new();
    let mut req_ids: HashSet<String> = HashSet::new();
    for (line_no, line) in req_text.lines().enumerate() {
        if line.trim().is_empty() {
            continue;
        }
        let value: Value = serde_json::from_str(line)
            .map_err(|e| FatalError(format!("bad ndjson line {}: {e}", line_no + 1)))?;
        if !value.is_object() {
            return fatal(format!("ndjson line {} must be object", line_no + 1));
        }
        let item: RawBuildRequest = from_value(value, "build_requests.ndjson")?;
        if req_ids.contains(&item.request_id) {
            return fatal(format!("duplicate request_id {}", item.request_id));
        }
        req_ids.insert(item.request_id.clone());
        if item.lockfile_mode != "frozen" && item.lockfile_mode != "update" {
            return fatal("invalid lockfile_mode");
        }
        let unique: HashSet<&String> = item.member_ids.iter().collect();
        if unique.len() != item.member_ids.len() {
            return fatal("member_ids must be unique array");
        }
        requests.push(BuildRequest {
            request_id: item.request_id,
            lock_id: item.lock_id,
            patch_set_id: item.patch_set_id,
            replacement_set_id: item.replacement_set_id,
            lockfile_mode: item.lockfile_mode,
            member_ids: item.member_ids,
        });
    }

    // policy.json
    let pol_value = load_json(&data_dir.join("policy.json"))?;
    if !pol_value.is_object() {
        return fatal("policy.json must be object");
    }
    let pol_raw: RawPolicy = from_value(pol_value, "policy.json")?;
    let policy = Policy {
        maximum_packages: pol_raw.maximum_packages,
        maximum_dependency_edges: pol_raw.maximum_dependency_edges,
        maximum_resolution_rounds: pol_raw.maximum_resolution_rounds,
        maximum_requests: pol_raw.maximum_requests,
        maximum_workspace_members_per_request: pol_raw.maximum_workspace_members_per_request,
    };

    let member_edge_count: i64 = members.iter().map(|m| m.dependencies.len() as i64).sum();
    let total_edges = edge_count + member_edge_count;
    if (registry.len() + patched.len()) as i64 > policy.maximum_packages {
        return fatal("policy maximum_packages exceeded");
    }
    if total_edges > policy.maximum_dependency_edges {
        return fatal("policy maximum_dependency_edges exceeded");
    }
    if requests.len() as i64 > policy.maximum_requests {
        return fatal("policy maximum_requests exceeded");
    }
    for req in &requests {
        if req.member_ids.len() as i64 > policy.maximum_workspace_members_per_request {
            return fatal("policy maximum_workspace_members_per_request exceeded");
        }
    }

    let workspace_digest = workspace_digest_value(&ws_raw.workspace_name, &ws_raw.resolver_mode, &members);
    let patch_digests: HashMap<String, String> = patch_sets
        .iter()
        .map(|p| (p.patch_set_id.clone(), patch_set_digest_value(p)))
        .collect();
    let replacement_digests: HashMap<String, String> = replacement_sets
        .iter()
        .map(|r| (r.replacement_set_id.clone(), replacement_set_digest_value(r)))
        .collect();

    Ok(Dataset {
        workspace_name: ws_raw.workspace_name,
        resolver_mode: ws_raw.resolver_mode,
        members,
        registry_packages: registry,
        patched_packages: patched,
        patch_sets,
        replacement_sets,
        previous_locks: locks,
        build_requests: requests,
        policy,
        workspace_digest,
        patch_digests,
        replacement_digests,
    })
}
