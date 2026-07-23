use crate::err::Result;
use crate::r7::fence_r7::commit_fence_d;
use crate::support::shape_u5::{JournalFrame, ScheduleView, ShadowLedger, StageHeap};

pub fn apply_fence(
    heap: &mut StageHeap,
    shadow: &mut ShadowLedger,
    schedule: &ScheduleView,
    journal: &mut Vec<JournalFrame>,
) -> Result<()> {
    commit_fence_d(heap, shadow, schedule, journal)
}
