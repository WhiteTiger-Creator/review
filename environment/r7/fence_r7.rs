use crate::err::Result;
use crate::support::shape_u5::{JournalFrame, ScheduleView, ShadowLedger, StageHeap};

pub fn commit_fence_d(
    heap: &mut StageHeap,
    shadow: &mut ShadowLedger,
    schedule: &ScheduleView,
    journal: &mut Vec<JournalFrame>,
) -> Result<()> {
    let _ = heap;
    let _ = schedule;
    shadow.journal_epoch = shadow.journal_epoch.saturating_add(1);
    journal.push(JournalFrame {
        kind: "fence".into(),
        ordinal: shadow.journal_epoch,
        gen: shadow.fence_gen,
        note: "epoch-bump".into(),
        batch_keys: vec![],
    });
    Ok(())
}
