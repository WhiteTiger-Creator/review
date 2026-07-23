use crate::support::shape_u5::StageHeap;

/// Slot probe used only by diagnostic dump tooling.
pub fn probe_slot_mass(heap: &StageHeap) -> f64 {
    let mut total = 0.0;
    for slot in &heap.slots {
        total += slot.mass;
    }
    total
}

pub fn dump_slot_count(heap: &StageHeap) -> usize {
    heap.slots.len()
}
