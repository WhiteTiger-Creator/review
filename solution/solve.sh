#!/bin/bash
set -euo pipefail

cd /app

cat > a7/w9/k_wind.ts <<'EOF'
import { WindBag } from "../../src/types";

export function kWind(xSlot: number, yMeta: Record<string, number>): WindBag {
  const span = typeof yMeta.span === "number" ? yMeta.span : 4;
  const trainEnd = xSlot + span;
  const evalStart = trainEnd + 1;

  const slots: any[] = (global as any).currentSlots || [];

  let maxTrainDay = Number.NEGATIVE_INFINITY;
  let minEvalDay = Number.POSITIVE_INFINITY;

  for (const s of slots) {
    if (s.id >= xSlot && s.id <= trainEnd) {
      if (s.day > maxTrainDay) {
        maxTrainDay = s.day;
      }
    } else if (s.id >= evalStart) {
      if (s.day < minEvalDay) {
        minEvalDay = s.day;
      }
    }
  }

  const leakProbe =
    maxTrainDay >= minEvalDay && Number.isFinite(maxTrainDay) && Number.isFinite(minEvalDay)
      ? 1
      : 0;

  const rows: Array<Record<string, number>> = [];
  for (let i = xSlot; i <= evalStart; i++) {
    rows.push({ id: i, day: i, slot: i, span });
  }
  if (rows.length === 0) {
    rows.push({ id: xSlot, day: xSlot, slot: xSlot, span });
  }

  return { trainEnd, evalStart, leakProbe, rows };
}
EOF

cat > b3/p4/r_fit.ts <<'EOF'
export function robustResid(z: number[], c: number[]): number[] {
  if (c.length !== z.length || z.length === 0) return z.slice();
  let dotCc = 0;
  let dotCz = 0;
  for (let i = 0; i < z.length; i++) {
    dotCc += c[i] * c[i];
    dotCz += c[i] * z[i];
  }
  if (dotCc <= 0) return z.slice();
  const a = dotCz / dotCc;
  const r1 = z.map((zi, i) => zi - a * c[i]);
  const mean = r1.reduce((s, v) => s + v, 0) / r1.length;
  const std = Math.sqrt(r1.reduce((s, v) => s + Math.pow(v - mean, 2), 0) / r1.length);
  const inliers: number[] = [];
  for (let i = 0; i < r1.length; i++) {
    if (Math.abs(r1[i] - mean) <= 2.0 * std) inliers.push(i);
  }
  if (inliers.length < 3) return r1;
  let cc = 0;
  let cz = 0;
  for (const i of inliers) {
    cc += c[i] * c[i];
    cz += c[i] * z[i];
  }
  if (cc <= 0) return r1;
  const ar = cz / cc;
  return z.map((zi, i) => zi - ar * c[i]);
}
EOF

cat > b3/p4/m_prio.ts <<'EOF'
import { PrioBag } from "../../src/types";
import { binPriorDelta, getCovBuf } from "./hist_util";
import { robustResid } from "./r_fit";

export function mPrio(zVec: number[], kParts: number): PrioBag {
  const parts = Math.max(2, Math.floor(kParts));
  const priorDelta = binPriorDelta(zVec, parts);
  const cov = getCovBuf();
  const aligned = cov.length === zVec.length ? cov : [];
  const resid = aligned.length === zVec.length ? robustResid(zVec, aligned) : zVec.slice();
  const priorDeltaResidual = binPriorDelta(resid, parts);
  return {
    priorDelta,
    priorDeltaResidual,
    parts,
  };
}
EOF

cat > c5/g2/m_edge.ts <<'EOF'
export function rankEdges(logits: number[], k: number): number[] {
  const margins = logits.map((logit, idx) => ({ margin: Math.abs(logit), idx }));
  margins.sort((a, b) => {
    const d = a.margin - b.margin;
    if (Math.abs(d) < 1e-9) return a.idx - b.idx;
    return d;
  });
  return margins.slice(0, Math.max(0, k)).map((m) => m.idx);
}
EOF

cat > c5/g2/v_gauge.ts <<'EOF'
import { GaugeMap } from "../../src/types";
import { getTrueBuf, hitRate } from "./gauge_types";
import { rankEdges } from "./m_edge";

export function vGauge(aHome: number[], bPart: number[], nSalt: number): GaugeMap {
  const truth = getTrueBuf();
  const base = truth.length ? truth.slice() : aHome.slice();
  const home = aHome.length ? aHome : base;
  const shift = bPart.length ? bPart : home;

  const accHome = hitRate(home, base);

  const K = nSalt % 3;
  const shiftPerturbed = shift.slice();
  if (K > 0 && base.length === shift.length) {
    const picks = rankEdges(base, K);
    for (const idx of picks) {
      shiftPerturbed[idx] = shift[idx] >= 0 ? -1.0 : 1.0;
    }
  }

  const accShift = hitRate(shiftPerturbed, base);
  const accGap = accHome - accShift;

  return {
    accHome,
    accShift,
    accGap,
    salt: nSalt,
  };
}
EOF

cat > d9/l8/t_emit.ts <<'EOF'
import { fx6, pipeTable } from "./table_util";

export function tEmit(mIdx: Record<string, number>, maxPages: number): string {
  void maxPages;
  const keys = Object.keys(mIdx);
  keys.sort((a, b) => {
    if (a.length !== b.length) {
      return a.length - b.length;
    }
    return a.localeCompare(b);
  });

  const floatKeys: Record<string, boolean> = {
    prior_delta: true,
    prior_delta_residual: true,
    acc_home: true,
    acc_shift: true,
    acc_gap: true,
  };

  const rows: string[][] = [];
  for (const key of keys) {
    if (!(key in mIdx)) continue;
    const v = mIdx[key];
    const cell = floatKeys[key] ? fx6(v) : String(Math.trunc(v));
    rows.push([key, cell]);
  }

  const table = pipeTable(["question", "value"], rows);
  return `# Scoring\n\n${table}\n`;
}
EOF

cat > r4/q_bind.ts <<'EOF'
import { makeReproHex } from "../lib/hash";

export function qBind(
  packDigest: string,
  seals: string[]
): { chain: string; resume: string } {
  const ordered = seals.slice();
  const chain = makeReproHex([packDigest, ...ordered]);
  const resume = makeReproHex([chain, ordered.length]);
  return { chain, resume };
}

export function qPackDigest(parts: Array<string | number>): string {
  return makeReproHex(parts);
}
EOF

cat > x2/s_memo.ts <<'EOF'
const memoStore = new Map<string, any>();

export function memoGet(digest: string): any | null {
  return memoStore.has(digest) ? memoStore.get(digest) : null;
}

export function memoPut(digest: string, payload: any): void {
  memoStore.set(digest, payload);
}

export function memoClear(): void {
  memoStore.clear();
}
EOF

cat > j6/w_tape.ts <<'EOF'
import { writeFileSync, appendFileSync, existsSync, readFileSync, mkdirSync } from "fs";
import { dirname } from "path";

export type TapeEvent = {
  pack_digest: string;
  tag: string;
  seal: string;
  parts: Array<string | number>;
};

export function tapeReset(path: string): void {
  const dir = dirname(path);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  writeFileSync(path, "", "utf8");
}

export function tapeAppend(path: string, ev: TapeEvent): void {
  appendFileSync(path, JSON.stringify(ev) + "\n", "utf8");
}

export function tapeReplay(path: string, packDigest: string): Record<string, string> | null {
  if (!existsSync(path)) return null;
  const raw = readFileSync(path, "utf8");
  const map: Record<string, string> = {};
  for (const line of raw.split("\n")) {
    if (!line.trim()) continue;
    let ev: TapeEvent;
    try {
      ev = JSON.parse(line) as TapeEvent;
    } catch {
      continue;
    }
    if (ev.pack_digest !== packDigest) continue;
    map[ev.tag] = ev.seal;
  }
  const required = ["cal", "prio", "gauge", "brief"];
  for (const tag of required) {
    if (!(tag in map)) return null;
  }
  return map;
}
EOF

bash /app/environment/scripts/run_desk.sh --pack /app/data/board_q3 --out /app/output
