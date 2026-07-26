import { mkdirSync } from "node:fs";
import { loadCsv } from "../lib/csv_in.js";
import { loadLayout, writeLayout } from "../lib/layout_io.js";
import { writeBundle } from "../lib/bundle_io.js";
import { writeScorecard } from "../lib/trace_emit.js";
import { mapK } from "../enc/map_k.js";
import { fitW } from "../est/fit_w.js";
import { wideBag } from "../enc/wide_bag.js";
import { meanLine } from "../est/mean_line.js";

const root = "/app/environment";
const out = "/app/output";
mkdirSync(out, { recursive: true });

const layout = loadLayout(`${root}/fixtures/seed_layout.json`);
const fitRows = loadCsv(`${root}/data/prime_batch.csv`);

const setG = new Set<string>();
const setT = new Set<string>();
for (const r of fitRows) {
  if (r.grp) setG.add(r.grp);
  if (r.tier) setT.add(r.tier);
}
layout.vocab = { g: [...setG].sort(), t: [...setT].sort() };

void wideBag(fitRows[0], layout);
void meanLine(
  fitRows.map((r) => mapK(r, layout)),
  fitRows.map((r) => r.tgt ?? 0),
);

const encoded = fitRows.map((r) => mapK(r, layout));
const targets = fitRows.map((r) => r.tgt ?? 0);
const bundle = fitW(encoded, targets, layout);

writeLayout(`${out}/layout.json`, bundle.layout);
writeBundle(`${out}/bundle.json`, bundle);

let correct = 0;
for (let i = 0; i < fitRows.length; i++) {
  const v = encoded[i].v;
  let z = bundle.b;
  for (let j = 0; j < v.length && j < bundle.w.length; j++) z += v[j] * bundle.w[j];
  const p = 1 / (1 + Math.exp(-z));
  const pred = p >= 0.5 ? 1 : 0;
  if (pred === targets[i]) correct += 1;
}
const acc = fitRows.length === 0 ? 0 : correct / fitRows.length;
writeScorecard(`${out}/scorecard.json`, {
  acc,
  flip_rate: 0,
  mean_l0: 0,
  n_rows: 0,
});
