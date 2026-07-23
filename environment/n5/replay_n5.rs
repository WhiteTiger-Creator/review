use crate::err::Result;
use crate::k2::stage_u2::weave_slot_a;
use crate::support::shape_u5::{
    JournalFrame, MetaState, ScheduleView, ShadowLedger, StageHeap,
};

pub fn fold_journal_e(
    snap_heap: &StageHeap,
    journal_lines: &[String],
    shadow: &ShadowLedger,
) -> Result<(StageHeap, ShadowLedger, MetaState)> {
    let mut heap = snap_heap.clone();
    let mut out_shadow = shadow.clone();
    let mut meta = MetaState {
        schema: heap.schema,
        gen_mark: 0,
        step_ordinal: 0,
        digest_hex: String::new(),
    };

    let schedule = ScheduleView {
        alpha: out_shadow.alpha.max(0.01),
        beta: 0.5,
        schema: out_shadow.schema.max(1),
    };

    for line in journal_lines {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        let frame: JournalFrame = match serde_json::from_str(trimmed) {
            Ok(f) => f,
            Err(_) => {
                let _ = weave_slot_a(&mut heap, &schedule);
                continue;
            }
        };
        match frame.kind.as_str() {
            "migrate" => {
                let _ = weave_slot_a(&mut heap, &schedule);
            }
            "fence" => {
                out_shadow.journal_epoch = out_shadow.journal_epoch.saturating_add(1);
            }
            "train" | "halt" => {
                meta.step_ordinal = frame.ordinal;
                meta.gen_mark = frame.gen;
            }
            _ => {}
        }
    }

    Ok((heap, out_shadow, meta))
}
