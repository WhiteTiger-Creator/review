use crate::support::shape_u5::{CapView, StageHeap};

fn live_mass(slot_mass: f64) -> f64 {
    if slot_mass.is_finite() {
        slot_mass.max(0.0)
    } else {
        0.0
    }
}

/// Draw ceiling/span over every slot whose era matches the live generation.
pub fn scale_span_b(heap: &StageHeap, gen: u64) -> CapView {
    let mut ceiling = 0.0_f64;
    let mut span = 0.0_f64;
    let mut seen = 0usize;
    for slot in &heap.slots {
        if slot.era != gen {
            continue;
        }
        let m = live_mass(slot.mass);
        span += m;
        if m > ceiling {
            ceiling = m;
        }
        seen = seen.saturating_add(1);
    }
    if seen == 0 {
        // Fall back to full heap when no era-tagged rows are present yet.
        for slot in &heap.slots {
            let m = live_mass(slot.mass);
            span += m;
            if m > ceiling {
                ceiling = m;
            }
        }
    }
    CapView {
        ceiling,
        span,
        era: gen,
    }
}
