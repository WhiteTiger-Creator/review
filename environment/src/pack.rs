use crate::fmt::Fmt;
use crate::mode::Mode;

pub fn encode_value(
    _sign: u64,
    _m: u128,
    _e: i128,
    _dest: Fmt,
    _mode: Mode,
) -> (u64, bool, bool, bool) {
    (0, false, false, false)
}
