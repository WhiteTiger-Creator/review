//! SQL identifier/literal quoting helpers (neutral; no bootstrap SQL bodies).

#![allow(dead_code)]

pub use crate::canonical::{quote_ident, quote_string};

/// Build a rejection-row shaped JSON object without deciding policy outcomes.
pub fn rejection_row(
    cluster_id: &str,
    stage: &str,
    reason: &str,
    resource_id_or_null: Option<&str>,
    details: serde_json::Value,
) -> serde_json::Value {
    serde_json::json!({
        "cluster_id": cluster_id,
        "stage": stage,
        "reason": reason,
        "resource_id_or_null": resource_id_or_null,
        "details": details,
    })
}
