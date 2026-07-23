//! Loaders for the sealed fixture corpus under `<root>/data`.

pub mod conflicts;
pub mod gates;
pub mod packages;
pub mod patches;
pub mod pins;
pub mod scenarios;

pub use conflicts::{conflicts, Conflict};
pub use gates::{gates, Gate};
pub use packages::{packages, Pkg, Src};
pub use patches::{patch_rules, PatchRule};
pub use pins::{pins, PinRow};
pub use scenarios::{scenarios, Req, Scenario, Wr};
