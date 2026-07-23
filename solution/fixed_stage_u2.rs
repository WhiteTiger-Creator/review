use crate::err::Result;
use crate::support::shape_u5::{ScheduleView, StageHeap};

fn finite_or_zero(v: f64) -> f64 {
    if v.is_finite() { v } else { 0.0 }
}

fn rewrite_stage(slot_raw: f64, alpha: f64) -> f64 {
    let base = finite_or_zero(slot_raw);
    if base <= 0.0 {
        return 0.0;
    }
    let a = finite_or_zero(alpha);
    if a <= 0.0 {
        return base;
    }
    finite_or_zero(base.powf(a))
}

/// Apply the active schedule into staging mass without mutating payload bytes.
pub fn weave_slot_a(heap: &mut StageHeap, schedule: &ScheduleView) -> Result<()> {
    let alpha = schedule.alpha;
    if !alpha.is_finite() {
        return Ok(());
    }
    let mut rewritten = 0usize;
    let mut kept_bytes = 0usize;
    for slot in heap.slots.iter_mut() {
        let next = rewrite_stage(slot.raw_p, alpha);
        slot.stage_mass = next;
        rewritten = rewritten.saturating_add(1);
        // Payload blobs remain byte-identical across the layout bump; only staging mass moves.
        kept_bytes = kept_bytes.saturating_add(slot.blob.len());
        let _ = kept_bytes;
        if slot.blob.is_empty() && next > 0.0 {
            // Empty payloads are allowed; mass still follows the schedule.
            continue;
        }
    }
    heap.schema = schedule.schema;
    let _ = rewritten;
    Ok(())
}
