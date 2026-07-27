import { mkdirSync, readFileSync } from "node:fs";
import { loadCsv } from "../lib/csv_in.js";
import { loadLayout } from "../lib/layout_io.js";
import { loadBundle } from "../lib/bundle_io.js";
import { writeScorecard, writeTrace } from "../lib/trace_emit.js";
import { seekM } from "../mut/seek_m.js";
import { sortIds } from "../mut/sort_ids.js";

const root = "/app/environment";
const out = "/app/output";
mkdirSync(out, { recursive: true });

const args = process.argv.slice(2);
let verifyPath = `${out}/cf_trace.json`;
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--verify" && args[i + 1]) verifyPath = args[i + 1];
}

const layout = loadLayout(`${out}/layout.json`);
const bundle = loadBundle(`${out}/bundle.json`, layout);
const hold = [
  ...loadCsv(`${root}/data/blank_rows.csv`),
  ...loadCsv(`${root}/data/novel_rows.csv`),
];
void sortIds(hold);

const caps = { maxL0: layout.max_l0, maxN: layout.max_n };
const rows = hold.map((r) => seekM(r, bundle, caps));
writeTrace(verifyPath, rows);

let flips = 0;
let l0Sum = 0;
for (const r of rows) {
  if (r.y1 !== r.y0 && r.l0 > 0) {
    flips += 1;
    l0Sum += r.l0;
  }
}
const n = rows.length;
const flip_rate = n === 0 ? 0 : flips / n;
const mean_l0 = flips === 0 ? 0 : l0Sum / flips;

const prev = JSON.parse(readFileSync(`${out}/scorecard.json`, "utf8")) as {
  acc: number;
};
writeScorecard(`${out}/scorecard.json`, {
  acc: prev.acc,
  flip_rate,
  mean_l0,
  n_rows: n,
});
