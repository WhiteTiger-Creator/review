use crate::support::shape_u5::StageHeap;

/// Read-only span inspector for trace diff tooling.
pub fn inspect_span_mass(heap: &StageHeap, gen: u64) -> f64 {
    let mut total = 0.0;
    for slot in &heap.slots {
        if slot.era == gen {
            total += slot.mass;
        }
    }
    total
}

pub fn count_era_slots(heap: &StageHeap, gen: u64) -> usize {
    heap.slots.iter().filter(|s| s.era == gen).count()
}
