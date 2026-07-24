/**
 * Driver writes /app/output/cover_min_report.json.
 * Row fields: scenario_id, span_rc, hop_rc, mark_rc, drift_code, facet_hex.
 * Summary: rows_total, consensus_status, span_band, lane_digest, rule_count, gauge.
 * argv: npm run build && /app/m3/k72/dist/fm
 * health subcommand: /app/m3/k72/dist/fm --health (local probe only)
 */
import * as fs from "fs";
import * as path from "path";
import { fold_lane, refresh_pack } from "../../n4/src/bind_step";
import { run_combine, pad_mix } from "./stack_mix";
import {
  lines_p7,
  TargetRow,
  SeedBundle,
  MarkWitness,
  EmittedRow,
} from "../../../p8/core/src/lines_p7";
import { mesh_view } from "../../../p8/core/src/mesh";
import { gauge_summary } from "../../../p8/core/src/gauge_r";

const APP = process.cwd();
const DATA = path.join(APP, "data");
const DOCS = path.join(APP, "docs");
const OUT = path.join(APP, "output", "cover_min_report.json");

interface RuleRow {
  id: string;
  family: number;
  sole_witness: boolean;
  shadowed_by: string | null;
}

function read_scene_ids(): string[] {
  return fs
    .readFileSync(path.join(DOCS, "scene_ids.txt"), "utf8")
    .trim()
    .split(",")
    .map((s: string) => s.trim())
    .filter(Boolean);
}

function read_seed(): SeedBundle {
  const raw = JSON.parse(
    fs.readFileSync(path.join(DATA, "seed_bundle.json"), "utf8")
  );
  return { marks: raw.marks as Record<string, number> };
}

function read_rules(): RuleRow[] {
  const raw = JSON.parse(fs.readFileSync(path.join(DATA, "rules.json"), "utf8"));
  return raw.rules as RuleRow[];
}

function read_mix(): Record<string, [number, number, number][]> {
  const text = fs.readFileSync(path.join(DATA, "mix_table.toml"), "utf8");
  const out: Record<string, [number, number, number][]> = {};
  let cur = "";
  for (const line of text.split("\n")) {
    const sec = line.match(/^\[scenes\.([^\]]+)\]/);
    if (sec) {
      cur = sec[1];
      out[cur] = [];
      continue;
    }
    const step = line.match(
      /^\s*steps\s*=\s*\[\s*(.+)\]\s*$/
    );
    if (step && cur) {
      const tuples = step[1].matchAll(/\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)/g);
      for (const m of tuples) {
        out[cur].push([Number(m[1]), Number(m[2]), Number(m[3])]);
      }
    }
  }
  return out;
}

function read_extras(): string[] {
  const text = fs.readFileSync(path.join(DATA, "extra_scenes.toml"), "utf8");
  const m = text.match(/ids\s*=\s*\[([^\]]*)\]/);
  if (!m) return [];
  return Array.from(m[1].matchAll(/"([^"]+)"/g)).map((x: RegExpMatchArray) => x[1]);
}

function lane_digest_from_rows(rows: EmittedRow[]): string {
  const parts = rows.map(
    (row) =>
      `${row.scenario_id}|${row.span_rc ? 1 : 0}|${row.hop_rc ? 1 : 0}|${
        row.mark_rc ? 1 : 0
      }|${row.drift_code}|${row.facet_hex}`
  );
  parts.sort();
  const payload = parts.join("\n");
  const mask64 = (1n << 64n) - 1n;
  let total = 0n;
  for (let idx = 0; idx < payload.length; idx++) {
    const addend = BigInt((idx + 1) * payload.charCodeAt(idx)) & mask64;
    total = (total + addend) & mask64;
  }
  return (total & 0xffffffffn).toString(16).padStart(8, "0");
}

function mirror_ok(rows: EmittedRow[]): boolean {
  const by = Object.fromEntries(rows.map((r) => [r.scenario_id, r]));
  const pairs: [string, string][] = [
    ["lowerdir", "lowerdir_echo"],
    ["upper", "upper_echo"],
    ["worker", "worker_echo"],
  ];
  return pairs.every(([a, b]) => {
    const ra = by[a];
    const rb = by[b];
    if (!ra || !rb) return false;
    return (
      ra.facet_hex === rb.facet_hex &&
      ra.span_rc === rb.span_rc &&
      ra.hop_rc === rb.hop_rc &&
      ra.mark_rc === rb.mark_rc
    );
  });
}

function reduce_rules(rules: RuleRow[]): number {
  let kept = 0;
  for (const r of rules) {
    if (r.sole_witness) {
      kept += 1;
      continue;
    }
    if (r.shadowed_by) {
      continue;
    }
    kept += 1;
  }
  return kept;
}

function build_targets(
  ids: string[],
  mix: Record<string, [number, number, number][]>,
  seeds: SeedBundle
): { targets: TargetRow[]; health: Record<string, number> } {
  const health: Record<string, number> = {};
  const targets: TargetRow[] = [];
  for (const id of mesh_view(ids)) {
    const steps = mix[id] || [[1, 1, 0]];
    let fold = 0n;
    let spanDone = false;
    let hopDone = false;
    let premature = false;
    let phase = 0;
    const state = { stamp: 0, mark: 0 };
    const durable = seeds.marks[id] ?? 0;
    health[id] = durable ^ 0x11;

    for (const [stepIx, familyIx, prevFamily] of steps) {
      fold = fold_lane(stepIx, familyIx, prevFamily);
      const incoming = { stamp: stepIx, mark: durable };
      refresh_pack(state, incoming, familyIx);
      phase = 0;
      const code = run_combine(
        false,
        () => {
          phase = 1;
          spanDone = true;
        },
        () => {
          if (phase !== 1) {
            premature = true;
          }
          hopDone = true;
        }
      );
      void code;
      void pad_mix(stepIx, familyIx);
    }

    targets.push({
      scenario_id: id,
      step_ix: steps[steps.length - 1][0],
      family_ix: steps[steps.length - 1][1],
      prev_family: steps[steps.length - 1][2],
      fold_bits: fold,
      mark: state.mark,
      hop_done: hopDone,
      span_done: spanDone,
      premature,
    });
  }
  return { targets, health };
}

function run_pipeline(): void {
  const sceneIds = read_scene_ids();
  const extras = read_extras();
  const allIds = Array.from(new Set([...sceneIds, ...extras]));
  const seeds = read_seed();
  const mix = read_mix();
  const rules = read_rules();

  const { targets, health } = build_targets(allIds, mix, seeds);
  const witness: MarkWitness = {
    durable: { ...seeds.marks },
    health,
  };
  const rows = lines_p7(targets, seeds, witness);
  const primaryRows = rows.filter((r) => sceneIds.includes(r.scenario_id));
  const ordered = primaryRows
    .slice()
    .sort((a, b) => a.scenario_id.localeCompare(b.scenario_id));

  const spanBand = Math.max(0, ...ordered.map((r) => Math.abs(r.drift_code)));
  const allClosed = ordered.every(
    (r) => r.drift_code === 0 && r.span_rc && r.hop_rc && r.mark_rc
  );
  const consensus =
    allClosed && mirror_ok(ordered) ? "settled" : "drift";
  const digest = lane_digest_from_rows(ordered);
  const ruleCount = reduce_rules(rules);

  const report = {
    rows: ordered,
    summary: {
      rows_total: ordered.length,
      consensus_status: consensus,
      span_band: spanBand,
      lane_digest: digest,
      rule_count: ruleCount,
      gauge: gauge_summary(ordered),
    },
  };

  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(report, null, 2) + "\n", "utf8");
}

function health_only(): void {
  console.log(JSON.stringify({ status: "green", probe: "ok" }));
}

if (process.argv.includes("--health")) {
  health_only();
} else {
  run_pipeline();
}
