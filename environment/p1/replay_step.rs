use crate::err::Result;
use crate::n5::replay_n5::fold_journal_e;
use crate::support::shape_u5::{MetaState, ShadowLedger, StageHeap};

pub fn resume_fold(
    snap_heap: &StageHeap,
    journal_lines: &[String],
    shadow: &ShadowLedger,
) -> Result<(StageHeap, ShadowLedger, MetaState)> {
    fold_journal_e(snap_heap, journal_lines, shadow)
}
