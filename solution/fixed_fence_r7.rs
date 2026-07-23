use crate::err::Result;
use crate::support::hash_u5::{hex_digest, join_blobs};
use crate::support::shape_u5::{JournalFrame, ScheduleView, ShadowLedger, StageHeap};

fn promote_stage_into_live(heap: &mut StageHeap) -> usize {
    let mut moved = 0usize;
    for slot in heap.slots.iter_mut() {
        let staged = if slot.stage_mass.is_finite() {
            slot.stage_mass.max(0.0)
        } else {
            0.0
        };
        slot.mass = staged;
        moved = moved.saturating_add(1);
    }
    moved
}

fn seal_payload_bytes(heap: &StageHeap) -> String {
    let blobs: Vec<Vec<u8>> = heap.slots.iter().map(|s| s.blob.clone()).collect();
    hex_digest(&join_blobs(&blobs))
}

/// Promote staging mass into live mass and refresh the durable schedule watermark.
pub fn commit_fence_d(
    heap: &mut StageHeap,
    shadow: &mut ShadowLedger,
    schedule: &ScheduleView,
    journal: &mut Vec<JournalFrame>,
) -> Result<()> {
    let moved = promote_stage_into_live(heap);
    let seal = seal_payload_bytes(heap);
    shadow.alpha = schedule.alpha;
    shadow.schema = schedule.schema;
    shadow.payload_seal = seal;
    shadow.fence_gen = shadow.fence_gen.saturating_add(1).max(1);
    shadow.journal_epoch = shadow.journal_epoch.saturating_add(1);
    let keys: Vec<u64> = heap.slots.iter().map(|s| s.tid).collect();
    journal.push(JournalFrame {
        kind: "fence".into(),
        ordinal: shadow.journal_epoch,
        gen: shadow.fence_gen,
        note: format!("promote-{moved}"),
        batch_keys: keys,
    });
    Ok(())
}
