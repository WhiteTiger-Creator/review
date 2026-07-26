#!/bin/bash
set -euo pipefail

apply_a=${apply_a:-1}
apply_b=${apply_b:-1}
apply_c=${apply_c:-1}

if [ "${apply_a}" = "1" ]; then
cat > "/app/environment/enc/map_k.ts" <<'EOF'
import type { EncodedVec, LayoutBlob, RawRow } from "../lib/types.js";

export function mapK(row: RawRow, layout: LayoutBlob): EncodedVec {
  const v = new Array(layout.dim).fill(0);
  put(v, slotG(layout, row.grp), 1);
  put(v, slotT(layout, row.tier), 1);
  put(v, layout.offs.nx, row.mag * layout.scale);
  return { v };
}

function slotG(layout: LayoutBlob, tok: string): number {
  if (!tok) return layout.r0;
  const i = layout.vocab.g.indexOf(tok);
  if (i < 0) return layout.r1;
  return layout.offs.g + i;
}

function slotT(layout: LayoutBlob, tok: string): number {
  if (!tok) return layout.r0;
  const i = layout.vocab.t.indexOf(tok);
  if (i < 0) return layout.r1;
  return layout.offs.t + i;
}

function put(v: number[], ix: number, val: number): void {
  if (ix >= 0 && ix < v.length) {
    v[ix] = val;
  }
}
EOF
fi

if [ "${apply_b}" = "1" ]; then
cat > "/app/environment/est/fit_w.ts" <<'EOF'
import type { EncodedVec, FitBundle, LayoutBlob } from "../lib/types.js";

export function fitW(
  rows: EncodedVec[],
  targets: number[],
  layout: LayoutBlob,
): FitBundle {
  const w = new Array(layout.dim).fill(0);
  let b = 0;
  const pos = targets.filter((y) => y >= 0.5).length;
  const neg = targets.length - pos;
  if (pos > 0 && neg > 0) {
    for (let j = 0; j < layout.dim; j++) {
      let sp = 0;
      let sn = 0;
      for (let i = 0; i < rows.length; i++) {
        const v = rows[i].v[j] || 0;
        if (targets[i] >= 0.5) sp += v;
        else sn += v;
      }
      w[j] = sp / pos - sn / neg;
    }
    b = Math.log(pos / neg);
  }
  const lr = 0.4;
  for (let epoch = 0; epoch < 500; epoch++) {
    for (let i = 0; i < rows.length; i++) {
      const z = b + dot(rows[i], w);
      const p = sig(z);
      const g = p - targets[i];
      b -= lr * g;
      const v = rows[i].v;
      for (let j = 0; j < v.length && j < w.length; j++) {
        w[j] -= lr * g * v[j];
      }
    }
  }
  return { layout: structuredClone(layout), w, b };
}

function dot(row: EncodedVec, w: number[]): number {
  let z = 0;
  const v = row.v;
  for (let i = 0; i < v.length && i < w.length; i++) z += v[i] * w[i];
  return z;
}

function sig(z: number): number {
  if (z >= 20) return 1;
  if (z <= -20) return 0;
  return 1 / (1 + Math.exp(-z));
}
EOF
fi

if [ "${apply_c}" = "1" ]; then
cat > "/app/environment/mut/seek_m.ts" <<'EOF'
import { mapK } from "../enc/map_k.js";
import type {
  Caps,
  CfRow,
  FitBundle,
  MutCell,
  RawRow,
} from "../lib/types.js";

export function seekM(row: RawRow, bundle: FitBundle, caps: Caps): CfRow {
  const layout = bundle.layout;
  const base = mapK(row, layout).v;
  const y0 = score(base, bundle.w, bundle.b) >= 0.5 ? 1 : 0;

  type Cand = { mut: MutCell[]; row: RawRow };
  const cands: Cand[] = [];

  const altsG = ["", ...layout.vocab.g];
  const altsT = ["", ...layout.vocab.t];
  const magDeltas = [-1.2, -0.8, -0.4, 0.4, 0.8, 1.2, 1.6, -1.6];

  for (const g of altsG) {
    if (g === row.grp) continue;
    cands.push({
      mut: [{ k: "grp", a: row.grp, b: g }],
      row: { ...row, grp: g },
    });
  }
  for (const t of altsT) {
    if (t === row.tier) continue;
    cands.push({
      mut: [{ k: "tier", a: row.tier, b: t }],
      row: { ...row, tier: t },
    });
  }
  for (const d of magDeltas) {
    const nv = Math.round((row.mag + d) * 10) / 10;
    if (nv === row.mag) continue;
    cands.push({
      mut: [{ k: "mag", a: row.mag, b: nv }],
      row: { ...row, mag: nv },
    });
  }

  for (const g of altsG) {
    if (g === row.grp) continue;
    for (const t of altsT) {
      if (t === row.tier) continue;
      cands.push({
        mut: [
          { k: "grp", a: row.grp, b: g },
          { k: "tier", a: row.tier, b: t },
        ],
        row: { ...row, grp: g, tier: t },
      });
    }
  }
  for (const g of altsG) {
    if (g === row.grp) continue;
    for (const d of magDeltas) {
      const nv = Math.round((row.mag + d) * 10) / 10;
      if (nv === row.mag) continue;
      cands.push({
        mut: [
          { k: "grp", a: row.grp, b: g },
          { k: "mag", a: row.mag, b: nv },
        ],
        row: { ...row, grp: g, mag: nv },
      });
    }
  }

  for (const g of altsG) {
    if (g === row.grp) continue;
    for (const t of altsT) {
      if (t === row.tier) continue;
      for (const d of [-0.8, 0.8, 1.2]) {
        const nv = Math.round((row.mag + d) * 10) / 10;
        if (nv === row.mag) continue;
        cands.push({
          mut: [
            { k: "grp", a: row.grp, b: g },
            { k: "tier", a: row.tier, b: t },
            { k: "mag", a: row.mag, b: nv },
          ],
          row: { ...row, grp: g, tier: t, mag: nv },
        });
      }
    }
  }

  let best: CfRow | null = null;
  for (const c of cands) {
    if (c.mut.length < 1 || c.mut.length > caps.maxL0) continue;
    const enc = mapK(c.row, layout).v;
    const nbytes = packLen(enc);
    if (nbytes > caps.maxN) continue;
    const y1 = score(enc, bundle.w, bundle.b) >= 0.5 ? 1 : 0;
    if (y1 === y0) continue;
    const cand: CfRow = {
      id: row.id,
      y0,
      y1,
      mut: c.mut,
      l0: c.mut.length,
      nbytes,
      enc_digest: digest(enc),
    };
    if (
      !best ||
      cand.l0 < best.l0 ||
      (cand.l0 === best.l0 && cand.nbytes < best.nbytes)
    ) {
      best = cand;
    }
  }

  if (!best) {
    return {
      id: row.id,
      y0,
      y1: y0,
      mut: [],
      l0: 0,
      nbytes: packLen(base),
      enc_digest: digest(base),
    };
  }
  return best;
}

function score(v: number[], w: number[], b: number): number {
  let z = b;
  for (let i = 0; i < v.length && i < w.length; i++) z += v[i] * w[i];
  if (z >= 20) return 1;
  if (z <= -20) return 0;
  return 1 / (1 + Math.exp(-z));
}

function packLen(v: number[]): number {
  return Buffer.byteLength(JSON.stringify(v), "utf8");
}

function digest(v: number[]): string {
  const joined = v.map((x) => x.toFixed(3)).join(",");
  let h = 0xcbf29ce484222325n;
  const bytes = Buffer.from(joined, "utf8");
  for (const b of bytes) {
    h ^= BigInt(b);
    h = (h * 0x100000001b3n) & 0xffffffffffffffffn;
  }
  return h.toString(16).padStart(16, "0");
}
EOF
fi

cd /app/environment
npx tsx /app/environment/run_fit/main.ts
npx tsx /app/environment/run_cf/main.ts --verify /app/output/cf_trace.json
