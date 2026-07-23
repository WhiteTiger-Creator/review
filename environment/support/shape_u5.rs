use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SlotRec {
    pub tid: u64,
    pub mass: f64,
    pub stage_mass: f64,
    pub raw_p: f64,
    pub blob: Vec<u8>,
    pub era: u64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StageHeap {
    pub slots: Vec<SlotRec>,
    pub schema: u32,
}

#[derive(Clone, Debug)]
pub struct ScheduleView {
    pub alpha: f64,
    pub beta: f64,
    pub schema: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct CapView {
    pub ceiling: f64,
    pub span: f64,
    pub era: u64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MetaState {
    pub schema: u32,
    pub gen_mark: u64,
    pub step_ordinal: u64,
    pub digest_hex: String,
}

#[derive(Clone, Debug)]
pub struct ProgressView {
    pub step_ordinal: u64,
    pub live_gen: u64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ShadowLedger {
    pub alpha: f64,
    pub schema: u32,
    pub payload_seal: String,
    pub fence_gen: u64,
    pub journal_epoch: u64,
}

impl Default for ShadowLedger {
    fn default() -> Self {
        Self {
            alpha: 0.0,
            schema: 0,
            payload_seal: String::new(),
            fence_gen: 0,
            journal_epoch: 0,
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct JournalFrame {
    pub kind: String,
    pub ordinal: u64,
    pub gen: u64,
    pub note: String,
    #[serde(default)]
    pub batch_keys: Vec<u64>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct StepObs {
    pub ordinal: u32,
    pub loss: f64,
    pub rank_histogram: Vec<u32>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DrawObs {
    pub ordinal: u32,
    pub span: f64,
    pub ceiling: f64,
    pub era: u64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ScoringObs {
    pub heldout_score: f64,
    pub baseline_score: f64,
    pub payload_digest: String,
    pub shadow_seal: String,
    pub fence_gen: u64,
    pub journal_epoch: u64,
    pub replay_delta: f64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RunObs {
    pub scenario: String,
    pub steps: Vec<StepObs>,
    pub draws: Vec<DrawObs>,
    pub scoring: ScoringObs,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct TrainingObservations {
    pub seed: u64,
    pub runs: Vec<RunObs>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HaltAudit {
    pub scenario: String,
    pub halt_step: u64,
    pub gen_mark: u64,
    pub live_gen: u64,
    pub meta_digest: String,
    pub bindstamp: String,
    pub fence_gen: u64,
    pub journal_epoch: u64,
    pub shadow_seal: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ReplayAudit {
    pub scenario: String,
    pub journal_entries: u64,
    pub chain_gap: u64,
    pub fence_gen: u64,
    pub shadow_seal: String,
    pub replay_stamp: String,
}
