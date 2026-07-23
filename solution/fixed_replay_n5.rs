use crate::err::Result;
use crate::support::hash_u5::{hex_digest, join_blobs};
use crate::support::shape_u5::{
    JournalFrame, MetaState, ShadowLedger, StageHeap,
};

fn promote_stage(heap: &mut StageHeap) {
    for slot in heap.slots.iter_mut() {
        let staged = if slot.stage_mass.is_finite() {
            slot.stage_mass.max(0.0)
        } else {
            0.0
        };
        slot.mass = staged;
    }
}

fn seal_payload(heap: &StageHeap) -> String {
    let blobs: Vec<Vec<u8>> = heap.slots.iter().map(|s| s.blob.clone()).collect();
    hex_digest(&join_blobs(&blobs))
}

fn drop_torn_tail(lines: &[String]) -> Vec<&str> {
    let mut out: Vec<&str> = lines
        .iter()
        .map(|l| l.trim())
        .filter(|l| !l.is_empty())
        .collect();
    if let Some(last) = out.last() {
        if serde_json::from_str::<JournalFrame>(last).is_err() {
            out.pop();
        }
    }
    out
}

/// Replay journal frames onto a snap heap without re-applying migrate weaves.
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

    let lines = drop_torn_tail(journal_lines);
    let mut saw_fence = false;
    for line in lines {
        let frame: JournalFrame = match serde_json::from_str(line) {
            Ok(f) => f,
            Err(_) => continue,
        };
        match frame.kind.as_str() {
            "migrate" => {
                // Schema bump is recorded in the frame trail; live mass stays snap-backed
                // until a fence promotes staging. Do not re-weave here.
                meta.schema = heap.schema;
            }
            "fence" => {
                promote_stage(&mut heap);
                saw_fence = true;
                out_shadow.fence_gen = frame.gen.max(out_shadow.fence_gen).max(1);
                out_shadow.journal_epoch = frame.ordinal.max(out_shadow.journal_epoch);
                if out_shadow.schema == 0 {
                    out_shadow.schema = heap.schema;
                }
                if out_shadow.alpha <= 0.0 {
                    out_shadow.alpha = shadow.alpha.max(0.4);
                }
                out_shadow.payload_seal = seal_payload(&heap);
            }
            "train" | "halt" => {
                meta.step_ordinal = frame.ordinal.max(meta.step_ordinal);
                meta.gen_mark = frame.gen.max(meta.gen_mark);
            }
            _ => {}
        }
    }

    if !saw_fence && out_shadow.payload_seal.is_empty() && !shadow.payload_seal.is_empty() {
        out_shadow = shadow.clone();
        heap = snap_heap.clone();
    }
    if meta.step_ordinal == 0 {
        meta.digest_hex = shadow.payload_seal.clone();
    } else {
        meta.digest_hex = out_shadow.payload_seal.clone();
    }

    Ok((heap, out_shadow, meta))
}
