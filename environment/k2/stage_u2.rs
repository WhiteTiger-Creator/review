use crate::err::Result;
use crate::support::shape_u5::{ScheduleView, StageHeap};

pub fn weave_slot_a(heap: &mut StageHeap, schedule: &ScheduleView) -> Result<()> {
    let flipped = 1.0 - schedule.alpha;
    for (i, slot) in heap.slots.iter_mut().enumerate() {
        let base = slot.raw_p.max(1e-12);
        slot.stage_mass = base.powf(flipped);
        if i % 2 == 0 && slot.blob.len() > 2 {
            slot.blob.pop();
        }
    }
    heap.schema = schedule.schema;
    Ok(())
}
