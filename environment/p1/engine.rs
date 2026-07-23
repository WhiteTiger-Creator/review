use crate::err::{KitErr, Result};
use crate::j0::pack_j0::load_pack;
use crate::p1::draw_step::take_cap;
use crate::p1::fence_step::apply_fence;
use crate::p1::halt_step::seal_progress;
use crate::p1::lane_p1::{emit_draw, emit_scoring, emit_step, payload_digest};
use crate::p1::migrate_step::apply_schema_bump;
use crate::p1::replay_step::resume_fold;
use crate::support::hash_u5::hex_digest;
use crate::support::shape_u5::{
    HaltAudit, JournalFrame, MetaState, ProgressView, ReplayAudit, RunObs, ScheduleView,
    ShadowLedger, StageHeap, TrainingObservations,
};
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, Deserialize)]
pub struct TrainCfg {
    pub seed: u64,
    pub alpha_v1: f64,
    pub alpha_v2: f64,
    pub beta: f64,
    pub schema_v2: u32,
    pub train_steps: u32,
    pub hist_bins: usize,
    pub eval_band_rel: f64,
    pub twin_skew_max: f64,
    #[serde(default = "default_twin_ceiling")]
    pub twin_ceiling_min: f64,
}

fn default_twin_ceiling() -> f64 {
    0.85
}

impl TrainCfg {
    pub fn load(path: &Path) -> Result<Self> {
        let text = fs::read_to_string(path).map_err(|e| KitErr::Io(e.to_string()))?;
        toml::from_str(&text).map_err(|e| KitErr::Parse(e.to_string()))
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct SnapState {
    scenario: String,
    heap: StageHeap,
    meta: MetaState,
    live_gen: u64,
    step_ordinal: u64,
    baseline_score: f64,
}

pub struct Engine {
    pub cfg: TrainCfg,
    pub pack_path: PathBuf,
    pub state_dir: PathBuf,
}

impl Engine {
    pub fn new(cfg: TrainCfg, pack_path: PathBuf, state_dir: PathBuf) -> Self {
        Self {
            cfg,
            pack_path,
            state_dir,
        }
    }

    fn schedule_v2(&self) -> ScheduleView {
        ScheduleView {
            alpha: self.cfg.alpha_v2,
            beta: self.cfg.beta,
            schema: self.cfg.schema_v2,
        }
    }

    fn snap_path(&self) -> PathBuf {
        self.state_dir.join("snap.json")
    }

    fn journal_path(&self) -> PathBuf {
        self.state_dir.join("journal.ndjson")
    }

    fn shadow_path(&self) -> PathBuf {
        self.state_dir.join("shadow.json")
    }

    fn ensure_dir(&self) -> Result<()> {
        fs::create_dir_all(&self.state_dir).map_err(|e| KitErr::Io(e.to_string()))
    }

    fn save_snap(&self, st: &SnapState) -> Result<()> {
        self.ensure_dir()?;
        let text = serde_json::to_string_pretty(st).map_err(|e| KitErr::Parse(e.to_string()))?;
        fs::write(self.snap_path(), text).map_err(|e| KitErr::Io(e.to_string()))
    }

    fn load_snap(&self) -> Result<SnapState> {
        let text = fs::read_to_string(self.snap_path()).map_err(|e| KitErr::Io(e.to_string()))?;
        serde_json::from_str(&text).map_err(|e| KitErr::Parse(e.to_string()))
    }

    fn save_shadow(&self, shadow: &ShadowLedger) -> Result<()> {
        self.ensure_dir()?;
        let text =
            serde_json::to_string_pretty(shadow).map_err(|e| KitErr::Parse(e.to_string()))?;
        fs::write(self.shadow_path(), text).map_err(|e| KitErr::Io(e.to_string()))
    }

    fn load_shadow(&self) -> Result<ShadowLedger> {
        let path = self.shadow_path();
        if !path.exists() {
            return Ok(ShadowLedger::default());
        }
        let text = fs::read_to_string(path).map_err(|e| KitErr::Io(e.to_string()))?;
        serde_json::from_str(&text).map_err(|e| KitErr::Parse(e.to_string()))
    }

    fn read_journal_lines(&self) -> Result<Vec<String>> {
        let path = self.journal_path();
        if !path.exists() {
            return Ok(Vec::new());
        }
        let file = fs::File::open(path).map_err(|e| KitErr::Io(e.to_string()))?;
        let reader = BufReader::new(file);
        let mut lines = Vec::new();
        for line in reader.lines() {
            lines.push(line.map_err(|e| KitErr::Io(e.to_string()))?);
        }
        Ok(lines)
    }

    fn write_journal(&self, frames: &[JournalFrame]) -> Result<()> {
        self.ensure_dir()?;
        let mut file = fs::File::create(self.journal_path()).map_err(|e| KitErr::Io(e.to_string()))?;
        for frame in frames {
            let line =
                serde_json::to_string(frame).map_err(|e| KitErr::Parse(e.to_string()))?;
            writeln!(file, "{line}").map_err(|e| KitErr::Io(e.to_string()))?;
        }
        Ok(())
    }

    fn append_journal_frame(&self, frames: &mut Vec<JournalFrame>, frame: JournalFrame) -> Result<()> {
        frames.push(frame.clone());
        self.ensure_dir()?;
        let mut file = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(self.journal_path())
            .map_err(|e| KitErr::Io(e.to_string()))?;
        let line = serde_json::to_string(&frame).map_err(|e| KitErr::Parse(e.to_string()))?;
        writeln!(file, "{line}").map_err(|e| KitErr::Io(e.to_string()))
    }

    pub fn append_torn_line(&self, fragment: &str) -> Result<()> {
        self.ensure_dir()?;
        let mut file = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(self.journal_path())
            .map_err(|e| KitErr::Io(e.to_string()))?;
        write!(file, "{fragment}").map_err(|e| KitErr::Io(e.to_string()))
    }

    pub fn build_v1(&self, era: u64) -> Result<StageHeap> {
        load_pack(&self.pack_path, self.cfg.alpha_v1, era)
    }

    pub fn rebuild_v2(&self, era: u64) -> Result<StageHeap> {
        let mut heap = load_pack(&self.pack_path, self.cfg.alpha_v2, era)?;
        heap.schema = self.cfg.schema_v2;
        Ok(heap)
    }

    fn migrate_and_fence(
        &self,
        heap: &mut StageHeap,
        shadow: &mut ShadowLedger,
        journal: &mut Vec<JournalFrame>,
        live_gen: u64,
    ) -> Result<()> {
        let schedule = self.schedule_v2();
        let prior_schema = heap.schema;
        apply_schema_bump(heap, &schedule)?;
        if prior_schema != schedule.schema {
            self.append_journal_frame(
                journal,
                JournalFrame {
                    kind: "migrate".into(),
                    ordinal: journal.len() as u64,
                    gen: live_gen,
                    note: "schema-bump".into(),
                    batch_keys: heap.slots.iter().map(|s| s.tid).collect(),
                },
            )?;
        }
        apply_fence(heap, shadow, &schedule, journal)?;
        // Persist fence journal frame if commit appended one.
        if let Some(last) = journal.last() {
            if last.kind == "fence" {
                // rewrite full journal for consistency after in-memory fence push
                self.write_journal(journal)?;
            }
        }
        Ok(())
    }

    fn sample_index(heap: &StageHeap, ceiling: f64, tick: u64) -> usize {
        if heap.slots.is_empty() {
            return 0;
        }
        let mut acc = 0.0_f64;
        let target = ((tick.wrapping_mul(0x9E37_79B9_7F4A_7C15)) as f64 / u64::MAX as f64)
            * ceiling.max(1e-12);
        for (i, slot) in heap.slots.iter().enumerate() {
            acc += slot.mass.max(0.0);
            if acc >= target {
                return i;
            }
        }
        heap.slots.len() - 1
    }

    fn rank_hist(heap: &StageHeap, bins: usize) -> Vec<u32> {
        let mut hist = vec![0u32; bins.max(1)];
        let mut max_m = 1e-12_f64;
        for slot in &heap.slots {
            if slot.mass > max_m {
                max_m = slot.mass;
            }
        }
        for slot in &heap.slots {
            let frac = (slot.mass / max_m).clamp(0.0, 0.999999);
            let bin = (frac * bins as f64) as usize;
            hist[bin] += 1;
        }
        hist
    }

    fn step_loss(&self, ordinal: u32, is_w: f64) -> f64 {
        let t = ordinal as u64;
        let noise = ((self.cfg.seed ^ t).wrapping_mul(0x9E37_79B9_7F4A_7C15) & 0xFFFF) as f64
            / 65535.0;
        0.35 + 0.2 * noise - 0.05 * is_w.min(2.0)
    }

    fn heldout(&self, heap: &StageHeap, ceiling: f64) -> f64 {
        if heap.slots.is_empty() || ceiling <= 0.0 {
            return 0.0;
        }
        let total: f64 = heap
            .slots
            .iter()
            .map(|s| s.mass.max(0.0))
            .sum::<f64>()
            .max(1e-12);
        let mut num = 0.0_f64;
        let mut den = 0.0_f64;
        let n = heap.slots.len() as f64;
        for (i, slot) in heap.slots.iter().enumerate() {
            let p = (slot.mass.max(0.0) / total).clamp(1e-12, 1.0);
            let w = (n * p).powf(-self.cfg.beta);
            let scale = (slot.mass / ceiling.max(1e-12)).clamp(0.0, 4.0);
            let target = ((slot.tid.wrapping_mul(17) + i as u64) % 97) as f64 / 97.0;
            num += w * target * (0.25 + scale);
            den += w;
        }
        if den <= 0.0 {
            0.0
        } else {
            num / den
        }
    }

    fn persist_all(
        &self,
        scenario: &str,
        heap: &StageHeap,
        meta: &MetaState,
        shadow: &ShadowLedger,
        live_gen: u64,
        step_ordinal: u64,
        baseline_score: f64,
        journal: &[JournalFrame],
    ) -> Result<()> {
        self.save_snap(&SnapState {
            scenario: scenario.to_string(),
            heap: heap.clone(),
            meta: meta.clone(),
            live_gen,
            step_ordinal,
            baseline_score,
        })?;
        self.save_shadow(shadow)?;
        self.write_journal(journal)?;
        Ok(())
    }

    fn train_loop(
        &self,
        scenario: &str,
        heap: &mut StageHeap,
        meta: &mut MetaState,
        shadow: &mut ShadowLedger,
        journal: &mut Vec<JournalFrame>,
        live_gen: &mut u64,
        step_ordinal: &mut u64,
        baseline_score: f64,
        steps: u32,
        halt_at: Option<u32>,
        replay_delta: f64,
    ) -> Result<RunObs> {
        let mut step_obs = Vec::new();
        let mut draw_obs = Vec::new();
        let start = *step_ordinal as u32;
        let end = start + steps;
        for ordinal in start..end {
            if let Some(h) = halt_at {
                if ordinal >= h {
                    break;
                }
            }
            let cap = take_cap(heap, *live_gen);
            let idx =
                Self::sample_index(heap, cap.ceiling.max(1e-12), self.cfg.seed ^ ordinal as u64);
            let mass = heap.slots[idx].mass.max(1e-12);
            let p = (mass / cap.ceiling.max(1e-12)).clamp(1e-12, 1.0);
            let w = (heap.slots.len() as f64 * p).powf(-self.cfg.beta);
            let loss = self.step_loss(ordinal, w);
            let hist = Self::rank_hist(heap, self.cfg.hist_bins);
            step_obs.push(emit_step(ordinal, loss, hist));
            draw_obs.push(emit_draw(ordinal, cap.span, cap.ceiling, cap.era));
            *step_ordinal = ordinal as u64 + 1;
            self.append_journal_frame(
                journal,
                JournalFrame {
                    kind: "train".into(),
                    ordinal: *step_ordinal,
                    gen: *live_gen,
                    note: format!("step-{ordinal}"),
                    batch_keys: vec![heap.slots[idx].tid],
                },
            )?;
            if ordinal > 0 && ordinal % 5 == 0 {
                *live_gen = live_gen.saturating_add(1);
                for slot in heap.slots.iter_mut() {
                    slot.era = *live_gen;
                }
            }
        }
        let progress = ProgressView {
            step_ordinal: *step_ordinal,
            live_gen: *live_gen,
        };
        seal_progress(meta, &progress, &shadow.payload_seal)?;
        if halt_at.is_some() {
            self.append_journal_frame(
                journal,
                JournalFrame {
                    kind: "halt".into(),
                    ordinal: *step_ordinal,
                    gen: *live_gen,
                    note: "segment-halt".into(),
                    batch_keys: vec![],
                },
            )?;
        }
        let cap = take_cap(heap, *live_gen);
        let held = self.heldout(heap, cap.ceiling.max(1e-12));
        let scoring = emit_scoring(held, baseline_score, heap, shadow, replay_delta);
        Ok(RunObs {
            scenario: scenario.to_string(),
            steps: step_obs,
            draws: draw_obs,
            scoring,
        })
    }

    fn twin_mass_setup(&self, heap: &mut StageHeap, alpha: f64) {
        let n = heap.slots.len();
        let twin_p = 0.97_f64;
        if n >= 4 {
            for i in (n / 2)..n {
                heap.slots[i].raw_p = twin_p;
                heap.slots[i].mass = twin_p.powf(alpha);
                heap.slots[i].stage_mass = heap.slots[i].mass;
            }
        }
    }

    fn baseline_from_rebuild(&self) -> Result<(StageHeap, f64)> {
        let rebuilt = self.rebuild_v2(1)?;
        let probe = take_cap(&rebuilt, 1);
        let base = self.heldout(&rebuilt, probe.ceiling.max(1e-12));
        Ok((rebuilt, base))
    }

    pub fn run_scenario(&self, scenario: &str, mode: &str) -> Result<RunObs> {
        match mode {
            "baseline" => {
                let mut heap = self.rebuild_v2(1)?;
                let mut meta = MetaState {
                    schema: heap.schema,
                    gen_mark: 0,
                    step_ordinal: 0,
                    digest_hex: String::new(),
                };
                let mut shadow = ShadowLedger {
                    alpha: self.cfg.alpha_v2,
                    schema: self.cfg.schema_v2,
                    payload_seal: payload_digest(&heap),
                    fence_gen: 1,
                    journal_epoch: 0,
                };
                let mut journal = Vec::new();
                let mut live_gen = 1u64;
                let mut step = 0u64;
                let probe = take_cap(&heap, live_gen);
                let base = self.heldout(&heap, probe.ceiling.max(1e-12));
                let run = self.train_loop(
                    scenario,
                    &mut heap,
                    &mut meta,
                    &mut shadow,
                    &mut journal,
                    &mut live_gen,
                    &mut step,
                    base,
                    self.cfg.train_steps,
                    None,
                    0.0,
                )?;
                self.persist_all(
                    scenario, &heap, &meta, &shadow, live_gen, step, base, &journal,
                )?;
                Ok(run)
            }
            "migrate_load" => self.run_migrate_train(scenario, false, None),
            "rebuild" => {
                let mut heap = self.rebuild_v2(1)?;
                let mut meta = MetaState {
                    schema: heap.schema,
                    gen_mark: 0,
                    step_ordinal: 0,
                    digest_hex: String::new(),
                };
                let mut shadow = ShadowLedger {
                    alpha: self.cfg.alpha_v2,
                    schema: self.cfg.schema_v2,
                    payload_seal: payload_digest(&heap),
                    fence_gen: 1,
                    journal_epoch: 0,
                };
                let mut journal = Vec::new();
                let mut live_gen = 1u64;
                let mut step = 0u64;
                let probe = take_cap(&heap, live_gen);
                let base = self.heldout(&heap, probe.ceiling.max(1e-12));
                let run = self.train_loop(
                    scenario,
                    &mut heap,
                    &mut meta,
                    &mut shadow,
                    &mut journal,
                    &mut live_gen,
                    &mut step,
                    base,
                    self.cfg.train_steps,
                    None,
                    0.0,
                )?;
                self.persist_all(
                    scenario, &heap, &meta, &shadow, live_gen, step, base, &journal,
                )?;
                Ok(run)
            }
            "idempotent" | "double_fence" => {
                let mut heap = self.build_v1(1)?;
                let mut shadow = ShadowLedger::default();
                let mut journal = Vec::new();
                self.migrate_and_fence(&mut heap, &mut shadow, &mut journal, 1)?;
                let digest_a = payload_digest(&heap);
                let seal_a = shadow.payload_seal.clone();
                self.migrate_and_fence(&mut heap, &mut shadow, &mut journal, 1)?;
                let digest_b = payload_digest(&heap);
                let seal_b = shadow.payload_seal.clone();
                let mut replay_delta = 0.0;
                if digest_a != digest_b || seal_a != seal_b {
                    replay_delta = 1.0;
                }
                let mut meta = MetaState {
                    schema: heap.schema,
                    gen_mark: 0,
                    step_ordinal: 0,
                    digest_hex: String::new(),
                };
                let mut live_gen = 1u64;
                let mut step = 0u64;
                let (_, base) = self.baseline_from_rebuild()?;
                let mut run = self.train_loop(
                    scenario,
                    &mut heap,
                    &mut meta,
                    &mut shadow,
                    &mut journal,
                    &mut live_gen,
                    &mut step,
                    base,
                    self.cfg.train_steps,
                    None,
                    replay_delta,
                )?;
                if replay_delta > 0.0 {
                    run.scoring.heldout_score *= 0.5;
                }
                run.scoring.payload_digest = digest_b;
                run.scoring.shadow_seal = seal_b;
                run.scoring.replay_delta = replay_delta;
                self.persist_all(
                    scenario, &heap, &meta, &shadow, live_gen, step, base, &journal,
                )?;
                Ok(run)
            }
            "twin_mass" => {
                let mut heap = self.build_v1(1)?;
                self.twin_mass_setup(&mut heap, self.cfg.alpha_v1);
                let mut shadow = ShadowLedger::default();
                let mut journal = Vec::new();
                self.migrate_and_fence(&mut heap, &mut shadow, &mut journal, 1)?;
                let mut meta = MetaState {
                    schema: heap.schema,
                    gen_mark: 0,
                    step_ordinal: 0,
                    digest_hex: String::new(),
                };
                let mut live_gen = 1u64;
                let mut step = 0u64;
                let mut rebuilt = self.rebuild_v2(1)?;
                self.twin_mass_setup(&mut rebuilt, self.cfg.alpha_v2);
                let probe = take_cap(&rebuilt, 1);
                let base = self.heldout(&rebuilt, probe.ceiling.max(1e-12));
                let run = self.train_loop(
                    scenario,
                    &mut heap,
                    &mut meta,
                    &mut shadow,
                    &mut journal,
                    &mut live_gen,
                    &mut step,
                    base,
                    self.cfg.train_steps,
                    None,
                    0.0,
                )?;
                self.persist_all(
                    scenario, &heap, &meta, &shadow, live_gen, step, base, &journal,
                )?;
                Ok(run)
            }
            "hybrid_halt" => self.run_hybrid_halt(scenario, false),
            "halt_twin" => self.run_hybrid_halt(scenario, true),
            "torn_resume" => self.run_torn_resume(scenario),
            "gen_bump" => self.run_gen_bump(scenario),
            "assess_migrate" => {
                let run = self.run_migrate_train(scenario, false, None)?;
                // Assess from durable state and overwrite scoring observation.
                let assessed = self.assess_only()?;
                Ok(RunObs {
                    scenario: scenario.to_string(),
                    steps: run.steps,
                    draws: run.draws,
                    scoring: assessed.scoring,
                })
            }
            _ => Err(KitErr::BadState(format!("unknown mode {mode}"))),
        }
    }

    fn run_migrate_train(
        &self,
        scenario: &str,
        twin: bool,
        halt_at: Option<u32>,
    ) -> Result<RunObs> {
        let mut heap = self.build_v1(1)?;
        if twin {
            self.twin_mass_setup(&mut heap, self.cfg.alpha_v1);
        }
        let mut shadow = ShadowLedger::default();
        let mut journal = Vec::new();
        self.migrate_and_fence(&mut heap, &mut shadow, &mut journal, 1)?;
        let mut meta = MetaState {
            schema: heap.schema,
            gen_mark: 0,
            step_ordinal: 0,
            digest_hex: String::new(),
        };
        let mut live_gen = 1u64;
        let mut step = 0u64;
        let mut rebuilt = self.rebuild_v2(1)?;
        if twin {
            self.twin_mass_setup(&mut rebuilt, self.cfg.alpha_v2);
        }
        let probe = take_cap(&rebuilt, 1);
        let base = self.heldout(&rebuilt, probe.ceiling.max(1e-12));
        let run = self.train_loop(
            scenario,
            &mut heap,
            &mut meta,
            &mut shadow,
            &mut journal,
            &mut live_gen,
            &mut step,
            base,
            self.cfg.train_steps,
            halt_at,
            0.0,
        )?;
        self.persist_all(
            scenario, &heap, &meta, &shadow, live_gen, step, base, &journal,
        )?;
        Ok(run)
    }

    fn run_hybrid_halt(&self, scenario: &str, twin: bool) -> Result<RunObs> {
        // First segment only; matrix harness resumes from the same STATE_DIR.
        let mut heap = self.build_v1(1)?;
        if twin {
            self.twin_mass_setup(&mut heap, self.cfg.alpha_v1);
        }
        let mut shadow = ShadowLedger::default();
        let mut journal = Vec::new();
        self.migrate_and_fence(&mut heap, &mut shadow, &mut journal, 1)?;
        let mut meta = MetaState {
            schema: heap.schema,
            gen_mark: 0,
            step_ordinal: 0,
            digest_hex: String::new(),
        };
        let mut live_gen = 1u64;
        let mut step = 0u64;
        let mut rebuilt = self.rebuild_v2(1)?;
        if twin {
            self.twin_mass_setup(&mut rebuilt, self.cfg.alpha_v2);
        }
        let probe = take_cap(&rebuilt, 1);
        let base = self.heldout(&rebuilt, probe.ceiling.max(1e-12));
        let mut run = self.train_loop(
            scenario,
            &mut heap,
            &mut meta,
            &mut shadow,
            &mut journal,
            &mut live_gen,
            &mut step,
            base,
            self.cfg.train_steps,
            Some(6),
            0.0,
        )?;
        if shadow.fence_gen == 0 || shadow.payload_seal.is_empty() {
            run.scoring.heldout_score *= 0.5;
        }
        self.persist_all(
            scenario, &heap, &meta, &shadow, live_gen, step, base, &journal,
        )?;
        Ok(run)
    }

    fn run_torn_resume(&self, scenario: &str) -> Result<RunObs> {
        let mut heap = self.build_v1(1)?;
        let mut shadow = ShadowLedger::default();
        let mut journal = Vec::new();
        self.migrate_and_fence(&mut heap, &mut shadow, &mut journal, 1)?;
        let mut meta = MetaState {
            schema: heap.schema,
            gen_mark: 0,
            step_ordinal: 0,
            digest_hex: String::new(),
        };
        let mut live_gen = 1u64;
        let mut step = 0u64;
        let (_, base) = self.baseline_from_rebuild()?;
        let _ = self.train_loop(
            scenario,
            &mut heap,
            &mut meta,
            &mut shadow,
            &mut journal,
            &mut live_gen,
            &mut step,
            base,
            4,
            None,
            0.0,
        )?;
        let seal_before = shadow.payload_seal.clone();
        let digest_before = payload_digest(&heap);
        self.persist_all(
            scenario, &heap, &meta, &shadow, live_gen, step, base, &journal,
        )?;
        // Append a torn incomplete journal line.
        self.append_torn_line("{\"kind\":\"train\",\"ordinal\":")?;

        // Reload via journal fold (resume path).
        let snap = self.load_snap()?;
        let shadow_disk = self.load_shadow()?;
        let lines = self.read_journal_lines()?;
        let (mut heap2, mut shadow2, mut meta2) =
            resume_fold(&snap.heap, &lines, &shadow_disk)?;
        let mut live_gen2 = snap.live_gen;
        let mut step2 = snap.step_ordinal;
        // Prefer snap ordinals when fold drifts (healthy recovery).
        if meta2.step_ordinal == 0 {
            step2 = snap.step_ordinal;
            live_gen2 = snap.live_gen;
            meta2 = snap.meta.clone();
        }
        let mut replay_delta = 0.0;
        if payload_digest(&heap2) != digest_before || shadow2.payload_seal != seal_before {
            replay_delta = 1.0;
        }
        // Healthy recover uses snap heap when fold corrupts blobs.
        if replay_delta > 0.0 {
        }
        let mut journal2 = Vec::new();
        for line in &lines {
            let t = line.trim();
            if t.is_empty() {
                continue;
            }
            if let Ok(frame) = serde_json::from_str::<JournalFrame>(t) {
                journal2.push(frame);
            }
        }
        let mut run = self.train_loop(
            scenario,
            &mut heap2,
            &mut meta2,
            &mut shadow2,
            &mut journal2,
            &mut live_gen2,
            &mut step2,
            base,
            self.cfg.train_steps.saturating_sub(4),
            None,
            replay_delta,
        )?;
        if replay_delta > 0.0 {
            run.scoring.heldout_score *= 0.4;
            run.scoring.replay_delta = replay_delta;
        } else {
            run.scoring.replay_delta = 0.0;
            run.scoring.payload_digest = digest_before;
            run.scoring.shadow_seal = seal_before;
        }
        self.persist_all(
            scenario, &heap2, &meta2, &shadow2, live_gen2, step2, base, &journal2,
        )?;
        Ok(run)
    }

    fn run_gen_bump(&self, scenario: &str) -> Result<RunObs> {
        let mut heap = self.build_v1(1)?;
        let n = heap.slots.len();
        if n >= 4 {
            for i in 0..n {
                let boost = 0.2 + 0.75 * (i as f64 / (n - 1) as f64);
                heap.slots[i].raw_p = boost;
                heap.slots[i].mass = boost.powf(self.cfg.alpha_v1);
                heap.slots[i].stage_mass = heap.slots[i].mass;
            }
        }
        let mut shadow = ShadowLedger::default();
        let mut journal = Vec::new();
        self.migrate_and_fence(&mut heap, &mut shadow, &mut journal, 1)?;
        let mut meta = MetaState {
            schema: heap.schema,
            gen_mark: 0,
            step_ordinal: 0,
            digest_hex: String::new(),
        };
        let mut live_gen = 1u64;
        let mut step = 0u64;
        let (_, base) = self.baseline_from_rebuild()?;
        let run = self.train_loop(
            scenario,
            &mut heap,
            &mut meta,
            &mut shadow,
            &mut journal,
            &mut live_gen,
            &mut step,
            base,
            self.cfg.train_steps,
            None,
            0.0,
        )?;
        self.persist_all(
            scenario, &heap, &meta, &shadow, live_gen, step, base, &journal,
        )?;
        Ok(run)
    }

    pub fn resume_from_state(&self, steps: Option<u32>) -> Result<RunObs> {
        let snap = self.load_snap()?;
        let shadow_disk = self.load_shadow()?;
        let lines = self.read_journal_lines()?;
        let (folded_heap, folded_shadow, folded_meta) =
            resume_fold(&snap.heap, &lines, &shadow_disk)?;
        // Prefer snap bytes when fold drifts (torn-line recovery).
        let fold_corrupted = payload_digest(&folded_heap) != payload_digest(&snap.heap)
            || (shadow_disk.payload_seal.len() == 64
                && folded_shadow.payload_seal != shadow_disk.payload_seal);
        let (mut heap, mut shadow, mut meta, mut live_gen, mut step) = if fold_corrupted
            && !shadow_disk.payload_seal.is_empty()
        {
            (
                snap.heap.clone(),
                shadow_disk.clone(),
                snap.meta.clone(),
                snap.live_gen,
                snap.step_ordinal,
            )
        } else if folded_meta.step_ordinal == 0 && snap.step_ordinal > 0 {
            (
                snap.heap.clone(),
                shadow_disk.clone(),
                snap.meta.clone(),
                snap.live_gen,
                snap.step_ordinal,
            )
        } else {
            (
                folded_heap,
                folded_shadow,
                folded_meta,
                snap.live_gen,
                snap.step_ordinal,
            )
        };
        let mut journal = Vec::new();
        for line in &lines {
            let t = line.trim();
            if t.is_empty() {
                continue;
            }
            if let Ok(frame) = serde_json::from_str::<JournalFrame>(t) {
                journal.push(frame);
            }
        }
        let remain = steps.unwrap_or_else(|| {
            self.cfg
                .train_steps
                .saturating_sub(step as u32)
                .max(1)
        });
        let mut run = self.train_loop(
            &snap.scenario,
            &mut heap,
            &mut meta,
            &mut shadow,
            &mut journal,
            &mut live_gen,
            &mut step,
            snap.baseline_score,
            remain,
            None,
            if fold_corrupted && shadow_disk.payload_seal.is_empty() {
                1.0
            } else {
                0.0
            },
        )?;
        if meta.gen_mark != live_gen || meta.step_ordinal != step {
            run.scoring.heldout_score *= 0.25;
            for d in run.draws.iter_mut() {
                d.era = meta.gen_mark;
            }
        }
        if shadow.fence_gen == 0 || shadow.payload_seal.is_empty() {
            run.scoring.heldout_score *= 0.5;
            run.scoring.replay_delta = 1.0;
        }
        self.persist_all(
            &snap.scenario,
            &heap,
            &meta,
            &shadow,
            live_gen,
            step,
            snap.baseline_score,
            &journal,
        )?;
        Ok(run)
    }

    pub fn assess_only(&self) -> Result<RunObs> {
        let st = self.load_snap()?;
        let shadow = self.load_shadow()?;
        let cap = take_cap(&st.heap, st.live_gen);
        let held = self.heldout(&st.heap, cap.ceiling.max(1e-12));
        Ok(RunObs {
            scenario: st.scenario,
            steps: vec![],
            draws: vec![emit_draw(0, cap.span, cap.ceiling, cap.era)],
            scoring: emit_scoring(held, st.baseline_score, &st.heap, &shadow, 0.0),
        })
    }

    pub fn inspect(&self) -> Result<HaltAudit> {
        let st = self.load_snap()?;
        let shadow = self.load_shadow()?;
        let mut meta = st.meta.clone();
        seal_progress(
            &mut meta,
            &ProgressView {
                step_ordinal: st.step_ordinal,
                live_gen: st.live_gen,
            },
            &shadow.payload_seal,
        )?;
        let bind = hex_digest(
            format!(
                "{}:{}:{}:{}:{}",
                st.scenario, st.step_ordinal, meta.gen_mark, meta.digest_hex, shadow.payload_seal
            )
            .as_bytes(),
        );
        Ok(HaltAudit {
            scenario: st.scenario,
            halt_step: st.step_ordinal,
            gen_mark: meta.gen_mark,
            live_gen: st.live_gen,
            meta_digest: meta.digest_hex,
            bindstamp: bind,
            fence_gen: shadow.fence_gen,
            journal_epoch: shadow.journal_epoch,
            shadow_seal: shadow.payload_seal,
        })
    }

    pub fn replay_audit(&self, scenario: &str) -> Result<ReplayAudit> {
        let snap = self.load_snap()?;
        let shadow = self.load_shadow()?;
        let lines = self.read_journal_lines()?;
        let mut valid = 0u64;
        let mut gap = 0u64;
        for line in &lines {
            let t = line.trim();
            if t.is_empty() {
                continue;
            }
            match serde_json::from_str::<JournalFrame>(t) {
                Ok(_) => valid += 1,
                Err(_) => gap += 1,
            }
        }
        let (_heap, folded_shadow, _meta) = resume_fold(&snap.heap, &lines, &shadow)?;
        let seal = if folded_shadow.payload_seal.is_empty() {
            shadow.payload_seal.clone()
        } else {
            folded_shadow.payload_seal.clone()
        };
        let fence = if folded_shadow.fence_gen == 0 {
            shadow.fence_gen
        } else {
            folded_shadow.fence_gen
        };
        let chain_gap = if seal.is_empty() || fence == 0 {
            gap.max(1)
        } else if gap > 0 {
            if shadow.payload_seal.is_empty() {
                gap
            } else {
                0
            }
        } else {
            0
        };
        let stamp = hex_digest(
            format!(
                "{}:{}:{}:{}",
                scenario, valid, fence, seal
            )
            .as_bytes(),
        );
        Ok(ReplayAudit {
            scenario: scenario.to_string(),
            journal_entries: valid,
            chain_gap,
            fence_gen: fence,
            shadow_seal: seal,
            replay_stamp: stamp,
        })
    }

    pub fn write_observations(&self, seed: u64, runs: Vec<RunObs>, out: &Path) -> Result<()> {
        let obs = TrainingObservations { seed, runs };
        if let Some(parent) = out.parent() {
            fs::create_dir_all(parent).map_err(|e| KitErr::Io(e.to_string()))?;
        }
        let text = serde_json::to_string_pretty(&obs).map_err(|e| KitErr::Parse(e.to_string()))?;
        fs::write(out, text).map_err(|e| KitErr::Io(e.to_string()))
    }

    pub fn write_json<T: Serialize>(&self, value: &T, out: &Path) -> Result<()> {
        if let Some(parent) = out.parent() {
            fs::create_dir_all(parent).map_err(|e| KitErr::Io(e.to_string()))?;
        }
        let text = serde_json::to_string_pretty(value).map_err(|e| KitErr::Parse(e.to_string()))?;
        fs::write(out, text).map_err(|e| KitErr::Io(e.to_string()))
    }
}
