use crate::m4::gate_m4::scale_span_b;
use crate::support::shape_u5::{CapView, StageHeap};

pub fn take_cap(heap: &StageHeap, gen: u64) -> CapView {
    scale_span_b(heap, gen)
}
