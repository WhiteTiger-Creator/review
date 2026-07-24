//! Typed input and output models for the bootstrap planner.

use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Clone, Deserialize)]
pub struct ClustersDoc {
    pub clusters: Vec<ClusterInput>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ClusterInput {
    pub cluster_id: String,
    pub environment: String,
    pub roles: Vec<RoleInput>,
    #[serde(default)]
    pub role_memberships: Vec<MembershipInput>,
    #[serde(default)]
    pub databases: Vec<DatabaseInput>,
    #[serde(default)]
    pub extensions: Vec<ExtensionInput>,
    #[serde(default)]
    pub privileges: Vec<PrivilegeInput>,
    #[serde(default)]
    pub hba_rules: Vec<HbaInput>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct RoleInput {
    pub role_id: String,
    pub role_name: String,
    pub login: bool,
    pub inherit: bool,
    pub createdb: bool,
    pub createrole: bool,
    pub replication: bool,
    pub bypassrls: bool,
    pub connection_limit: i64,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct MembershipInput {
    pub membership_id: String,
    pub member_role_id: String,
    pub granted_role_id: String,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct DatabaseInput {
    pub database_id: String,
    pub database_name: String,
    pub owner_role_id: String,
    pub template: String,
    pub encoding: String,
    pub connection_limit: i64,
    pub environment_allowlist: Vec<String>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct ExtensionInput {
    pub extension_request_id: String,
    pub database_id: String,
    pub extension_id: String,
    pub version: String,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct PrivilegeInput {
    pub grant_id: String,
    pub scope: String,
    pub database_id: String,
    pub schema_name_or_null: Option<String>,
    pub table_name_or_null: Option<String>,
    pub grantee_role_id: String,
    pub privileges: Vec<String>,
    pub grant_option: bool,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct HbaInput {
    pub hba_id: String,
    pub connection_type: String,
    pub database_selector: String,
    pub role_selector: String,
    pub ipv4_cidr_or_null: Option<String>,
    pub auth_method: String,
    pub priority: i64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SettingsDoc {
    pub settings: Vec<SettingInput>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct SettingInput {
    pub setting_id: String,
    pub cluster_id: String,
    pub scope: String,
    #[serde(default)]
    pub database_id_or_null: Option<String>,
    #[serde(default)]
    pub role_id_or_null: Option<String>,
    pub setting_name: String,
    pub value: Value,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ExtensionCatalogDoc {
    pub extensions: Vec<ExtensionCatalogEntry>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ExtensionCatalogEntry {
    pub extension_id: String,
    pub allowed_versions: Vec<String>,
    pub requires: Vec<String>,
    pub trusted: bool,
    pub required_settings: Vec<ExtensionRequiredSetting>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ExtensionRequiredSetting {
    pub setting_name: String,
    pub scope: String,
    pub required_value_contains_or_null: Option<String>,
    pub required_value_equals_or_null: Option<Value>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SettingCatalogDoc {
    pub settings: Vec<SettingCatalogEntry>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SettingCatalogEntry {
    pub setting_name: String,
    pub value_type: String,
    pub allowed_scopes: Vec<String>,
    pub minimum_integer_or_null: Option<i64>,
    pub maximum_integer_or_null: Option<i64>,
    pub activation_mode: String,
    pub transaction_compatible: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct BootstrapPlan {
    pub schema_version: i64,
    pub policy_snapshot_rows: Vec<PolicySnapshotRow>,
    pub cluster_rows: Vec<ClusterRow>,
    pub role_rows: Vec<RoleRow>,
    pub membership_rows: Vec<MembershipRow>,
    pub database_rows: Vec<DatabaseRow>,
    pub extension_rows: Vec<ExtensionRow>,
    pub privilege_rows: Vec<PrivilegeRow>,
    pub hba_rows: Vec<HbaRow>,
    pub setting_rows: Vec<SettingRow>,
    pub operation_rows: Vec<OperationRow>,
    pub phase_rows: Vec<PhaseRow>,
    pub rejection_rows: Vec<RejectionRow>,
    pub summary: Summary,
    pub sql_sha256: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct PolicySnapshotRow {
    pub environment: String,
    pub policy_revision: String,
    pub fragment_rows: Vec<FragmentRow>,
}

#[derive(Debug, Clone, Serialize)]
pub struct FragmentRow {
    pub fragment_id: String,
    pub body_sha256: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ClusterRow {
    pub cluster_id: String,
    pub environment: String,
    pub status: String,
    pub reason_or_null: Option<String>,
    pub requires_reload: bool,
    pub requires_restart: bool,
    pub role_count: i64,
    pub database_count: i64,
    pub extension_count: i64,
    pub privilege_count: i64,
    pub hba_count: i64,
    pub setting_count: i64,
    pub operation_count: i64,
    pub phase_count: i64,
}

#[derive(Debug, Clone, Serialize)]
pub struct RoleRow {
    pub cluster_id: String,
    pub role_id: String,
    pub role_name: String,
    pub source: String,
    pub login: bool,
    pub inherit: bool,
    pub createdb: bool,
    pub createrole: bool,
    pub replication: bool,
    pub bypassrls: bool,
    pub connection_limit: i64,
}

#[derive(Debug, Clone, Serialize)]
pub struct MembershipRow {
    pub cluster_id: String,
    pub membership_id: String,
    pub member_role_id: String,
    pub granted_role_id: String,
    pub source: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct DatabaseRow {
    pub cluster_id: String,
    pub database_id: String,
    pub database_name: String,
    pub owner_role_id: String,
    pub template: String,
    pub encoding: String,
    pub connection_limit: i64,
    pub source: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ExtensionRow {
    pub cluster_id: String,
    pub database_id: String,
    pub extension_id: String,
    pub version: String,
    pub selection_reason: String,
    pub dependency_depth: i64,
    pub topological_position: i64,
}

#[derive(Debug, Clone, Serialize)]
pub struct PrivilegeRow {
    pub cluster_id: String,
    pub grant_id: String,
    pub scope: String,
    pub database_id: String,
    pub schema_name_or_null: Option<String>,
    pub table_name_or_null: Option<String>,
    pub grantee_role_id: String,
    pub privileges: Vec<String>,
    pub grant_option: bool,
    pub source: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct HbaRow {
    pub cluster_id: String,
    pub hba_position: i64,
    pub hba_id: String,
    pub connection_type: String,
    pub database_selector: String,
    pub role_selector: String,
    pub ipv4_cidr_or_null: Option<String>,
    pub auth_method: String,
    pub source: String,
    pub mandatory: bool,
    pub priority: i64,
}

#[derive(Debug, Clone, Serialize)]
pub struct SettingRow {
    pub cluster_id: String,
    pub setting_id: String,
    pub scope: String,
    pub database_id_or_null: Option<String>,
    pub role_id_or_null: Option<String>,
    pub setting_name: String,
    pub normalized_value: Value,
    pub activation_mode: String,
    pub transaction_compatible: bool,
    pub source: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct OperationRow {
    pub cluster_id: String,
    pub operation_id: String,
    pub operation_kind: String,
    pub resource_id: String,
    pub database_id_or_null: Option<String>,
    pub depends_on_operation_ids: Vec<String>,
    pub topological_position: i64,
    pub phase_index: i64,
}

#[derive(Debug, Clone, Serialize)]
pub struct PhaseRow {
    pub cluster_id: String,
    pub phase_index: i64,
    pub phase_kind: String,
    pub database_id_or_null: Option<String>,
    pub transactional: bool,
    pub operation_ids: Vec<String>,
    pub requires_reload: bool,
    pub requires_restart: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct RejectionRow {
    pub cluster_id: String,
    pub stage: String,
    pub reason: String,
    pub resource_id_or_null: Option<String>,
    pub details: Value,
}

#[derive(Debug, Clone, Serialize)]
pub struct Summary {
    pub cluster_count: i64,
    pub accepted_cluster_count: i64,
    pub rejected_cluster_count: i64,
    pub policy_snapshot_count: i64,
    pub role_count: i64,
    pub membership_count: i64,
    pub database_count: i64,
    pub extension_count: i64,
    pub privilege_count: i64,
    pub hba_count: i64,
    pub setting_count: i64,
    pub operation_count: i64,
    pub phase_count: i64,
    pub reload_required_cluster_count: i64,
    pub restart_required_cluster_count: i64,
}
