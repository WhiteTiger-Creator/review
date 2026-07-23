use crate::support::shape_u5::JournalFrame;

/// Counts journal kinds for bench tooling; not on the live resume path.
pub fn count_kind(frames: &[JournalFrame], kind: &str) -> usize {
    frames.iter().filter(|f| f.kind == kind).count()
}

pub fn last_ordinal(frames: &[JournalFrame]) -> u64 {
    frames.last().map(|f| f.ordinal).unwrap_or(0)
}
