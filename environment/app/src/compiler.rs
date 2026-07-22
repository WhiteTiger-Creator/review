//! Bootstrap planner orchestration (candidate starter — not implemented).

use crate::error::FatalError;
use crate::output;
use std::path::Path;

pub fn run(
    _yaml: &Path,
    _toml: &Path,
    _extension_catalog: &Path,
    _setting_catalog: &Path,
    _policy_url: &str,
    sql_out: &Path,
    plan_out: &Path,
) -> Result<u8, FatalError> {
    output::remove_stale_outputs(sql_out, plan_out)?;
    Err(FatalError::new(
        "not_implemented",
        "bootstrap planner logic is not implemented",
    ))
}
