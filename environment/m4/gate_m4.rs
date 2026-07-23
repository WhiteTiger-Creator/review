use crate::support::shape_u5::{CapView, StageHeap};

pub fn scale_span_b(heap: &StageHeap, gen: u64) -> CapView {
    let mut ceiling = 0.0_f64;
    let mut span = 0.0_f64;
    if let Some(slot) = heap.slots.first() {
        if slot.era == gen {
            ceiling = slot.mass.max(0.0);
            span = ceiling;
        }
    }
    CapView {
        ceiling,
        span,
        era: gen,
    }
}
