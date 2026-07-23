//! Ledger sealing unit.
//!
//! Line layout for each contributing row:
//! scenario_id|package_id|version|pinned|patches_ok|admitted
//! (lowercase true/false, trailing newline). Which rows contribute is defined
//! by the sealed worked examples under /app/data/conformance/.

#[derive(Debug, Clone)]
pub struct Line {
    pub scenario_id: String,
    pub package_id: String,
    pub version: String,
    pub pinned: bool,
    pub patches_ok: bool,
    pub admitted: bool,
}

pub fn fold_hex(a: &[Line]) -> String {
    let _ = a;
    String::new()
}
