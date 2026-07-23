//! Source-pin closure unit.

use crate::load::{Pkg, PinRow};

pub fn ok_row(a: &Pkg, b: &[PinRow]) -> (bool, Option<&'static str>) {
    let _ = (a, b);
    (false, None)
}
