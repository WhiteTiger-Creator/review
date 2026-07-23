use crate::support::hash_u5::{hex_digest, join_blobs};
use crate::support::shape_u5::{DrawObs, ScoringObs, ShadowLedger, StageHeap, StepObs};

pub fn emit_step(ordinal: u32, loss: f64, hist: Vec<u32>) -> StepObs {
    StepObs {
        ordinal,
        loss,
        rank_histogram: hist,
    }
}

pub fn emit_draw(ordinal: u32, span: f64, ceiling: f64, era: u64) -> DrawObs {
    DrawObs {
        ordinal,
        span,
        ceiling,
        era,
    }
}

pub fn payload_digest(heap: &StageHeap) -> String {
    let blobs: Vec<Vec<u8>> = heap.slots.iter().map(|s| s.blob.clone()).collect();
    hex_digest(&join_blobs(&blobs))
}

pub fn emit_scoring(
    heldout: f64,
    base: f64,
    heap: &StageHeap,
    shadow: &ShadowLedger,
    replay_delta: f64,
) -> ScoringObs {
    ScoringObs {
        heldout_score: heldout,
        baseline_score: base,
        payload_digest: payload_digest(heap),
        shadow_seal: shadow.payload_seal.clone(),
        fence_gen: shadow.fence_gen,
        journal_epoch: shadow.journal_epoch,
        replay_delta,
    }
}
