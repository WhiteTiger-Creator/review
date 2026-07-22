//! Bootstrap planner orchestration: load local inputs, fetch per-environment
//! policy snapshots over localhost HTTP, plan each cluster (merge policy with
//! local resources, validate, build an operation DAG), then render the
//! accepted clusters into `bootstrap.sql` and `bootstrap_plan.json`.
//!
//! This mirrors `tests/reference/planner.py` (plus `reference/hba.py` and
//! `reference/sql.py`) statement-for-statement so that oracle output matches
//! the independent Python reference implementation.

use crate::api::{self, PolicySnapshot};
use crate::canonical::{quote_ident, quote_string, sha256_hex};
use crate::error::FatalError;
use crate::models::*;
use crate::output;
use serde::de::DeserializeOwned;
use serde_json::Value;
use std::collections::{BTreeSet, HashMap, HashSet};
use std::path::Path;

const VALID_ENVIRONMENTS: [&str; 3] = ["development", "staging", "production"];
const BOOL_ROLE_ATTRS: [&str; 6] = [
    "login",
    "inherit",
    "createdb",
    "createrole",
    "replication",
    "bypassrls",
];
const FRAGMENT_ORDER: [&str; 3] = ["identity", "database", "access"];

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

pub fn run(
    yaml: &Path,
    toml_path: &Path,
    extension_catalog: &Path,
    setting_catalog: &Path,
    policy_url: &str,
    sql_out: &Path,
    plan_out: &Path,
) -> Result<u8, FatalError> {
    output::remove_stale_outputs(sql_out, plan_out)?;
    match plan_all(
        yaml,
        toml_path,
        extension_catalog,
        setting_catalog,
        policy_url,
    ) {
        Ok((sql_text, plan)) => {
            let plan_json = serde_json::to_string_pretty(&plan)
                .map_err(|e| FatalError::new("output_write_failed", e.to_string()))?
                + "\n";
            output::write_atomic(sql_out, sql_text.as_bytes())?;
            output::write_atomic(plan_out, plan_json.as_bytes())?;
            let has_rows = !plan.cluster_rows.is_empty();
            Ok(if has_rows { 0 } else { 1 })
        }
        Err(e) => {
            output::remove_stale_outputs(sql_out, plan_out)?;
            Err(e)
        }
    }
}

fn plan_all(
    yaml: &Path,
    toml_path: &Path,
    extension_catalog: &Path,
    setting_catalog: &Path,
    policy_url: &str,
) -> Result<(String, BootstrapPlan), FatalError> {
    for path in [yaml, toml_path, extension_catalog, setting_catalog] {
        if !path.is_file() {
            return Err(FatalError::new(
                "missing_required_input",
                path.display().to_string(),
            ));
        }
    }

    let clusters = load_clusters_doc(yaml)?;
    let settings_local = load_settings_doc(toml_path)?;
    let ext_catalog_doc = load_extension_catalog(extension_catalog)?;
    let setting_catalog_doc = load_setting_catalog(setting_catalog)?;

    let cluster_ids: Vec<&str> = clusters.iter().map(|c| c.cluster_id.as_str()).collect();
    let unique_ids: HashSet<&str> = cluster_ids.iter().copied().collect();
    if unique_ids.len() != cluster_ids.len() {
        return Err(FatalError::new("duplicate_cluster_id", ""));
    }

    for cluster in &clusters {
        ensure_unique_ids(cluster.roles.iter().map(|r| r.role_id.as_str()))?;
        ensure_unique_ids(cluster.roles.iter().map(|r| r.role_name.as_str()))?;
        ensure_unique_ids(
            cluster
                .role_memberships
                .iter()
                .map(|m| m.membership_id.as_str()),
        )?;
        ensure_unique_ids(cluster.databases.iter().map(|d| d.database_id.as_str()))?;
        ensure_unique_ids(cluster.databases.iter().map(|d| d.database_name.as_str()))?;
        ensure_unique_ids(
            cluster
                .extensions
                .iter()
                .map(|e| e.extension_request_id.as_str()),
        )?;
        ensure_unique_ids(cluster.privileges.iter().map(|p| p.grant_id.as_str()))?;
        ensure_unique_ids(cluster.hba_rules.iter().map(|h| h.hba_id.as_str()))?;
    }
    ensure_unique_ids(settings_local.iter().map(|s| s.setting_id.as_str()))?;

    let ext_catalog: HashMap<String, ExtensionCatalogEntry> = ext_catalog_doc
        .extensions
        .into_iter()
        .map(|e| (e.extension_id.clone(), e))
        .collect();
    let setting_catalog_map: HashMap<String, SettingCatalogEntry> = setting_catalog_doc
        .settings
        .into_iter()
        .map(|s| (s.setting_name.clone(), s))
        .collect();

    let mut environments: Vec<String> = clusters.iter().map(|c| c.environment.clone()).collect();
    environments.sort();
    environments.dedup();
    for env in &environments {
        if !VALID_ENVIRONMENTS.contains(&env.as_str()) {
            return Err(FatalError::new("unknown_local_environment", env.clone()));
        }
    }

    let mut snapshots: HashMap<String, PolicySnapshot> = HashMap::new();
    for env in &environments {
        let snap = api::fetch_snapshot(policy_url, env)?;
        snapshots.insert(env.clone(), snap);
    }

    let mut sorted_clusters: Vec<&ClusterInput> = clusters.iter().collect();
    sorted_clusters.sort_by(|a, b| a.cluster_id.cmp(&b.cluster_id));

    let mut cluster_rows: Vec<ClusterRow> = Vec::new();
    let mut rejection_rows: Vec<RejectionRow> = Vec::new();
    let mut accepted: Vec<AcceptedCluster> = Vec::new();

    for cluster in &sorted_clusters {
        let snap = snapshots.get(&cluster.environment).expect("fetched above");
        match plan_cluster(cluster, &settings_local, &ext_catalog, &setting_catalog_map, snap) {
            Ok(mut ac) => {
                ac.phase_count = build_phases(&ac, &setting_catalog_map).len() as i64;
                cluster_rows.push(ClusterRow {
                    cluster_id: ac.cluster_id.clone(),
                    environment: ac.environment.clone(),
                    status: "accepted".to_string(),
                    reason_or_null: None,
                    requires_reload: ac.requires_reload,
                    requires_restart: ac.requires_restart,
                    role_count: ac.roles.len() as i64,
                    database_count: ac.databases.len() as i64,
                    extension_count: ac.extensions.len() as i64,
                    privilege_count: ac.privileges.len() as i64,
                    hba_count: ac.hba_rows.len() as i64,
                    setting_count: ac.settings.len() as i64,
                    operation_count: ac.operations.len() as i64,
                    phase_count: ac.phase_count,
                });
                accepted.push(ac);
            }
            Err(rej) => {
                cluster_rows.push(ClusterRow {
                    cluster_id: cluster.cluster_id.clone(),
                    environment: cluster.environment.clone(),
                    status: "rejected".to_string(),
                    reason_or_null: Some(rej.reason.clone()),
                    requires_reload: false,
                    requires_restart: false,
                    role_count: 0,
                    database_count: 0,
                    extension_count: 0,
                    privilege_count: 0,
                    hba_count: 0,
                    setting_count: 0,
                    operation_count: 0,
                    phase_count: 0,
                });
                rejection_rows.push(rej);
            }
        }
    }

    let mut sql_blocks: Vec<String> = Vec::new();
    let mut role_rows: Vec<RoleRow> = Vec::new();
    let mut membership_rows: Vec<MembershipRow> = Vec::new();
    let mut database_rows: Vec<DatabaseRow> = Vec::new();
    let mut extension_rows: Vec<ExtensionRow> = Vec::new();
    let mut privilege_rows: Vec<PrivilegeRow> = Vec::new();
    let mut hba_rows: Vec<HbaRow> = Vec::new();
    let mut setting_rows: Vec<SettingRow> = Vec::new();
    let mut operation_rows: Vec<OperationRow> = Vec::new();
    let mut phase_rows: Vec<PhaseRow> = Vec::new();

    for ac in &accepted {
        let cid = &ac.cluster_id;
        for r in &ac.roles {
            role_rows.push(RoleRow {
                cluster_id: cid.clone(),
                role_id: r.role_id.clone(),
                role_name: r.role_name.clone(),
                source: r.source.clone(),
                login: r.login,
                inherit: r.inherit,
                createdb: r.createdb,
                createrole: r.createrole,
                replication: r.replication,
                bypassrls: r.bypassrls,
                connection_limit: r.connection_limit,
            });
        }
        for m in &ac.memberships {
            membership_rows.push(MembershipRow {
                cluster_id: cid.clone(),
                membership_id: m.membership_id.clone(),
                member_role_id: m.member_role_id.clone(),
                granted_role_id: m.granted_role_id.clone(),
                source: m.source.clone(),
            });
        }
        for d in &ac.databases {
            database_rows.push(DatabaseRow {
                cluster_id: cid.clone(),
                database_id: d.database_id.clone(),
                database_name: d.database_name.clone(),
                owner_role_id: d.owner_role_id.clone(),
                template: d.template.clone(),
                encoding: d.encoding.clone(),
                connection_limit: d.connection_limit,
                source: d.source.clone(),
            });
        }
        for e in &ac.extensions {
            extension_rows.push(ExtensionRow {
                cluster_id: cid.clone(),
                database_id: e.database_id.clone(),
                extension_id: e.extension_id.clone(),
                version: e.version.clone(),
                selection_reason: e.selection_reason.clone(),
                dependency_depth: e.dependency_depth,
                topological_position: e.topological_position,
            });
        }
        for p in &ac.privileges {
            privilege_rows.push(PrivilegeRow {
                cluster_id: cid.clone(),
                grant_id: p.grant_id.clone(),
                scope: p.scope.clone(),
                database_id: p.database_id.clone(),
                schema_name_or_null: p.schema_name_or_null.clone(),
                table_name_or_null: p.table_name_or_null.clone(),
                grantee_role_id: p.grantee_role_id.clone(),
                privileges: p.privileges.clone(),
                grant_option: p.grant_option,
                source: p.source.clone(),
            });
        }
        for h in &ac.hba_rows {
            hba_rows.push(HbaRow {
                cluster_id: cid.clone(),
                hba_position: h.hba_position,
                hba_id: h.hba_id.clone(),
                connection_type: h.connection_type.clone(),
                database_selector: h.database_selector.clone(),
                role_selector: h.role_selector.clone(),
                ipv4_cidr_or_null: h.ipv4_cidr_or_null.clone(),
                auth_method: h.auth_method.clone(),
                source: h.source.clone(),
                mandatory: h.mandatory,
                priority: h.priority,
            });
        }
        for s in &ac.settings {
            setting_rows.push(SettingRow {
                cluster_id: cid.clone(),
                setting_id: s.setting_id.clone(),
                scope: s.scope.clone(),
                database_id_or_null: s.database_id_or_null.clone(),
                role_id_or_null: s.role_id_or_null.clone(),
                setting_name: s.setting_name.clone(),
                normalized_value: s.normalized_value.clone(),
                activation_mode: s.activation_mode.clone(),
                transaction_compatible: s.transaction_compatible,
                source: s.source.clone(),
            });
        }
        let phases = build_phases(ac, &setting_catalog_map);
        let mut op_phase: HashMap<String, i64> = HashMap::new();
        for p in &phases {
            for oid in &p.operation_ids {
                op_phase.insert(oid.clone(), p.phase_index);
            }
        }
        for o in &ac.operations {
            operation_rows.push(OperationRow {
                cluster_id: cid.clone(),
                operation_id: o.operation_id.clone(),
                operation_kind: if o.operation_kind == "extension" {
                    "create_extension".to_string()
                } else {
                    o.operation_kind.clone()
                },
                resource_id: o.resource_id.clone(),
                database_id_or_null: o.database_id_or_null.clone(),
                depends_on_operation_ids: o.depends_on_operation_ids.clone(),
                topological_position: o.topological_position,
                phase_index: *op_phase.get(&o.operation_id).unwrap_or(&0),
            });
        }
        for p in &phases {
            phase_rows.push(PhaseRow {
                cluster_id: cid.clone(),
                phase_index: p.phase_index,
                phase_kind: p.phase_kind.clone(),
                database_id_or_null: p.database_id_or_null.clone(),
                transactional: p.transactional,
                operation_ids: p.operation_ids.clone(),
                requires_reload: p.requires_reload,
                requires_restart: p.requires_restart,
            });
        }
        let block = serialize_phases(&phases, cid);
        if !block.is_empty() {
            sql_blocks.push(block);
        }
    }

    let mut sql_text = sql_blocks.join("\n");
    if !sql_text.is_empty() && !sql_text.ends_with('\n') {
        sql_text.push('\n');
    }
    let sql_digest = sha256_hex(sql_text.as_bytes());

    let mut env_sorted: Vec<&String> = snapshots.keys().collect();
    env_sorted.sort();
    let policy_snapshot_rows: Vec<PolicySnapshotRow> = env_sorted
        .into_iter()
        .map(|env| {
            let snap = &snapshots[env];
            PolicySnapshotRow {
                environment: env.clone(),
                policy_revision: snap.policy_revision.clone(),
                fragment_rows: snap
                    .fragment_rows
                    .iter()
                    .map(|(fid, digest)| FragmentRow {
                        fragment_id: fid.clone(),
                        body_sha256: digest.clone(),
                    })
                    .collect(),
            }
        })
        .collect();

    cluster_rows.sort_by(|a, b| a.cluster_id.cmp(&b.cluster_id));
    role_rows.sort_by(|a, b| (&a.cluster_id, &a.role_id).cmp(&(&b.cluster_id, &b.role_id)));
    membership_rows.sort_by(|a, b| {
        (&a.cluster_id, &a.member_role_id, &a.granted_role_id, &a.membership_id).cmp(&(
            &b.cluster_id,
            &b.member_role_id,
            &b.granted_role_id,
            &b.membership_id,
        ))
    });
    database_rows
        .sort_by(|a, b| (&a.cluster_id, &a.database_id).cmp(&(&b.cluster_id, &b.database_id)));
    extension_rows.sort_by(|a, b| {
        (&a.cluster_id, &a.database_id, a.topological_position, &a.extension_id).cmp(&(
            &b.cluster_id,
            &b.database_id,
            b.topological_position,
            &b.extension_id,
        ))
    });
    privilege_rows.sort_by(|a, b| {
        let ka = (
            &a.cluster_id,
            &a.database_id,
            scope_rank(&a.scope),
            a.schema_name_or_null.clone().unwrap_or_default(),
            a.table_name_or_null.clone().unwrap_or_default(),
            &a.grantee_role_id,
            &a.grant_id,
        );
        let kb = (
            &b.cluster_id,
            &b.database_id,
            scope_rank(&b.scope),
            b.schema_name_or_null.clone().unwrap_or_default(),
            b.table_name_or_null.clone().unwrap_or_default(),
            &b.grantee_role_id,
            &b.grant_id,
        );
        ka.cmp(&kb)
    });
    hba_rows.sort_by(|a, b| (&a.cluster_id, a.hba_position).cmp(&(&b.cluster_id, b.hba_position)));
    setting_rows.sort_by(|a, b| {
        let ka = (
            &a.cluster_id,
            setting_scope_rank(&a.scope),
            a.database_id_or_null.clone().unwrap_or_default(),
            a.role_id_or_null.clone().unwrap_or_default(),
            &a.setting_name,
            &a.setting_id,
        );
        let kb = (
            &b.cluster_id,
            setting_scope_rank(&b.scope),
            b.database_id_or_null.clone().unwrap_or_default(),
            b.role_id_or_null.clone().unwrap_or_default(),
            &b.setting_name,
            &b.setting_id,
        );
        ka.cmp(&kb)
    });
    operation_rows.sort_by(|a, b| {
        (&a.cluster_id, a.topological_position, &a.operation_id).cmp(&(
            &b.cluster_id,
            b.topological_position,
            &b.operation_id,
        ))
    });
    phase_rows.sort_by(|a, b| (&a.cluster_id, a.phase_index).cmp(&(&b.cluster_id, b.phase_index)));
    rejection_rows.sort_by(|a, b| a.cluster_id.cmp(&b.cluster_id));

    let accepted_count = cluster_rows.iter().filter(|c| c.status == "accepted").count() as i64;
    let rejected_count = cluster_rows.iter().filter(|c| c.status == "rejected").count() as i64;
    let reload_required = cluster_rows.iter().filter(|c| c.requires_reload).count() as i64;
    let restart_required = cluster_rows.iter().filter(|c| c.requires_restart).count() as i64;

    let summary = Summary {
        cluster_count: cluster_rows.len() as i64,
        accepted_cluster_count: accepted_count,
        rejected_cluster_count: rejected_count,
        policy_snapshot_count: snapshots.len() as i64,
        role_count: role_rows.len() as i64,
        membership_count: membership_rows.len() as i64,
        database_count: database_rows.len() as i64,
        extension_count: extension_rows.len() as i64,
        privilege_count: privilege_rows.len() as i64,
        hba_count: hba_rows.len() as i64,
        setting_count: setting_rows.len() as i64,
        operation_count: operation_rows.len() as i64,
        phase_count: phase_rows.len() as i64,
        reload_required_cluster_count: reload_required,
        restart_required_cluster_count: restart_required,
    };

    let plan = BootstrapPlan {
        schema_version: 1,
        policy_snapshot_rows,
        cluster_rows,
        role_rows,
        membership_rows,
        database_rows,
        extension_rows,
        privilege_rows,
        hba_rows,
        setting_rows,
        operation_rows,
        phase_rows,
        rejection_rows,
        summary,
        sql_sha256: sql_digest,
    };

    Ok((sql_text, plan))
}

fn scope_rank(scope: &str) -> i32 {
    match scope {
        "database" => 0,
        "schema" => 1,
        "table" => 2,
        _ => 9,
    }
}

fn setting_scope_rank(scope: &str) -> i32 {
    match scope {
        "system" => 0,
        "database" => 1,
        "role" => 2,
        "role_database" => 3,
        _ => 9,
    }
}

// ---------------------------------------------------------------------------
// Local input loading
// ---------------------------------------------------------------------------

fn ensure_unique_ids<'a, I>(ids: I) -> Result<(), FatalError>
where
    I: IntoIterator<Item = &'a str>,
{
    let mut seen = HashSet::new();
    for id in ids {
        if !seen.insert(id) {
            return Err(FatalError::new("duplicate_local_resource_id", ""));
        }
    }
    Ok(())
}

fn load_clusters_doc(path: &Path) -> Result<Vec<ClusterInput>, FatalError> {
    let text = std::fs::read_to_string(path)
        .map_err(|_| FatalError::new("missing_required_input", path.display().to_string()))?;
    let yaml_value: serde_yaml::Value =
        serde_yaml::from_str(&text).map_err(|e| FatalError::new("malformed_yaml", e.to_string()))?;
    let json_value: Value = serde_json::to_value(&yaml_value)
        .map_err(|e| FatalError::new("malformed_yaml", e.to_string()))?;
    let obj = json_value
        .as_object()
        .ok_or_else(|| FatalError::new("invalid_local_schema", ""))?;
    let clusters_value = obj
        .get("clusters")
        .ok_or_else(|| FatalError::new("invalid_local_schema", ""))?;
    let items = clusters_value
        .as_array()
        .ok_or_else(|| FatalError::new("invalid_local_schema", ""))?;
    if items.is_empty() {
        return Err(FatalError::new("invalid_local_schema", ""));
    }
    let mut clusters = Vec::with_capacity(items.len());
    for item in items {
        let cluster: ClusterInput = serde_json::from_value(item.clone())
            .map_err(|e| FatalError::new("invalid_local_schema", e.to_string()))?;
        clusters.push(cluster);
    }
    Ok(clusters)
}

fn load_settings_doc(path: &Path) -> Result<Vec<SettingInput>, FatalError> {
    let text = std::fs::read_to_string(path)
        .map_err(|_| FatalError::new("missing_required_input", path.display().to_string()))?;
    let toml_value: toml::Value =
        toml::from_str(&text).map_err(|e| FatalError::new("malformed_toml", e.to_string()))?;
    let json_value: Value = serde_json::to_value(&toml_value)
        .map_err(|e| FatalError::new("malformed_toml", e.to_string()))?;
    let items = json_value
        .get("settings")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let mut settings = Vec::with_capacity(items.len());
    for item in items {
        let s: SettingInput = serde_json::from_value(item)
            .map_err(|e| FatalError::new("malformed_toml", e.to_string()))?;
        settings.push(s);
    }
    Ok(settings)
}

fn load_extension_catalog(path: &Path) -> Result<ExtensionCatalogDoc, FatalError> {
    let text = std::fs::read_to_string(path)
        .map_err(|_| FatalError::new("missing_required_input", path.display().to_string()))?;
    serde_json::from_str(&text).map_err(|e| FatalError::new("malformed_extension_catalog", e.to_string()))
}

fn load_setting_catalog(path: &Path) -> Result<SettingCatalogDoc, FatalError> {
    let text = std::fs::read_to_string(path)
        .map_err(|_| FatalError::new("missing_required_input", path.display().to_string()))?;
    serde_json::from_str(&text).map_err(|e| FatalError::new("malformed_setting_catalog", e.to_string()))
}

fn parse_list<T: DeserializeOwned>(doc: &Value, key: &str) -> Vec<T> {
    doc.get(key)
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|item| serde_json::from_value::<T>(item.clone()).ok())
                .collect()
        })
        .unwrap_or_default()
}

// ---------------------------------------------------------------------------
// Working data model for a single cluster
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
struct RoleRec {
    role_id: String,
    role_name: String,
    login: bool,
    inherit: bool,
    createdb: bool,
    createrole: bool,
    replication: bool,
    bypassrls: bool,
    connection_limit: i64,
    source: String,
}

impl RoleRec {
    fn key_tuple(&self) -> (bool, bool, bool, bool, bool, bool, i64) {
        (
            self.login,
            self.inherit,
            self.createdb,
            self.createrole,
            self.replication,
            self.bypassrls,
            self.connection_limit,
        )
    }

    fn get_attr(&self, attr: &str) -> bool {
        match attr {
            "login" => self.login,
            "inherit" => self.inherit,
            "createdb" => self.createdb,
            "createrole" => self.createrole,
            "replication" => self.replication,
            "bypassrls" => self.bypassrls,
            _ => false,
        }
    }

    fn set_attr(&mut self, attr: &str, val: bool) {
        match attr {
            "login" => self.login = val,
            "inherit" => self.inherit = val,
            "createdb" => self.createdb = val,
            "createrole" => self.createrole = val,
            "replication" => self.replication = val,
            "bypassrls" => self.bypassrls = val,
            _ => {}
        }
    }
}

impl From<&RoleInput> for RoleRec {
    fn from(r: &RoleInput) -> Self {
        RoleRec {
            role_id: r.role_id.clone(),
            role_name: r.role_name.clone(),
            login: r.login,
            inherit: r.inherit,
            createdb: r.createdb,
            createrole: r.createrole,
            replication: r.replication,
            bypassrls: r.bypassrls,
            connection_limit: r.connection_limit,
            source: "local".to_string(),
        }
    }
}

#[derive(Clone, Debug)]
struct MembershipRec {
    membership_id: String,
    member_role_id: String,
    granted_role_id: String,
    source: String,
}

#[derive(Clone, Debug)]
struct DbRec {
    database_id: String,
    database_name: String,
    owner_role_id: String,
    template: String,
    encoding: String,
    connection_limit: i64,
    environment_allowlist: Vec<String>,
    source: String,
}

impl From<&DatabaseInput> for DbRec {
    fn from(d: &DatabaseInput) -> Self {
        DbRec {
            database_id: d.database_id.clone(),
            database_name: d.database_name.clone(),
            owner_role_id: d.owner_role_id.clone(),
            template: d.template.clone(),
            encoding: d.encoding.clone(),
            connection_limit: d.connection_limit,
            environment_allowlist: d.environment_allowlist.clone(),
            source: "local".to_string(),
        }
    }
}

#[derive(Clone, Debug)]
struct ExtRec {
    extension_request_id: String,
    database_id: String,
    extension_id: String,
    version: String,
    selection_reason: String,
    dependency_depth: i64,
    topological_position: i64,
}

#[derive(Clone, Debug)]
struct PrivRec {
    grant_id: String,
    scope: String,
    database_id: String,
    schema_name_or_null: Option<String>,
    table_name_or_null: Option<String>,
    grantee_role_id: String,
    privileges: Vec<String>,
    grant_option: bool,
    source: String,
}

#[derive(Clone, Debug)]
struct HbaRec {
    hba_id: String,
    connection_type: String,
    database_selector: String,
    role_selector: String,
    ipv4_cidr_or_null: Option<String>,
    auth_method: String,
    priority: i64,
    source: String,
    mandatory: bool,
    hba_position: i64,
}

#[derive(Clone, Debug)]
struct WorkSetting {
    setting_id: String,
    scope: String,
    database_id_or_null: Option<String>,
    role_id_or_null: Option<String>,
    setting_name: String,
    value: Value,
    source: String,
    normalized_value: Value,
    activation_mode: String,
    transaction_compatible: bool,
    value_type: String,
}

#[derive(Clone, Debug)]
struct Op {
    operation_id: String,
    operation_kind: String,
    resource_id: String,
    database_id_or_null: Option<String>,
    depends_on_operation_ids: Vec<String>,
    topological_position: i64,
}

struct AcceptedCluster {
    cluster_id: String,
    environment: String,
    roles: Vec<RoleRec>,
    memberships: Vec<MembershipRec>,
    databases: Vec<DbRec>,
    extensions: Vec<ExtRec>,
    privileges: Vec<PrivRec>,
    hba_rows: Vec<HbaRec>,
    settings: Vec<WorkSetting>,
    operations: Vec<Op>,
    requires_reload: bool,
    requires_restart: bool,
    topo: Vec<String>,
    phase_count: i64,
}

struct Rejection {
    reason: String,
    row: RejectionRow,
}

fn reject(
    cluster_id: &str,
    stage: &str,
    reason: &str,
    resource_id: Option<&str>,
    details: Value,
) -> Rejection {
    Rejection {
        reason: reason.to_string(),
        row: RejectionRow {
            cluster_id: cluster_id.to_string(),
            stage: stage.to_string(),
            reason: reason.to_string(),
            resource_id_or_null: resource_id.map(|s| s.to_string()),
            details,
        },
    }
}

// Policy fragment sub-documents (typed views over the JSON fragments).

#[derive(serde::Deserialize, Default)]
struct RoleConstraint {
    role_id_or_star: String,
    #[serde(default)]
    forbidden_true_attributes: Vec<String>,
    #[serde(default)]
    forced_boolean_attributes: serde_json::Map<String, Value>,
    #[serde(default)]
    maximum_connection_limit_or_null: Option<i64>,
}

#[derive(serde::Deserialize, Default)]
struct DatabaseConstraint {
    database_id_or_star: String,
    #[serde(default)]
    forbidden_templates: Vec<String>,
    #[serde(default)]
    forced_encoding_or_null: Option<String>,
    #[serde(default)]
    maximum_connection_limit_or_null: Option<i64>,
    #[serde(default)]
    allowed_environments: Vec<String>,
}

#[derive(serde::Deserialize, Default)]
struct SettingPolicy {
    setting_name: String,
    scope_or_star: String,
    #[serde(default)]
    forced_value_or_null: Option<Value>,
    #[serde(default)]
    minimum_integer_or_null: Option<i64>,
    #[serde(default)]
    maximum_integer_or_null: Option<i64>,
    #[serde(default)]
    forbidden: bool,
    #[serde(default)]
    required: bool,
}

#[derive(serde::Deserialize, Default)]
struct PrivilegeRule {
    scope: String,
    #[serde(default)]
    allowed_privileges: Vec<String>,
    #[serde(default)]
    forbid_grant_option: bool,
    #[serde(default)]
    forbid_direct_login_role_grants: bool,
}

// ---------------------------------------------------------------------------
// Per-cluster planning
// ---------------------------------------------------------------------------

fn plan_cluster(
    cluster: &ClusterInput,
    settings_local: &[SettingInput],
    ext_catalog: &HashMap<String, ExtensionCatalogEntry>,
    setting_catalog: &HashMap<String, SettingCatalogEntry>,
    snap: &PolicySnapshot,
) -> Result<AcceptedCluster, RejectionRow> {
    plan_cluster_inner(cluster, settings_local, ext_catalog, setting_catalog, snap)
        .map_err(|r| r.row)
}

fn plan_cluster_inner(
    cluster: &ClusterInput,
    settings_local: &[SettingInput],
    ext_catalog: &HashMap<String, ExtensionCatalogEntry>,
    setting_catalog: &HashMap<String, SettingCatalogEntry>,
    snap: &PolicySnapshot,
) -> Result<AcceptedCluster, Rejection> {
    let cid = cluster.cluster_id.as_str();
    let env = cluster.environment.as_str();
    let identity = &snap.identity;
    let database_doc = &snap.database;
    let access = &snap.access;

    // --- roles merge ---
    let mut role_order: Vec<String> = Vec::new();
    let mut roles_by_id: HashMap<String, RoleRec> = HashMap::new();
    for r in &cluster.roles {
        role_order.push(r.role_id.clone());
        roles_by_id.insert(r.role_id.clone(), RoleRec::from(r));
    }
    let required_roles: Vec<RoleInput> = parse_list(identity, "required_roles");
    for req in &required_roles {
        let rid = req.role_id.clone();
        if let Some(local) = roles_by_id.get(&rid) {
            let req_rec = RoleRec::from(req);
            if local.key_tuple() != req_rec.key_tuple() {
                return Err(reject(cid, "merge", "resource_identity_conflict", Some(&rid), Value::Object(Default::default())));
            }
            roles_by_id.get_mut(&rid).unwrap().source = "merged".to_string();
        } else {
            let mut rec = RoleRec::from(req);
            rec.source = "policy_required".to_string();
            role_order.push(rid.clone());
            roles_by_id.insert(rid, rec);
        }
    }

    // role constraints
    let constraints: Vec<RoleConstraint> = parse_list(identity, "role_constraints");
    for role_id in role_order.clone() {
        let mut applicable: Vec<&RoleConstraint> = constraints
            .iter()
            .filter(|c| c.role_id_or_star == "*" || c.role_id_or_star == role_id)
            .collect();
        applicable.sort_by_key(|c| if c.role_id_or_star == role_id { 0 } else { 1 });
        for c in applicable {
            for attr in &c.forbidden_true_attributes {
                let role = roles_by_id.get(&role_id).unwrap();
                if role.get_attr(attr) {
                    return Err(reject(
                        cid,
                        "roles",
                        "forbidden_role_capability",
                        Some(&role_id),
                        serde_json::json!({"attribute": attr}),
                    ));
                }
            }
            for (attr, val) in &c.forced_boolean_attributes {
                let val_bool = val.as_bool().unwrap_or(false);
                let role = roles_by_id.get(&role_id).unwrap();
                if role.get_attr(attr) != val_bool {
                    if c.forbidden_true_attributes.contains(attr) && val_bool {
                        return Err(reject(
                            cid,
                            "roles",
                            "forbidden_role_capability",
                            Some(&role_id),
                            serde_json::json!({"attribute": attr}),
                        ));
                    }
                    roles_by_id.get_mut(&role_id).unwrap().set_attr(attr, val_bool);
                }
            }
            if let Some(max_lim) = c.maximum_connection_limit_or_null {
                let role = roles_by_id.get(&role_id).unwrap();
                if role.connection_limit != -1 && role.connection_limit > max_lim {
                    return Err(reject(
                        cid,
                        "roles",
                        "role_constraint_violation",
                        Some(&role_id),
                        serde_json::json!({"limit": max_lim}),
                    ));
                }
            }
        }
    }

    // memberships
    let mut memberships: Vec<MembershipRec> = Vec::new();
    let mut seen_edges: HashSet<(String, String)> = HashSet::new();
    for m in &cluster.role_memberships {
        memberships.push(MembershipRec {
            membership_id: m.membership_id.clone(),
            member_role_id: m.member_role_id.clone(),
            granted_role_id: m.granted_role_id.clone(),
            source: "local".to_string(),
        });
        seen_edges.insert((m.member_role_id.clone(), m.granted_role_id.clone()));
    }
    let required_memberships: Vec<MembershipInput> = parse_list(identity, "required_memberships");
    for req in &required_memberships {
        let edge = (req.member_role_id.clone(), req.granted_role_id.clone());
        if !seen_edges.contains(&edge) {
            memberships.push(MembershipRec {
                membership_id: req.membership_id.clone(),
                member_role_id: req.member_role_id.clone(),
                granted_role_id: req.granted_role_id.clone(),
                source: "policy_required".to_string(),
            });
            seen_edges.insert(edge);
        }
    }
    let forbidden_memberships: Vec<Value> = identity
        .get("forbidden_memberships")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    for forb in &forbidden_memberships {
        let member = forb.get("member_role_id").and_then(|v| v.as_str()).unwrap_or("");
        let granted = forb.get("granted_role_id").and_then(|v| v.as_str()).unwrap_or("");
        if seen_edges.contains(&(member.to_string(), granted.to_string())) {
            return Err(reject(cid, "roles", "forbidden_membership", Some(member), forb.clone()));
        }
    }

    if let Some(cycle) = detect_membership_cycle(
        &memberships
            .iter()
            .map(|m| (m.member_role_id.clone(), m.granted_role_id.clone()))
            .collect::<Vec<_>>(),
    ) {
        return Err(reject(
            cid,
            "roles",
            "role_membership_cycle",
            Some(&cycle[0]),
            serde_json::json!({"cycle_members": cycle}),
        ));
    }

    // --- databases merge ---
    let mut db_order: Vec<String> = Vec::new();
    let mut dbs_by_id: HashMap<String, DbRec> = HashMap::new();
    for d in &cluster.databases {
        db_order.push(d.database_id.clone());
        dbs_by_id.insert(d.database_id.clone(), DbRec::from(d));
    }
    let required_databases: Vec<DatabaseInput> = parse_list(database_doc, "required_databases");
    for req in &required_databases {
        let did = req.database_id.clone();
        if let Some(local) = dbs_by_id.get(&did) {
            if local.database_name != req.database_name
                || local.owner_role_id != req.owner_role_id
                || local.template != req.template
                || local.encoding != req.encoding
            {
                return Err(reject(cid, "merge", "resource_identity_conflict", Some(&did), Value::Object(Default::default())));
            }
            dbs_by_id.get_mut(&did).unwrap().source = "merged".to_string();
        } else {
            let mut rec = DbRec::from(req);
            rec.source = "policy_required".to_string();
            db_order.push(did.clone());
            dbs_by_id.insert(did, rec);
        }
    }

    let database_constraints: Vec<DatabaseConstraint> = parse_list(database_doc, "database_constraints");
    for db_id in db_order.clone() {
        {
            let owner_ok = roles_by_id.contains_key(&dbs_by_id.get(&db_id).unwrap().owner_role_id);
            if !owner_ok {
                return Err(reject(cid, "databases", "database_owner_unavailable", Some(&db_id), Value::Object(Default::default())));
            }
        }
        let mut applicable: Vec<&DatabaseConstraint> = database_constraints
            .iter()
            .filter(|c| c.database_id_or_star == "*" || c.database_id_or_star == db_id)
            .collect();
        applicable.sort_by_key(|c| if c.database_id_or_star == db_id { 0 } else { 1 });
        for c in applicable {
            let allowed = if c.allowed_environments.is_empty() {
                vec![env.to_string()]
            } else {
                c.allowed_environments.clone()
            };
            if !allowed.iter().any(|a| a == env) {
                return Err(reject(cid, "databases", "database_environment_forbidden", Some(&db_id), Value::Object(Default::default())));
            }
            let template = dbs_by_id.get(&db_id).unwrap().template.clone();
            if c.forbidden_templates.iter().any(|t| t == &template) {
                return Err(reject(
                    cid,
                    "databases",
                    "database_constraint_violation",
                    Some(&db_id),
                    serde_json::json!({"template": template}),
                ));
            }
            if let Some(forced) = &c.forced_encoding_or_null {
                let db = dbs_by_id.get_mut(&db_id).unwrap();
                if &db.encoding != forced {
                    db.encoding = forced.clone();
                }
            }
            if let Some(max_lim) = c.maximum_connection_limit_or_null {
                let db = dbs_by_id.get(&db_id).unwrap();
                if db.connection_limit != -1 && db.connection_limit > max_lim {
                    return Err(reject(
                        cid,
                        "databases",
                        "database_constraint_violation",
                        Some(&db_id),
                        serde_json::json!({"limit": max_lim}),
                    ));
                }
            }
        }
        let db = dbs_by_id.get(&db_id).unwrap();
        if !db.environment_allowlist.iter().any(|a| a == env) {
            return Err(reject(cid, "databases", "database_environment_forbidden", Some(&db_id), Value::Object(Default::default())));
        }
    }

    // --- extensions ---
    let mut ext_requests: Vec<ExtRequest> = Vec::new();
    for e in &cluster.extensions {
        ext_requests.push(ExtRequest {
            extension_request_id: e.extension_request_id.clone(),
            database_id: e.database_id.clone(),
            extension_id: e.extension_id.clone(),
            version: e.version.clone(),
            selection_reason: "local".to_string(),
        });
    }
    let required_extensions: Vec<ExtensionInput> = parse_list(database_doc, "required_extensions");
    for req in &required_extensions {
        ext_requests.push(ExtRequest {
            extension_request_id: req.extension_request_id.clone(),
            database_id: req.database_id.clone(),
            extension_id: req.extension_id.clone(),
            version: req.version.clone(),
            selection_reason: "policy_required".to_string(),
        });
    }

    let extensions = match extension_closure(&ext_requests, ext_catalog) {
        Ok(v) => v,
        Err(err) => return Err(reject(cid, "extensions", &err, None, Value::Object(Default::default()))),
    };

    // --- settings ---
    let mut effective_settings: Vec<WorkSetting> = Vec::new();
    let mut setting_keys: HashSet<(String, Option<String>, Option<String>, String)> = HashSet::new();
    for s in settings_local.iter().filter(|s| s.cluster_id == cid) {
        effective_settings.push(WorkSetting {
            setting_id: s.setting_id.clone(),
            scope: s.scope.clone(),
            database_id_or_null: s.database_id_or_null.clone(),
            role_id_or_null: s.role_id_or_null.clone(),
            setting_name: s.setting_name.clone(),
            value: s.value.clone(),
            source: "local".to_string(),
            normalized_value: Value::Null,
            activation_mode: String::new(),
            transaction_compatible: false,
            value_type: String::new(),
        });
        setting_keys.insert((
            s.scope.clone(),
            s.database_id_or_null.clone(),
            s.role_id_or_null.clone(),
            s.setting_name.clone(),
        ));
    }
    let setting_policies: Vec<SettingPolicy> = parse_list(database_doc, "setting_policies");
    for sp in &setting_policies {
        if !sp.required || sp.forbidden {
            continue;
        }
        if sp.scope_or_star == "system" {
            if let Some(forced) = &sp.forced_value_or_null {
                let key = ("system".to_string(), None, None, sp.setting_name.clone());
                if !setting_keys.contains(&key) {
                    effective_settings.push(WorkSetting {
                        setting_id: format!("policy_{}", sp.setting_name),
                        scope: "system".to_string(),
                        database_id_or_null: None,
                        role_id_or_null: None,
                        setting_name: sp.setting_name.clone(),
                        value: forced.clone(),
                        source: "policy_required".to_string(),
                        normalized_value: Value::Null,
                        activation_mode: String::new(),
                        transaction_compatible: false,
                        value_type: String::new(),
                    });
                    setting_keys.insert(key);
                }
            }
        }
    }

    let mut requires_restart = false;
    let mut requires_reload = false;
    let mut resolved_settings: Vec<WorkSetting> = Vec::new();
    for mut s in effective_settings {
        let cat = match setting_catalog.get(&s.setting_name) {
            Some(c) => c,
            None => return Err(reject(cid, "settings", "invalid_setting_type", Some(&s.setting_id), Value::Object(Default::default()))),
        };
        if !cat.allowed_scopes.iter().any(|sc| sc == &s.scope) {
            return Err(reject(cid, "settings", "invalid_setting_scope", Some(&s.setting_id), Value::Object(Default::default())));
        }
        if s.scope == "database" {
            let db_ok = s.database_id_or_null.as_ref().map(|d| dbs_by_id.contains_key(d)).unwrap_or(false);
            if !db_ok {
                return Err(reject(cid, "settings", "invalid_setting_scope", Some(&s.setting_id), Value::Object(Default::default())));
            }
        }
        if s.scope == "role" || s.scope == "role_database" {
            let role_ok = s.role_id_or_null.as_ref().map(|r| roles_by_id.contains_key(r)).unwrap_or(false);
            if !role_ok {
                return Err(reject(cid, "settings", "invalid_setting_scope", Some(&s.setting_id), Value::Object(Default::default())));
            }
        }
        if s.scope == "role_database" {
            let db_ok = s.database_id_or_null.as_ref().map(|d| dbs_by_id.contains_key(d)).unwrap_or(false);
            if !db_ok {
                return Err(reject(cid, "settings", "invalid_setting_scope", Some(&s.setting_id), Value::Object(Default::default())));
            }
        }

        let mut value = s.value.clone();
        for sp in &setting_policies {
            let scope_matches = sp.scope_or_star == "*" || sp.scope_or_star == s.scope;
            if !scope_matches || sp.setting_name != s.setting_name {
                continue;
            }
            if sp.forbidden {
                return Err(reject(cid, "settings", "setting_outside_policy_bounds", Some(&s.setting_id), Value::Object(Default::default())));
            }
            if let Some(forced) = &sp.forced_value_or_null {
                value = forced.clone();
            }
            if cat.value_type == "integer" {
                let iv = value_as_i64(&value);
                if let Some(mn) = sp.minimum_integer_or_null {
                    if iv < mn {
                        return Err(reject(cid, "settings", "setting_outside_policy_bounds", Some(&s.setting_id), Value::Object(Default::default())));
                    }
                }
                if let Some(mx) = sp.maximum_integer_or_null {
                    if iv > mx {
                        return Err(reject(cid, "settings", "setting_outside_policy_bounds", Some(&s.setting_id), Value::Object(Default::default())));
                    }
                }
            }
        }

        let (normalized, value_type_str) = match cat.value_type.as_str() {
            "integer" => {
                let iv = value_as_i64(&value);
                if let Some(mn) = cat.minimum_integer_or_null {
                    if iv < mn {
                        return Err(reject(cid, "settings", "setting_outside_policy_bounds", Some(&s.setting_id), Value::Object(Default::default())));
                    }
                }
                if let Some(mx) = cat.maximum_integer_or_null {
                    if iv > mx {
                        return Err(reject(cid, "settings", "setting_outside_policy_bounds", Some(&s.setting_id), Value::Object(Default::default())));
                    }
                }
                (Value::from(iv), "integer".to_string())
            }
            "boolean" => (Value::Bool(value_truthy(&value)), "boolean".to_string()),
            "string" => (Value::String(value_as_string(&value)), "string".to_string()),
            "string_array" => {
                let items: Vec<String> = value
                    .as_array()
                    .map(|a| a.iter().map(value_as_string).collect())
                    .unwrap_or_default();
                let unique: BTreeSet<String> = items.into_iter().collect();
                let sorted: Vec<Value> = unique.into_iter().map(Value::String).collect();
                (Value::Array(sorted), "string_array".to_string())
            }
            _ => return Err(reject(cid, "settings", "invalid_setting_type", Some(&s.setting_id), Value::Object(Default::default()))),
        };

        if cat.activation_mode == "restart" {
            requires_restart = true;
        }
        if cat.activation_mode == "reload" {
            requires_reload = true;
        }

        s.normalized_value = normalized;
        s.activation_mode = cat.activation_mode.clone();
        s.transaction_compatible = cat.transaction_compatible;
        s.value_type = value_type_str;
        resolved_settings.push(s);
    }

    // extension setting coupling
    let mut settings_by_scope: HashMap<(String, Option<String>, Option<String>, String), &WorkSetting> = HashMap::new();
    for s in &resolved_settings {
        settings_by_scope.insert(
            (s.scope.clone(), s.database_id_or_null.clone(), s.role_id_or_null.clone(), s.setting_name.clone()),
            s,
        );
    }
    for ext in &extensions {
        let cat_e = &ext_catalog[&ext.extension_id];
        for req in &cat_e.required_settings {
            let key = (req.scope.clone(), None, None, req.setting_name.clone());
            let eff = match settings_by_scope.get(&key) {
                Some(v) => *v,
                None => return Err(reject(cid, "extensions", "required_extension_setting_unsatisfied", Some(&ext.extension_id), Value::Object(Default::default()))),
            };
            if let Some(needle) = &req.required_value_contains_or_null {
                if !value_contains(&eff.normalized_value, needle) {
                    return Err(reject(cid, "extensions", "required_extension_setting_unsatisfied", Some(&ext.extension_id), Value::Object(Default::default())));
                }
            }
            if let Some(expected) = &req.required_value_equals_or_null {
                if &eff.normalized_value != expected {
                    return Err(reject(cid, "extensions", "required_extension_setting_unsatisfied", Some(&ext.extension_id), Value::Object(Default::default())));
                }
            }
        }
    }

    // --- privileges ---
    #[derive(Clone)]
    struct PrivWork {
        grant_id: String,
        scope: String,
        database_id: String,
        schema_name_or_null: Option<String>,
        table_name_or_null: Option<String>,
        grantee_role_id: String,
        privileges: Vec<String>,
        grant_option: bool,
        source: String,
    }
    let mut priv_inputs: Vec<PrivWork> = Vec::new();
    for p in &cluster.privileges {
        priv_inputs.push(PrivWork {
            grant_id: p.grant_id.clone(),
            scope: p.scope.clone(),
            database_id: p.database_id.clone(),
            schema_name_or_null: p.schema_name_or_null.clone(),
            table_name_or_null: p.table_name_or_null.clone(),
            grantee_role_id: p.grantee_role_id.clone(),
            privileges: p.privileges.clone(),
            grant_option: p.grant_option,
            source: "local".to_string(),
        });
    }
    let required_privileges: Vec<PrivilegeInput> = parse_list(access, "required_privileges");
    for p in &required_privileges {
        priv_inputs.push(PrivWork {
            grant_id: p.grant_id.clone(),
            scope: p.scope.clone(),
            database_id: p.database_id.clone(),
            schema_name_or_null: p.schema_name_or_null.clone(),
            table_name_or_null: p.table_name_or_null.clone(),
            grantee_role_id: p.grantee_role_id.clone(),
            privileges: p.privileges.clone(),
            grant_option: p.grant_option,
            source: "policy_required".to_string(),
        });
    }

    let mut priv_order: Vec<(String, String, Option<String>, Option<String>, String, bool)> = Vec::new();
    let mut priv_index: HashMap<(String, String, Option<String>, Option<String>, String, bool), PrivWork> = HashMap::new();
    for p in priv_inputs {
        let sem = (
            p.scope.clone(),
            p.database_id.clone(),
            p.schema_name_or_null.clone(),
            p.table_name_or_null.clone(),
            p.grantee_role_id.clone(),
            p.grant_option,
        );
        if let Some(existing) = priv_index.get_mut(&sem) {
            let mut combined: HashSet<String> = existing.privileges.iter().cloned().collect();
            combined.extend(p.privileges.iter().cloned());
            existing.privileges = sort_privileges(combined.into_iter().collect());
            if existing.source != p.source {
                existing.source = "merged".to_string();
            }
        } else {
            let mut entry = p.clone();
            entry.privileges = sort_privileges(entry.privileges.clone());
            priv_order.push(sem.clone());
            priv_index.insert(sem, entry);
        }
    }
    let merged_privs: Vec<PrivWork> = priv_order.iter().map(|k| priv_index[k].clone()).collect();

    let privilege_rules: Vec<PrivilegeRule> = parse_list(access, "privilege_rules");
    for p in &merged_privs {
        if !dbs_by_id.contains_key(&p.database_id) {
            return Err(reject(cid, "privileges", "privilege_target_unavailable", Some(&p.grant_id), Value::Object(Default::default())));
        }
        if !roles_by_id.contains_key(&p.grantee_role_id) {
            return Err(reject(cid, "privileges", "privilege_target_unavailable", Some(&p.grant_id), Value::Object(Default::default())));
        }
        for rule in &privilege_rules {
            if rule.scope != p.scope {
                continue;
            }
            for priv_name in &p.privileges {
                if !rule.allowed_privileges.iter().any(|a| a == priv_name) {
                    return Err(reject(
                        cid,
                        "privileges",
                        "forbidden_privilege",
                        Some(&p.grant_id),
                        serde_json::json!({"privilege": priv_name}),
                    ));
                }
            }
            if p.grant_option && rule.forbid_grant_option {
                return Err(reject(cid, "privileges", "forbidden_privilege", Some(&p.grant_id), Value::Object(Default::default())));
            }
            let grantee = roles_by_id.get(&p.grantee_role_id).unwrap();
            if grantee.login && rule.forbid_direct_login_role_grants && p.source == "local" {
                return Err(reject(cid, "privileges", "forbidden_privilege", Some(&p.grant_id), Value::Object(Default::default())));
            }
        }
    }

    // --- HBA ---
    let mut hba_recs: Vec<HbaRec> = Vec::new();
    for h in &cluster.hba_rules {
        hba_recs.push(HbaRec {
            hba_id: h.hba_id.clone(),
            connection_type: h.connection_type.clone(),
            database_selector: h.database_selector.clone(),
            role_selector: h.role_selector.clone(),
            ipv4_cidr_or_null: h.ipv4_cidr_or_null.as_deref().map(normalize_ipv4_cidr).transpose().map_err(|e: String| reject(cid, "hba", "invalid_hba_cidr", Some(&h.hba_id), serde_json::json!({"error": e})))?,
            auth_method: h.auth_method.clone(),
            priority: h.priority,
            source: "local".to_string(),
            mandatory: false,
            hba_position: 0,
        });
    }
    let mandatory_hba_rules: Vec<HbaInput> = parse_list(access, "mandatory_hba_rules");
    for h in &mandatory_hba_rules {
        hba_recs.push(HbaRec {
            hba_id: h.hba_id.clone(),
            connection_type: h.connection_type.clone(),
            database_selector: h.database_selector.clone(),
            role_selector: h.role_selector.clone(),
            ipv4_cidr_or_null: h.ipv4_cidr_or_null.as_deref().map(normalize_ipv4_cidr).transpose().map_err(|e: String| reject(cid, "hba", "invalid_hba_cidr", Some(&h.hba_id), serde_json::json!({"error": e})))?,
            auth_method: h.auth_method.clone(),
            priority: h.priority,
            source: "policy".to_string(),
            mandatory: true,
            hba_position: 0,
        });
    }

    for h in &hba_recs {
        if h.database_selector != "all" && !dbs_by_id.contains_key(&h.database_selector) {
            return Err(reject(cid, "hba", "hba_reference_unavailable", Some(&h.hba_id), Value::Object(Default::default())));
        }
        if h.role_selector != "all" && !roles_by_id.contains_key(&h.role_selector) {
            return Err(reject(cid, "hba", "hba_reference_unavailable", Some(&h.hba_id), Value::Object(Default::default())));
        }
    }

    if let Some((shadowed, shadowing)) = find_shadow(&hba_recs) {
        return Err(reject(
            cid,
            "hba",
            "hba_rule_fully_shadowed",
            Some(&shadowed),
            serde_json::json!({"shadowed_hba_id": shadowed, "shadowing_hba_id": shadowing}),
        ));
    }

    let mut ordered_hba = order_hba_rows(hba_recs);
    for (i, h) in ordered_hba.iter_mut().enumerate() {
        h.hba_position = i as i64;
    }

    // --- operations DAG ---
    let mut ops: Vec<Op> = Vec::new();
    let mut op_index: HashMap<String, usize> = HashMap::new();

    let mut role_ops: HashMap<String, String> = HashMap::new();
    let mut sorted_role_ids: Vec<String> = roles_by_id.keys().cloned().collect();
    sorted_role_ids.sort();
    for rid in &sorted_role_ids {
        let oid = add_op(&mut ops, &mut op_index, "create_role", cid, rid, None, Vec::new());
        role_ops.insert(rid.clone(), oid);
    }

    for m in &memberships {
        let deps = vec![
            role_ops[&m.member_role_id].clone(),
            role_ops[&m.granted_role_id].clone(),
        ];
        add_op(&mut ops, &mut op_index, "grant_role_membership", cid, &m.membership_id, None, deps);
    }

    let mut reload_ops: Vec<String> = Vec::new();
    for s in resolved_settings.iter().filter(|s| s.scope == "system") {
        let oid = add_op(&mut ops, &mut op_index, "alter_system_setting", cid, &s.setting_id, None, Vec::new());
        if s.activation_mode == "reload" {
            reload_ops.push(oid);
        }
    }

    let mut db_ops: HashMap<String, String> = HashMap::new();
    let mut connect_ops: HashMap<String, String> = HashMap::new();
    let mut sorted_db_ids: Vec<String> = dbs_by_id.keys().cloned().collect();
    sorted_db_ids.sort();
    for did in &sorted_db_ids {
        let owner = dbs_by_id[did].owner_role_id.clone();
        let oid = add_op(&mut ops, &mut op_index, "create_database", cid, did, None, vec![role_ops[&owner].clone()]);
        db_ops.insert(did.clone(), oid.clone());
        let coid = add_op(&mut ops, &mut op_index, "connect_database", cid, did, Some(did), vec![oid]);
        connect_ops.insert(did.clone(), coid);
    }

    let mut ext_ops: HashMap<(String, String), String> = HashMap::new();
    for ext in &extensions {
        let eid = ext.extension_id.clone();
        let resource_id = format!("{}:{}", ext.database_id, eid);
        let oid = add_op(
            &mut ops,
            &mut op_index,
            "extension",
            cid,
            &resource_id,
            Some(&ext.database_id),
            vec![connect_ops[&ext.database_id].clone()],
        );
        ext_ops.insert((ext.database_id.clone(), eid.clone()), oid.clone());
        for dep in &ext_catalog[&eid].requires {
            if let Some(dep_oid) = ext_ops.get(&(ext.database_id.clone(), dep.clone())) {
                let idx = op_index[&oid];
                let mut set: BTreeSet<String> = ops[idx].depends_on_operation_ids.iter().cloned().collect();
                set.insert(dep_oid.clone());
                ops[idx].depends_on_operation_ids = set.into_iter().collect();
            }
        }
    }

    for p in &merged_privs {
        let deps = vec![
            role_ops[&p.grantee_role_id].clone(),
            connect_ops[&p.database_id].clone(),
        ];
        let kind = match p.scope.as_str() {
            "database" => "grant_database_privilege",
            "schema" => "grant_schema_privilege",
            "table" => "grant_table_privilege",
            _ => "grant_database_privilege",
        };
        add_op(&mut ops, &mut op_index, kind, cid, &p.grant_id, Some(&p.database_id), deps);
    }

    for s in &resolved_settings {
        if s.scope == "system" {
            continue;
        }
        let mut deps: Vec<String> = Vec::new();
        if s.scope == "database" || s.scope == "role_database" {
            deps.push(connect_ops[s.database_id_or_null.as_ref().unwrap()].clone());
        }
        if s.scope == "role" || s.scope == "role_database" {
            deps.push(role_ops[s.role_id_or_null.as_ref().unwrap()].clone());
        }
        let kind = match s.scope.as_str() {
            "database" => "alter_database_setting",
            "role" => "alter_role_setting",
            "role_database" => "alter_role_database_setting",
            _ => "alter_database_setting",
        };
        let oid = add_op(&mut ops, &mut op_index, kind, cid, &s.setting_id, s.database_id_or_null.as_deref(), deps);
        if s.activation_mode == "reload" {
            reload_ops.push(oid);
        }
    }

    let mut hba_op_ids: Vec<String> = Vec::new();
    for h in &ordered_hba {
        let mut deps: Vec<String> = Vec::new();
        if h.database_selector != "all" {
            deps.push(connect_ops[&h.database_selector].clone());
        }
        if h.role_selector != "all" {
            deps.push(role_ops[&h.role_selector].clone());
        }
        hba_op_ids.push(add_op(&mut ops, &mut op_index, "emit_hba_rule", cid, &h.hba_id, None, deps));
    }

    if !reload_ops.is_empty() || !hba_op_ids.is_empty() {
        let mut deps = reload_ops.clone();
        deps.extend(hba_op_ids.clone());
        add_op(&mut ops, &mut op_index, "reload_configuration", cid, cid, None, deps);
        requires_reload = true;
    }

    let topo = match topo_sort_ops(&ops) {
        Ok(order) => order,
        Err(remaining) => {
            return Err(reject(
                cid,
                "graph",
                "operation_dependency_cycle",
                Some(&remaining[0]),
                serde_json::json!({"operations": remaining}),
            ));
        }
    };
    for (i, oid) in topo.iter().enumerate() {
        let idx = op_index[oid];
        ops[idx].topological_position = i as i64;
    }

    let roles: Vec<RoleRec> = sorted_role_ids
        .iter()
        .map(|rid| roles_by_id[rid].clone())
        .collect();
    let databases: Vec<DbRec> = sorted_db_ids
        .iter()
        .map(|did| dbs_by_id[did].clone())
        .collect();

    Ok(AcceptedCluster {
        cluster_id: cid.to_string(),
        environment: env.to_string(),
        roles,
        memberships,
        databases,
        extensions,
        privileges: merged_privs
            .into_iter()
            .map(|p| PrivRec {
                grant_id: p.grant_id,
                scope: p.scope,
                database_id: p.database_id,
                schema_name_or_null: p.schema_name_or_null,
                table_name_or_null: p.table_name_or_null,
                grantee_role_id: p.grantee_role_id,
                privileges: p.privileges,
                grant_option: p.grant_option,
                source: p.source,
            })
            .collect(),
        hba_rows: ordered_hba,
        settings: resolved_settings,
        operations: ops,
        requires_reload,
        requires_restart,
        topo,
        phase_count: 0,
    })
}

// ---------------------------------------------------------------------------
// Value helpers
// ---------------------------------------------------------------------------

fn value_as_i64(v: &Value) -> i64 {
    if let Some(i) = v.as_i64() {
        i
    } else if let Some(f) = v.as_f64() {
        f as i64
    } else if let Some(s) = v.as_str() {
        s.parse().unwrap_or(0)
    } else if let Some(b) = v.as_bool() {
        if b {
            1
        } else {
            0
        }
    } else {
        0
    }
}

fn value_truthy(v: &Value) -> bool {
    match v {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64().map(|f| f != 0.0).unwrap_or(false),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

fn value_as_string(v: &Value) -> String {
    match v {
        Value::String(s) => s.clone(),
        Value::Bool(b) => b.to_string(),
        Value::Number(n) => n.to_string(),
        Value::Null => String::new(),
        other => other.to_string(),
    }
}

fn value_contains(haystack: &Value, needle: &str) -> bool {
    match haystack {
        Value::Array(items) => items.iter().any(|item| value_as_string(item) == needle),
        Value::String(s) => s.contains(needle),
        _ => false,
    }
}

// ---------------------------------------------------------------------------
// Membership cycle detection (mirrors reference/planner.py::_detect_membership_cycle)
// ---------------------------------------------------------------------------

fn detect_membership_cycle(edges: &[(String, String)]) -> Option<Vec<String>> {
    let mut graph: HashMap<String, Vec<String>> = HashMap::new();
    let mut nodes: BTreeSet<String> = BTreeSet::new();
    for (m, g) in edges {
        if m == g {
            return Some(vec![m.clone()]);
        }
        nodes.insert(m.clone());
        nodes.insert(g.clone());
        graph.entry(m.clone()).or_default().push(g.clone());
    }
    let mut state: HashMap<String, u8> = nodes.iter().map(|n| (n.clone(), 0u8)).collect();
    let mut cycle_nodes: Vec<String> = Vec::new();

    fn dfs(
        n: &str,
        graph: &HashMap<String, Vec<String>>,
        state: &mut HashMap<String, u8>,
        stack: &mut Vec<String>,
        cycle_nodes: &mut Vec<String>,
    ) -> bool {
        state.insert(n.to_string(), 1);
        stack.push(n.to_string());
        if let Some(nexts) = graph.get(n) {
            for nxt in nexts {
                if state.get(nxt.as_str()).copied().unwrap_or(0) == 1 {
                    let idx = stack.iter().position(|x| x == nxt).unwrap();
                    let mut found: Vec<String> = stack[idx..].to_vec();
                    found.sort();
                    cycle_nodes.extend(found);
                    return true;
                }
                if state.get(nxt.as_str()).copied().unwrap_or(0) == 0
                    && dfs(nxt, graph, state, stack, cycle_nodes)
                {
                    return true;
                }
            }
        }
        stack.pop();
        state.insert(n.to_string(), 2);
        false
    }

    for n in &nodes {
        if state[n] == 0 && dfs(n, &graph, &mut state, &mut Vec::new(), &mut cycle_nodes) {
            let set: BTreeSet<String> = cycle_nodes.into_iter().collect();
            return Some(set.into_iter().collect());
        }
    }
    None
}

// ---------------------------------------------------------------------------
// Extension dependency closure (mirrors reference/planner.py::_extension_closure)
// ---------------------------------------------------------------------------

struct ExtRequest {
    extension_request_id: String,
    database_id: String,
    extension_id: String,
    version: String,
    selection_reason: String,
}

fn extension_closure(
    requests: &[ExtRequest],
    catalog: &HashMap<String, ExtensionCatalogEntry>,
) -> Result<Vec<ExtRec>, String> {
    #[derive(Clone)]
    struct Rec {
        extension_request_id: String,
        database_id: String,
        extension_id: String,
        version: String,
        selection_reason: String,
    }

    let mut by_key: HashMap<(String, String), Rec> = HashMap::new();
    for r in requests {
        let key = (r.database_id.clone(), r.extension_id.clone());
        if let Some(existing) = by_key.get(&key) {
            if existing.version != r.version {
                return Err("extension_version_conflict".to_string());
            }
        }
        by_key.insert(
            key,
            Rec {
                extension_request_id: r.extension_request_id.clone(),
                database_id: r.database_id.clone(),
                extension_id: r.extension_id.clone(),
                version: r.version.clone(),
                selection_reason: r.selection_reason.clone(),
            },
        );
    }

    let mut changed = true;
    while changed {
        changed = false;
        let keys: Vec<(String, String)> = by_key.keys().cloned().collect();
        for (db_id, ext_id) in keys {
            let cat = match catalog.get(&ext_id) {
                Some(c) => c,
                None => return Err("unknown_extension".to_string()),
            };
            let requires = cat.requires.clone();
            for dep in requires {
                let dkey = (db_id.clone(), dep.clone());
                if !by_key.contains_key(&dkey) {
                    let dep_cat = match catalog.get(&dep) {
                        Some(c) => c,
                        None => return Err("unknown_extension".to_string()),
                    };
                    if dep_cat.allowed_versions.len() != 1 {
                        return Err("extension_dependency_missing".to_string());
                    }
                    by_key.insert(
                        dkey,
                        Rec {
                            extension_request_id: format!("dep_{}_{}", db_id, dep),
                            database_id: db_id.clone(),
                            extension_id: dep.clone(),
                            version: dep_cat.allowed_versions[0].clone(),
                            selection_reason: "dependency".to_string(),
                        },
                    );
                    changed = true;
                }
            }
        }
    }

    // Cycle check via topological sort of the extension-id dependency graph.
    let ext_ids: BTreeSet<String> = by_key.keys().map(|(_, e)| e.clone()).collect();
    let mut nodes: BTreeSet<String> = ext_ids.clone();
    let mut adj: HashMap<String, Vec<String>> = HashMap::new();
    let mut indeg: HashMap<String, i32> = HashMap::new();
    for e in &ext_ids {
        indeg.entry(e.clone()).or_insert(0);
        if let Some(cat) = catalog.get(e) {
            for dep in &cat.requires {
                nodes.insert(dep.clone());
                adj.entry(dep.clone()).or_default().push(e.clone());
                *indeg.entry(e.clone()).or_insert(0) += 1;
                indeg.entry(dep.clone()).or_insert(0);
            }
        }
    }
    let mut ready: BTreeSet<String> = nodes
        .iter()
        .filter(|n| indeg.get(*n).copied().unwrap_or(0) == 0)
        .cloned()
        .collect();
    let mut ordered_exts: Vec<String> = Vec::new();
    while let Some(n) = ready.iter().next().cloned() {
        ready.remove(&n);
        ordered_exts.push(n.clone());
        if let Some(succ) = adj.get(&n).cloned() {
            for m in succ {
                let d = indeg.entry(m.clone()).or_insert(0);
                *d -= 1;
                if *d == 0 {
                    ready.insert(m);
                }
            }
        }
    }
    if ordered_exts.len() != nodes.len() {
        return Err("extension_dependency_cycle".to_string());
    }

    fn depth_of(
        ext_id: &str,
        catalog: &HashMap<String, ExtensionCatalogEntry>,
        memo: &mut HashMap<String, i64>,
    ) -> i64 {
        if let Some(&d) = memo.get(ext_id) {
            return d;
        }
        let deps = catalog
            .get(ext_id)
            .map(|c| c.requires.clone())
            .unwrap_or_default();
        let d = if deps.is_empty() {
            0
        } else {
            1 + deps
                .iter()
                .map(|dep| depth_of(dep, catalog, memo))
                .max()
                .unwrap_or(0)
        };
        memo.insert(ext_id.to_string(), d);
        d
    }

    let mut result: Vec<ExtRec> = Vec::new();
    let mut pos: i64 = 0;
    let mut depth_memo: HashMap<String, i64> = HashMap::new();
    let db_ids: BTreeSet<String> = by_key.keys().map(|(d, _)| d.clone()).collect();
    for db_id in db_ids {
        let mut entries: Vec<Rec> = by_key
            .iter()
            .filter(|((d, _), _)| d == &db_id)
            .map(|(_, rec)| rec.clone())
            .collect();
        entries.sort_by(|a, b| {
            let da = depth_of(&a.extension_id, catalog, &mut depth_memo);
            let db = depth_of(&b.extension_id, catalog, &mut depth_memo);
            (da, a.extension_id.clone(), a.version.clone(), a.extension_request_id.clone()).cmp(&(
                db,
                b.extension_id.clone(),
                b.version.clone(),
                b.extension_request_id.clone(),
            ))
        });
        for rec in entries {
            let depth = depth_of(&rec.extension_id, catalog, &mut depth_memo);
            result.push(ExtRec {
                extension_request_id: rec.extension_request_id,
                database_id: rec.database_id,
                extension_id: rec.extension_id,
                version: rec.version,
                selection_reason: rec.selection_reason,
                dependency_depth: depth,
                topological_position: pos,
            });
            pos += 1;
        }
    }
    Ok(result)
}

// ---------------------------------------------------------------------------
// Operation DAG helpers (mirrors reference/planner.py::_op_id / _topo_sort)
// ---------------------------------------------------------------------------

fn add_op(
    ops: &mut Vec<Op>,
    op_index: &mut HashMap<String, usize>,
    kind: &str,
    cid: &str,
    resource_id: &str,
    db_id: Option<&str>,
    mut deps: Vec<String>,
) -> String {
    deps.sort();
    let oid = op_id(kind, cid, resource_id, db_id);
    let op = Op {
        operation_id: oid.clone(),
        operation_kind: kind.to_string(),
        resource_id: resource_id.to_string(),
        database_id_or_null: db_id.map(|s| s.to_string()),
        depends_on_operation_ids: deps,
        topological_position: 0,
    };
    op_index.insert(oid.clone(), ops.len());
    ops.push(op);
    oid
}

fn op_id(kind: &str, cluster_id: &str, resource_id: &str, db_id: Option<&str>) -> String {
    if kind == "extension" {
        if let Some(db) = db_id {
            let last = resource_id.rsplit(':').next().unwrap_or(resource_id);
            return format!("extension:{}:{}:{}", cluster_id, db, last);
        }
    }
    match kind {
        "create_role" => format!("role:{}:{}", cluster_id, resource_id),
        "grant_role_membership" => format!("membership:{}:{}", cluster_id, resource_id),
        "alter_system_setting" => format!("system-setting:{}:{}", cluster_id, resource_id),
        "create_database" => format!("database:{}:{}", cluster_id, resource_id),
        "connect_database" => format!("connect:{}:{}", cluster_id, resource_id),
        "extension" => format!("extension:{}:{}", cluster_id, resource_id),
        "grant_database_privilege" | "grant_schema_privilege" | "grant_table_privilege" => {
            format!("privilege:{}:{}", cluster_id, resource_id)
        }
        "alter_database_setting" => format!("database-setting:{}:{}", cluster_id, resource_id),
        "alter_role_setting" => format!("role-setting:{}:{}", cluster_id, resource_id),
        "alter_role_database_setting" => {
            format!("role-database-setting:{}:{}", cluster_id, resource_id)
        }
        "emit_hba_rule" => format!("hba:{}:{}", cluster_id, resource_id),
        "reload_configuration" => format!("reload:{}", cluster_id),
        _ => format!("{}:{}:{}", kind, cluster_id, resource_id),
    }
}

fn op_effective_kind(op: &Op) -> String {
    if op.operation_kind == "extension" {
        "create_extension".to_string()
    } else {
        op.operation_kind.clone()
    }
}

fn phase_for_kind(kind: &str) -> &'static str {
    match kind {
        "create_role" | "grant_role_membership" => "cluster_transaction",
        "alter_system_setting" => "system_nontransactional",
        "create_database" => "database_create_nontransactional",
        "emit_hba_rule" | "reload_configuration" => "configuration_reload",
        _ => "database_transaction",
    }
}

fn phase_rank(kind: &str) -> i32 {
    match kind {
        "cluster_transaction" => 0,
        "system_nontransactional" => 1,
        "database_create_nontransactional" => 2,
        "database_transaction" => 3,
        "configuration_reload" => 4,
        _ => 9,
    }
}

fn operation_kind_rank(kind: &str) -> i32 {
    match kind {
        "create_role" => 0,
        "grant_role_membership" => 1,
        "alter_system_setting" => 2,
        "create_database" => 3,
        "connect_database" => 4,
        "create_extension" => 5,
        "grant_database_privilege" => 6,
        "grant_schema_privilege" => 7,
        "grant_table_privilege" => 8,
        "alter_database_setting" => 9,
        "alter_role_setting" => 10,
        "alter_role_database_setting" => 11,
        "emit_hba_rule" => 12,
        "reload_configuration" => 13,
        _ => 99,
    }
}

fn ready_key(op: &Op) -> (i32, String, i32, String, String) {
    let kind = op_effective_kind(op);
    let phase = phase_for_kind(&kind);
    (
        phase_rank(phase),
        op.database_id_or_null.clone().unwrap_or_default(),
        operation_kind_rank(&kind),
        op.resource_id.clone(),
        op.operation_id.clone(),
    )
}

fn topo_sort_ops(ops: &[Op]) -> Result<Vec<String>, Vec<String>> {
    let ids: Vec<String> = ops.iter().map(|o| o.operation_id.clone()).collect();
    let by_id: HashMap<&str, &Op> = ops.iter().map(|o| (o.operation_id.as_str(), o)).collect();
    let mut indeg: HashMap<String, i32> = ids.iter().map(|i| (i.clone(), 0)).collect();
    let mut adj: HashMap<String, Vec<String>> = ids.iter().map(|i| (i.clone(), Vec::new())).collect();
    for o in ops {
        for d in &o.depends_on_operation_ids {
            adj.entry(d.clone()).or_default().push(o.operation_id.clone());
            *indeg.entry(o.operation_id.clone()).or_insert(0) += 1;
        }
    }
    let mut ready: Vec<String> = ids.iter().filter(|i| indeg[*i] == 0).cloned().collect();
    ready.sort_by(|a, b| ready_key(by_id[a.as_str()]).cmp(&ready_key(by_id[b.as_str()])));
    let mut result: Vec<String> = Vec::new();
    while !ready.is_empty() {
        let n = ready.remove(0);
        result.push(n.clone());
        if let Some(succ) = adj.get(&n).cloned() {
            for m in succ {
                let d = indeg.entry(m.clone()).or_insert(0);
                *d -= 1;
                if *d == 0 {
                    ready.push(m);
                }
            }
        }
        ready.sort_by(|a, b| ready_key(by_id[a.as_str()]).cmp(&ready_key(by_id[b.as_str()])));
    }
    if result.len() != ids.len() {
        let mut remaining: Vec<String> = ids.iter().filter(|i| !result.contains(i)).cloned().collect();
        remaining.sort();
        return Err(remaining);
    }
    Ok(result)
}

// ---------------------------------------------------------------------------
// HBA ordering, containment, and shadow detection (mirrors reference/hba.py)
// ---------------------------------------------------------------------------

fn cidr_width(cidr: &Option<String>) -> i32 {
    match cidr {
        None => -1,
        Some(c) => c
            .rsplit('/')
            .next()
            .and_then(|p| p.parse::<i32>().ok())
            .unwrap_or(-1),
    }
}

fn db_selector_rank(sel: &str) -> i32 {
    if sel == "all" {
        0
    } else {
        1
    }
}

fn role_selector_rank(sel: &str) -> i32 {
    if sel == "all" {
        0
    } else {
        1
    }
}

fn connection_class_rank(ct: &str) -> i32 {
    match ct {
        "local" => 0,
        "host" => 1,
        "hostssl" => 2,
        _ => 9,
    }
}

fn db_contains(outer: &str, inner: &str) -> bool {
    outer == "all" || outer == inner
}

fn role_contains(outer: &str, inner: &str) -> bool {
    outer == "all" || outer == inner
}

fn connection_class_contains(outer: &str, inner: &str) -> bool {
    match outer {
        "local" => inner == "local",
        "host" => inner == "host",
        "hostssl" => inner == "hostssl",
        _ => false,
    }
}

fn cidr_supernet(outer: &Option<String>, inner: &Option<String>) -> bool {
    let (o, i) = match (outer, inner) {
        (Some(o), Some(i)) => (o, i),
        _ => return false,
    };
    let onet: ipnet::Ipv4Net = match o.parse() {
        Ok(n) => n,
        Err(_) => return false,
    };
    let inet: ipnet::Ipv4Net = match i.parse() {
        Ok(n) => n,
        Err(_) => return false,
    };
    onet.contains(&inet)
}

fn address_contains(outer: &HbaRec, inner: &HbaRec) -> bool {
    let otype = outer.connection_type.as_str();
    let itype = inner.connection_type.as_str();
    match otype {
        "local" => itype == "local",
        "host" => itype == "host" && cidr_supernet(&outer.ipv4_cidr_or_null, &inner.ipv4_cidr_or_null),
        "hostssl" => {
            itype == "hostssl" && cidr_supernet(&outer.ipv4_cidr_or_null, &inner.ipv4_cidr_or_null)
        }
        _ => false,
    }
}

fn hba_sort_key(row: &HbaRec) -> (i32, i32, i32, i64, i32, i32, i64, String) {
    let mandatory_reject = if row.mandatory && row.auth_method == "reject" {
        0
    } else {
        1
    };
    let cidr_w = cidr_width(&row.ipv4_cidr_or_null);
    let cidr_component: i64 = if row.ipv4_cidr_or_null.is_some() {
        -(cidr_w as i64)
    } else {
        0
    };
    let source_rank = if row.source == "policy" { 0 } else { 1 };
    (
        mandatory_reject,
        db_selector_rank(&row.database_selector),
        role_selector_rank(&row.role_selector),
        cidr_component,
        -connection_class_rank(&row.connection_type),
        source_rank,
        -row.priority,
        row.hba_id.clone(),
    )
}

fn order_hba_rows(mut rows: Vec<HbaRec>) -> Vec<HbaRec> {
    rows.sort_by(|a, b| hba_sort_key(a).cmp(&hba_sort_key(b)));
    rows
}

fn find_shadow(rows: &[HbaRec]) -> Option<(String, String)> {
    let ordered = order_hba_rows(rows.to_vec());
    for i in 0..ordered.len() {
        for j in 0..i {
            let earlier = &ordered[j];
            let later = &ordered[i];
            if connection_class_contains(&earlier.connection_type, &later.connection_type)
                && db_contains(&earlier.database_selector, &later.database_selector)
                && role_contains(&earlier.role_selector, &later.role_selector)
                && address_contains(earlier, later)
            {
                return Some((later.hba_id.clone(), earlier.hba_id.clone()));
            }
        }
    }
    None
}

// ---------------------------------------------------------------------------
// Privilege ordering (mirrors reference/sql.py::sort_privileges)
// ---------------------------------------------------------------------------

const PRIVILEGE_ORDER: [&str; 7] = ["CONNECT", "CREATE", "USAGE", "SELECT", "INSERT", "UPDATE", "DELETE"];

fn privilege_rank(p: &str) -> usize {
    PRIVILEGE_ORDER
        .iter()
        .position(|x| *x == p)
        .unwrap_or(PRIVILEGE_ORDER.len())
}

fn sort_privileges(mut privs: Vec<String>) -> Vec<String> {
    privs.sort_by_key(|p| privilege_rank(p));
    privs
}

// ---------------------------------------------------------------------------
// IPv4 CIDR normalization
// ---------------------------------------------------------------------------

fn normalize_ipv4_cidr(cidr: &str) -> Result<String, String> {
    let net: ipnet::Ipv4Net = cidr
        .parse()
        .map_err(|_| format!("invalid ipv4 cidr: {cidr}"))?;
    let network = net.network();
    Ok(format!("{}/{}", network, net.prefix_len()))
}

// ---------------------------------------------------------------------------
// SQL statement rendering (mirrors reference/sql.py)
// ---------------------------------------------------------------------------

fn grant_option_suffix(grant_option: bool) -> &'static str {
    if grant_option {
        " WITH GRANT OPTION"
    } else {
        ""
    }
}

fn create_role_sql(role: &RoleRec) -> String {
    let attrs = [
        if role.login { "LOGIN" } else { "NOLOGIN" },
        if role.inherit { "INHERIT" } else { "NOINHERIT" },
        if role.createdb { "CREATEDB" } else { "NOCREATEDB" },
        if role.createrole { "CREATEROLE" } else { "NOCREATEROLE" },
        if role.replication { "REPLICATION" } else { "NOREPLICATION" },
        if role.bypassrls { "BYPASSRLS" } else { "NOBYPASSRLS" },
    ];
    format!(
        "CREATE ROLE {} WITH {} CONNECTION LIMIT {};",
        quote_ident(&role.role_name),
        attrs.join(" "),
        role.connection_limit
    )
}

fn grant_membership_sql(granted: &str, member: &str) -> String {
    format!("GRANT {} TO {};", quote_ident(granted), quote_ident(member))
}

fn alter_system_sql(setting_name: &str, literal: &str) -> String {
    format!("ALTER SYSTEM SET {} = {};", quote_ident(setting_name), literal)
}

fn create_database_sql(db: &DbRec, owner_name: &str) -> String {
    format!(
        "CREATE DATABASE {} WITH OWNER = {} TEMPLATE = {} ENCODING = {} CONNECTION LIMIT = {};",
        quote_ident(&db.database_name),
        quote_ident(owner_name),
        quote_ident(&db.template),
        quote_string(&db.encoding),
        db.connection_limit
    )
}

fn connect_directive(db_name: &str) -> String {
    format!("\\connect {}", quote_ident(db_name))
}

fn create_extension_sql(ext_id: &str, version: &str) -> String {
    format!(
        "CREATE EXTENSION IF NOT EXISTS {} WITH VERSION {};",
        quote_ident(ext_id),
        quote_string(version)
    )
}

fn grant_database_sql(privs: &[String], db_name: &str, role_name: &str, grant_option: bool) -> String {
    let joined = sort_privileges(privs.to_vec()).join(", ");
    format!(
        "GRANT {} ON DATABASE {} TO {}{};",
        joined,
        quote_ident(db_name),
        quote_ident(role_name),
        grant_option_suffix(grant_option)
    )
}

fn grant_schema_sql(privs: &[String], schema: &str, role_name: &str, grant_option: bool) -> String {
    let joined = sort_privileges(privs.to_vec()).join(", ");
    format!(
        "GRANT {} ON SCHEMA {} TO {}{};",
        joined,
        quote_ident(schema),
        quote_ident(role_name),
        grant_option_suffix(grant_option)
    )
}

fn alter_database_setting_sql(db_name: &str, setting_name: &str, literal: &str) -> String {
    format!(
        "ALTER DATABASE {} SET {} = {};",
        quote_ident(db_name),
        quote_ident(setting_name),
        literal
    )
}

fn hba_comment(row: &HbaRec) -> String {
    let cidr = row.ipv4_cidr_or_null.clone().unwrap_or_else(|| "-".to_string());
    format!(
        "-- PG_HBA {} {} {} {} {} id={} source={}",
        row.connection_type,
        row.database_selector,
        row.role_selector,
        cidr,
        row.auth_method,
        row.hba_id,
        row.source
    )
}

fn reload_sql() -> String {
    "SELECT pg_reload_conf();".to_string()
}

fn setting_literal(value: &Value, value_type: &str) -> String {
    match value_type {
        "integer" => value.as_i64().unwrap_or(0).to_string(),
        "boolean" => {
            if value.as_bool().unwrap_or(false) {
                "'on'".to_string()
            } else {
                "'off'".to_string()
            }
        }
        "string" => quote_string(value.as_str().unwrap_or("")),
        "string_array" => {
            let items: Vec<String> = value
                .as_array()
                .map(|a| a.iter().map(|v| v.as_str().unwrap_or("").to_string()).collect())
                .unwrap_or_default();
            quote_string(&items.join(","))
        }
        _ => String::new(),
    }
}

// ---------------------------------------------------------------------------
// Phase construction and serialization (mirrors reference/planner.py::_build_phase_struct
// and reference/sql.py::serialize_phases)
// ---------------------------------------------------------------------------

struct Phase {
    phase_index: i64,
    phase_kind: String,
    database_id_or_null: Option<String>,
    transactional: bool,
    connect_line: Option<String>,
    statements: Vec<String>,
    operation_ids: Vec<String>,
    requires_reload: bool,
    requires_restart: bool,
}

fn build_phases(ac: &AcceptedCluster, _setting_catalog: &HashMap<String, SettingCatalogEntry>) -> Vec<Phase> {
    let roles_by_id: HashMap<&str, &RoleRec> = ac.roles.iter().map(|r| (r.role_id.as_str(), r)).collect();
    let dbs_by_id: HashMap<&str, &DbRec> = ac.databases.iter().map(|d| (d.database_id.as_str(), d)).collect();
    let op_by_id: HashMap<&str, &Op> = ac
        .operations
        .iter()
        .map(|o| (o.operation_id.as_str(), o))
        .collect();

    let mut phases: Vec<Phase> = Vec::new();
    let mut idx: i64 = 0;

    let mut cluster_stmts: Vec<String> = Vec::new();
    let mut cluster_ops: Vec<String> = Vec::new();
    for oid in &ac.topo {
        let op = op_by_id[oid.as_str()];
        if op.operation_kind == "create_role" {
            let role = roles_by_id[op.resource_id.as_str()];
            cluster_stmts.push(create_role_sql(role));
            cluster_ops.push(oid.clone());
        } else if op.operation_kind == "grant_role_membership" {
            if let Some(m) = ac.memberships.iter().find(|m| m.membership_id == op.resource_id) {
                let granted = roles_by_id[m.granted_role_id.as_str()];
                let member = roles_by_id[m.member_role_id.as_str()];
                cluster_stmts.push(grant_membership_sql(&granted.role_name, &member.role_name));
                cluster_ops.push(oid.clone());
            }
        }
    }
    if !cluster_stmts.is_empty() {
        phases.push(Phase {
            phase_index: idx,
            phase_kind: "cluster_transaction".to_string(),
            database_id_or_null: None,
            transactional: true,
            connect_line: None,
            statements: cluster_stmts,
            operation_ids: cluster_ops,
            requires_reload: false,
            requires_restart: false,
        });
        idx += 1;
    }

    for oid in &ac.topo {
        let op = op_by_id[oid.as_str()];
        if op.operation_kind == "alter_system_setting" {
            if let Some(s) = ac.settings.iter().find(|s| s.setting_id == op.resource_id) {
                let lit = setting_literal(&s.normalized_value, &s.value_type);
                let needs_restart = s.activation_mode == "restart";
                phases.push(Phase {
                    phase_index: idx,
                    phase_kind: "system_nontransactional".to_string(),
                    database_id_or_null: None,
                    transactional: false,
                    connect_line: None,
                    statements: vec![alter_system_sql(&s.setting_name, &lit)],
                    operation_ids: vec![oid.clone()],
                    requires_reload: s.activation_mode == "reload",
                    requires_restart: needs_restart,
                });
                idx += 1;
            }
        }
    }

    for oid in &ac.topo {
        let op = op_by_id[oid.as_str()];
        if op.operation_kind == "create_database" {
            if let Some(db) = dbs_by_id.get(op.resource_id.as_str()) {
                let owner = roles_by_id[db.owner_role_id.as_str()];
                phases.push(Phase {
                    phase_index: idx,
                    phase_kind: "database_create_nontransactional".to_string(),
                    database_id_or_null: Some(db.database_id.clone()),
                    transactional: false,
                    connect_line: None,
                    statements: vec![create_database_sql(db, &owner.role_name)],
                    operation_ids: vec![oid.clone()],
                    requires_reload: false,
                    requires_restart: false,
                });
                idx += 1;
            }
        }
    }

    let mut db_ids: Vec<&str> = ac.databases.iter().map(|d| d.database_id.as_str()).collect();
    db_ids.sort();
    for db_id in db_ids {
        let db = dbs_by_id[db_id];
        let connect_line = connect_directive(&db.database_name);
        let mut db_stmts: Vec<String> = Vec::new();
        let mut db_ops: Vec<String> = Vec::new();
        for oid in &ac.topo {
            let op = op_by_id[oid.as_str()];
            let matches_db = op.database_id_or_null.as_deref() == Some(db_id);

            if op.operation_kind == "connect_database" && op.resource_id == db_id {
                db_ops.push(oid.clone());
                continue;
            }

            // Role-scoped settings are attached after phases are built so we never
            // invent an empty SQL phase solely for metadata.
            if op.operation_kind == "alter_role_setting" {
                continue;
            }

            if op.operation_kind == "alter_role_database_setting" {
                if matches_db {
                    db_ops.push(oid.clone());
                }
                continue;
            }

            if op.operation_kind == "grant_table_privilege" {
                if matches_db {
                    db_ops.push(oid.clone());
                }
                continue;
            }

            if op.operation_kind == "extension" || op.operation_kind == "create_extension" {
                let parts: Vec<&str> = op.operation_id.split(':').collect();
                let ext_db = if parts.len() >= 4 { parts[2] } else { "" };
                if ext_db != db_id && !matches_db {
                    continue;
                }
                let ext_id = op.operation_id.rsplit(':').next().unwrap_or("");
                if let Some(ext) = ac
                    .extensions
                    .iter()
                    .find(|e| e.extension_id == ext_id && e.database_id == db_id)
                {
                    db_stmts.push(create_extension_sql(&ext.extension_id, &ext.version));
                    db_ops.push(oid.clone());
                }
                continue;
            }

            if !matches_db {
                continue;
            }

            if op.operation_kind == "grant_database_privilege" {
                if let Some(p) = ac.privileges.iter().find(|p| p.grant_id == op.resource_id) {
                    let role = roles_by_id[p.grantee_role_id.as_str()];
                    db_stmts.push(grant_database_sql(
                        &p.privileges,
                        &db.database_name,
                        &role.role_name,
                        p.grant_option,
                    ));
                    db_ops.push(oid.clone());
                }
            } else if op.operation_kind == "grant_schema_privilege" {
                if let Some(p) = ac.privileges.iter().find(|p| p.grant_id == op.resource_id) {
                    let role = roles_by_id[p.grantee_role_id.as_str()];
                    let schema = p.schema_name_or_null.clone().unwrap_or_default();
                    db_stmts.push(grant_schema_sql(&p.privileges, &schema, &role.role_name, p.grant_option));
                    db_ops.push(oid.clone());
                }
            } else if op.operation_kind == "alter_database_setting" {
                if let Some(s) = ac.settings.iter().find(|s| s.setting_id == op.resource_id) {
                    let lit = setting_literal(&s.normalized_value, &s.value_type);
                    db_stmts.push(alter_database_setting_sql(&db.database_name, &s.setting_name, &lit));
                    db_ops.push(oid.clone());
                }
            }
        }
        if !db_stmts.is_empty() {
            phases.push(Phase {
                phase_index: idx,
                phase_kind: "database_transaction".to_string(),
                database_id_or_null: Some(db_id.to_string()),
                transactional: true,
                connect_line: Some(connect_line),
                statements: db_stmts,
                operation_ids: db_ops,
                requires_reload: false,
                requires_restart: false,
            });
            idx += 1;
        }
    }

    let mut reload_stmts: Vec<String> = ac.hba_rows.iter().map(hba_comment).collect();
    let mut reload_ops: Vec<String> = Vec::new();
    for oid in &ac.topo {
        let op = op_by_id[oid.as_str()];
        if op.operation_kind == "emit_hba_rule" || op.operation_kind == "reload_configuration" {
            reload_ops.push(oid.clone());
        }
    }
    let has_reload = ac.settings.iter().any(|s| s.activation_mode == "reload") || !ac.hba_rows.is_empty();
    let has_restart = ac.settings.iter().any(|s| s.activation_mode == "restart");
    if has_reload {
        reload_stmts.push(reload_sql());
        phases.push(Phase {
            phase_index: idx,
            phase_kind: "configuration_reload".to_string(),
            database_id_or_null: None,
            transactional: false,
            connect_line: None,
            statements: reload_stmts,
            operation_ids: reload_ops,
            requires_reload: true,
            requires_restart: has_restart,
        });
    }

    // Attach role-scoped settings to the first database_transaction phase when one
    // exists; otherwise to cluster_transaction. Metadata only — no SQL change.
    let mut assigned: HashSet<String> = HashSet::new();
    for p in &phases {
        for oid in &p.operation_ids {
            assigned.insert(oid.clone());
        }
    }
    let attach_idx = phases
        .iter()
        .position(|p| p.phase_kind == "database_transaction")
        .or_else(|| phases.iter().position(|p| p.phase_kind == "cluster_transaction"));
    if let Some(pi) = attach_idx {
        for oid in &ac.topo {
            let op = op_by_id[oid.as_str()];
            if op.operation_kind == "alter_role_setting" && !assigned.contains(oid) {
                phases[pi].operation_ids.push(oid.clone());
                assigned.insert(oid.clone());
            }
        }
    }

    phases
}

fn serialize_phases(phases: &[Phase], cluster_id: &str) -> String {
    let mut lines: Vec<String> = Vec::new();
    for phase in phases {
        if !lines.is_empty() {
            lines.push(String::new());
        }
        lines.push(format!(
            "-- PHASE {} {} cluster={}",
            phase.phase_index, phase.phase_kind, cluster_id
        ));
        if phase.phase_kind == "database_transaction" {
            if let Some(cl) = &phase.connect_line {
                lines.push(cl.clone());
            }
            lines.push("BEGIN;".to_string());
            lines.extend(phase.statements.iter().cloned());
            lines.push("COMMIT;".to_string());
        } else if phase.transactional {
            lines.push("BEGIN;".to_string());
            lines.extend(phase.statements.iter().cloned());
            lines.push("COMMIT;".to_string());
        } else {
            lines.extend(phase.statements.iter().cloned());
        }
    }
    if lines.is_empty() {
        return String::new();
    }
    let mut result = lines.join("\n");
    result.push('\n');
    result
}
