import { stageCalendar } from "../a7/stage";
import { stagePrior } from "../b3/stage";
import { stageGauge } from "../c5/stage";
import { stageBrief } from "../d9/stage";
import { SlotRow } from "../a7/w9/slot_meta";
import { existsPath, joinPath, readJson, writeText } from "../lib/io";
import { fx6, makeReproHex } from "../lib/hash";
import { qBind, qPackDigest, qSeal } from "../r4";
import { qScan } from "../r4/q_scan";
import { loadOrCompute } from "../x2";
import { emitTape, tryReplay } from "../j6";

type Manifest = {
  ckpt: string;
  seed: number;
  nSalt: number;
  kParts: number;
  xSlot: number;
  span: number;
};

type ZRows = {
  logits: number[];
  covariates: number[];
  home_logits: number[];
  shift_logits: number[];
};

type HistRow = { bin: number; vals: number[] };

type RunCore = {
  leakProbe: number;
  trainEnd: number;
  evalStart: number;
  priorDelta: number;
  priorDeltaResidual: number;
  accHome: number;
  accShift: number;
  accGap: number;
};

function parseArgs(argv: string[]): { pack: string; out: string } {
  let pack = "";
  let out = "";
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === "--pack") pack = argv[++i] || "";
    else if (argv[i] === "--out") out = argv[++i] || "";
  }
  if (!pack || !out) {
    throw new Error("usage: main.js --pack <path> --out <path>");
  }
  return { pack, out };
}

function manifestDigest(m: Manifest): string {
  return qPackDigest([m.ckpt, m.seed, m.nSalt, m.kParts, m.xSlot, m.span]);
}

function loadRows(pack: string): {
  manifest: Manifest;
  slots: SlotRow[];
  hist: HistRow[];
  z: ZRows;
} {
  const manifest = readJson<Manifest>(joinPath(pack, "manifest.json"));
  const slots = readJson<SlotRow[]>(joinPath(pack, "slot_rows.json"));
  const hist = readJson<HistRow[]>(joinPath(pack, "hist_rows.json"));
  const z = readJson<ZRows>(joinPath(pack, "z_rows.json"));
  return { manifest, slots, hist, z };
}

function resolveHeld(pack: string): {
  manifest: Manifest;
  slots: SlotRow[];
  hist: HistRow[];
  z: ZRows;
} | null {
  const heldDir = joinPath(pack, "held_out");
  if (!existsPath(joinPath(heldDir, "manifest.json"))) return null;
  const manifest = readJson<Manifest>(joinPath(heldDir, "manifest.json"));
  const slots = existsPath(joinPath(heldDir, "slot_rows.json"))
    ? readJson<SlotRow[]>(joinPath(heldDir, "slot_rows.json"))
    : readJson<SlotRow[]>(joinPath(pack, "slot_rows.json"));
  const hist = existsPath(joinPath(heldDir, "hist_rows.json"))
    ? readJson<HistRow[]>(joinPath(heldDir, "hist_rows.json"))
    : readJson<HistRow[]>(joinPath(pack, "hist_rows.json"));
  const z = existsPath(joinPath(heldDir, "z_rows.json"))
    ? readJson<ZRows>(joinPath(heldDir, "z_rows.json"))
    : readJson<ZRows>(joinPath(pack, "z_rows.json"));
  return { manifest, slots, hist, z };
}

function runOne(
  manifest: Manifest,
  slots: SlotRow[],
  hist: HistRow[],
  z: ZRows
): RunCore {
  void hist;
  (global as any).currentSlots = slots;
  const wind = stageCalendar(manifest.xSlot, slots, manifest.span);
  const prio = stagePrior(z.logits, z.covariates, manifest.kParts);
  const gauge = stageGauge(z.logits, z.home_logits, z.shift_logits, manifest.nSalt);
  return {
    leakProbe: wind.leakProbe,
    trainEnd: wind.trainEnd,
    evalStart: wind.evalStart,
    priorDelta: prio.priorDelta,
    priorDeltaResidual: prio.priorDeltaResidual,
    accHome: gauge.accHome,
    accShift: gauge.accShift,
    accGap: gauge.accGap,
  };
}

function runOneMemo(digest: string, manifest: Manifest, slots: SlotRow[], hist: HistRow[], z: ZRows): RunCore {
  return loadOrCompute(digest, () => runOne(manifest, slots, hist, z)) as RunCore;
}

function main(): void {
  const { pack, out } = parseArgs(process.argv.slice(2));
  const primary = loadRows(pack);
  const primaryDigest = manifestDigest(primary.manifest);
  const core = runOneMemo(
    primaryDigest,
    primary.manifest,
    primary.slots,
    primary.hist,
    primary.z
  );

  const heldPack = resolveHeld(pack);
  let held = {
    prior_delta: core.priorDelta,
    prior_delta_residual: core.priorDeltaResidual,
    temporal_leak_probe: core.leakProbe,
  };
  if (heldPack) {
    const heldDigest = manifestDigest(heldPack.manifest);
    const h = runOneMemo(
      heldDigest,
      heldPack.manifest,
      heldPack.slots,
      heldPack.hist,
      heldPack.z
    );
    held = {
      prior_delta: h.priorDelta,
      prior_delta_residual: h.priorDeltaResidual,
      temporal_leak_probe: h.leakProbe,
    };
  }

  const seed = primary.manifest.seed;
  const nSalt = primary.manifest.nSalt;
  const pack_digest = primaryDigest;

  const seal_cal = qSeal("cal", [core.trainEnd, core.evalStart, core.leakProbe]);
  const seal_prio = qSeal("prio", [
    fx6(core.priorDelta),
    fx6(core.priorDeltaResidual),
  ]);
  const seal_gauge = qSeal("gauge", [
    fx6(core.accHome),
    fx6(core.accShift),
    fx6(core.accGap),
    nSalt,
  ]);

  const scoring_table = {
    temporal_leak_probe: core.leakProbe,
    train_end_slot: core.trainEnd,
    eval_start_slot: core.evalStart,
    prior_delta: core.priorDelta,
    prior_delta_residual: core.priorDeltaResidual,
    acc_home: core.accHome,
    acc_shift: core.accShift,
    acc_gap: core.accGap,
  };

  const mIdx: Record<string, number> = { ...scoring_table };
  const brief = stageBrief(mIdx, 2);
  const seal_brief = qSeal("brief", [brief.length, Object.keys(mIdx).length]);

  const seals = [seal_cal, seal_prio, seal_gauge, seal_brief];
  void qScan(seals);
  const bound = qBind(pack_digest, seals);

  const repro = makeReproHex([
    seed,
    core.trainEnd,
    core.evalStart,
    core.leakProbe,
    fx6(core.priorDelta),
    fx6(core.priorDeltaResidual),
    fx6(core.accHome),
    fx6(core.accShift),
    fx6(core.accGap),
    nSalt,
    pack_digest,
    bound.chain,
  ]);

  const stage_seals = {
    cal: seal_cal,
    prio: seal_prio,
    gauge: seal_gauge,
    brief: seal_brief,
  };

  const payload = {
    seed,
    partition_policy: "strict_calendar_gap",
    temporal_leak_probe: core.leakProbe,
    train_end_slot: core.trainEnd,
    eval_start_slot: core.evalStart,
    prior_delta: core.priorDelta,
    prior_delta_residual: core.priorDeltaResidual,
    acc_home: core.accHome,
    acc_shift: core.accShift,
    acc_gap: core.accGap,
    checkpoint_stamp: primary.manifest.ckpt,
    pack_digest,
    ledger_chain: bound.chain,
    resume_stamp: bound.resume,
    stage_seals,
    repro_digest: repro,
    scoring_table,
    held_out: held,
    tape_seal_count: 4,
  };

  const tapePath = joinPath(out, "stage_tape.jsonl");
  const ledgerPath = joinPath(out, "desk_ledger.json");
  const checkpointDir = joinPath(out, "checkpoints");
  const checkpointPath = joinPath(checkpointDir, `${primary.manifest.ckpt}.json`);

  let ledgerCorrupt = false;
  let ledgerData: any = null;

  if (existsPath(ledgerPath)) {
    try {
      ledgerData = readJson<any>(ledgerPath);
      if (
        !ledgerData ||
        typeof ledgerData !== "object" ||
        !ledgerData.ledger_chain ||
        !ledgerData.resume_stamp
      ) {
        ledgerCorrupt = true;
      } else if (ledgerData.pack_digest === pack_digest) {
        if (
          ledgerData.ledger_chain !== bound.chain ||
          ledgerData.resume_stamp !== bound.resume
        ) {
          ledgerCorrupt = true;
        }
        const s = ledgerData.stage_seals;
        if (
          !s ||
          s.cal !== seal_cal ||
          s.prio !== seal_prio ||
          s.gauge !== seal_gauge ||
          s.brief !== seal_brief
        ) {
          ledgerCorrupt = true;
        }
      }
    } catch (e) {
      ledgerCorrupt = true;
    }
  }

  let restored = false;

  if (ledgerCorrupt) {
    console.warn(
      `[Ledger Integrity Failure] Corrupted ledger detected! Checking checkpoint for ${primary.manifest.ckpt}...`
    );
    if (existsPath(checkpointPath)) {
      try {
        const ckptData = readJson<any>(checkpointPath);
        if (
          ckptData &&
          ckptData.pack_digest === pack_digest &&
          ckptData.ledger_chain === bound.chain &&
          ckptData.resume_stamp === bound.resume
        ) {
          const s = ckptData.stage_seals;
          if (
            s &&
            s.cal === seal_cal &&
            s.prio === seal_prio &&
            s.gauge === seal_gauge &&
            s.brief === seal_brief
          ) {
            ledgerData = {
              pack_digest: ckptData.pack_digest,
              ledger_chain: ckptData.ledger_chain,
              resume_stamp: ckptData.resume_stamp,
              stage_seals: ckptData.stage_seals,
            };
            restored = true;
            console.log(
              `[Ledger Integrity Recovery] Successfully restored ledger from checkpoint: ${primary.manifest.ckpt}`
            );
          }
        }
      } catch (e) {
        // checkpoint unreadable
      }
    }

    if (!restored && existsPath(tapePath)) {
      const replayed = tryReplay(tapePath, pack_digest);
      if (replayed) {
        const tags = ["cal", "prio", "gauge", "brief"] as const;
        const matches = tags.every((tag) => replayed[tag] === stage_seals[tag]);
        if (matches) {
          ledgerData = {
            pack_digest,
            ledger_chain: bound.chain,
            resume_stamp: bound.resume,
            stage_seals,
          };
          restored = true;
          console.log("[Ledger Integrity Recovery] Restored ledger from stage tape replay");
        }
      }
    }
  }

  if (!restored) {
    // Corrupt ledger with a present stage tape must be healed via tapeReplay
    // (checkpoint already failed). Do not silently overwrite with a fresh ledger.
    if (ledgerCorrupt && existsPath(tapePath)) {
      if (!ledgerData || typeof ledgerData !== "object") {
        ledgerData = {
          pack_digest: "unrecovered",
          ledger_chain: "unrecovered",
          resume_stamp: "unrecovered",
          stage_seals: {},
        };
      }
    } else {
      ledgerData = {
        pack_digest,
        ledger_chain: bound.chain,
        resume_stamp: bound.resume,
        stage_seals,
      };
    }
  }

  emitTape(tapePath, [
    {
      pack_digest,
      tag: "cal",
      seal: seal_cal,
      parts: [core.trainEnd, core.evalStart, core.leakProbe],
    },
    {
      pack_digest,
      tag: "prio",
      seal: seal_prio,
      parts: [fx6(core.priorDelta), fx6(core.priorDeltaResidual)],
    },
    {
      pack_digest,
      tag: "gauge",
      seal: seal_gauge,
      parts: [fx6(core.accHome), fx6(core.accShift), fx6(core.accGap), nSalt],
    },
    {
      pack_digest,
      tag: "brief",
      seal: seal_brief,
      parts: [brief.length, Object.keys(mIdx).length],
    },
  ]);

  const checkpointPayload = {
    checkpoint_stamp: primary.manifest.ckpt,
    pack_digest,
    ledger_chain: bound.chain,
    resume_stamp: bound.resume,
    stage_seals,
  };
  writeText(checkpointPath, JSON.stringify(checkpointPayload, null, 2) + "\n");

  writeText(joinPath(out, "scenario_score.json"), JSON.stringify(payload, null, 2) + "\n");
  writeText(joinPath(out, "uncertainty_brief.md"), brief.endsWith("\n") ? brief : brief + "\n");
  writeText(ledgerPath, JSON.stringify(ledgerData, null, 2) + "\n");
}

main();
