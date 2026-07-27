//! Planner scaffolding for the starter crate.
//! Bounded graph resolution, patch overlay, replacement projection, and
//! lock-entry reuse are not implemented.

use serde_json::Value;

use crate::models::Dataset;

/// Per-request bounded resolution is not implemented in the starter.
pub fn build_report(_ds: &Dataset) -> Value {
    unimplemented!("recovery report construction is not implemented")
}
