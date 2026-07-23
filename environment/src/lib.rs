//! apkseal library crate.
//!
//! Re-exports the loaders (`conf`, `load`) and the ordered decision units
//! (`knurl`, `splice`, `rift`, `weir`, `seal`, `emit`) plus the unused
//! `decoy` helper. The two binaries under `cmd/` drive these units.

#[path = "../internal/conf/mod.rs"]
pub mod conf;
#[path = "../internal/load/mod.rs"]
pub mod load;

#[path = "../pkg/knurl/mod.rs"]
pub mod knurl;
#[path = "../pkg/splice/mod.rs"]
pub mod splice;
#[path = "../pkg/rift/mod.rs"]
pub mod rift;
#[path = "../pkg/weir/mod.rs"]
pub mod weir;
#[path = "../pkg/seal/mod.rs"]
pub mod seal;
#[path = "../pkg/emit/mod.rs"]
pub mod emit;
#[path = "../pkg/decoy/mod.rs"]
pub mod decoy;
