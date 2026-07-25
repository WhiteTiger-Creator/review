pub const MANT_MASK: u64 = (1u64 << 52) - 1;
pub const QUIET: u64 = 1u64 << 51;
pub const POS_INF: u64 = 0x7ff0000000000000;
pub const NEG_INF: u64 = 0xfff0000000000000;

pub fn classify(word: u64) -> (u64, u64, u64) {
    ((word >> 63) & 1, (word >> 52) & 0x7ff, word & MANT_MASK)
}
