import json
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path


APP = Path("/app")
OUT = APP / "output" / "cover_min_report.json"
SCENE_IDS = (
    (APP / "docs" / "scene_ids.txt").read_text(encoding="utf-8").strip().split(",")
)
PRUNE_A = APP / "p8/q3/src/prune_a.ts"
TRACK_B = APP / "p8/q4/src/track_b.ts"
MUX_G2 = APP / "m3/k72/src/mux_g2.ts"
LINES_P7 = APP / "p8/core/src/lines_p7.ts"
BIND_STEP = APP / "m3/n4/src/bind_step.ts"
MIX_TOML = APP / "data/mix_table.toml"
STRIDE_TS = APP / "p8/y6/src/stride.ts"
CATALOG_TS = APP / "p8/y6/src/catalog.ts"
MAIN_TS = APP / "m3/k72/src/main.ts"

EXPECTED_LANE_DIGEST = None  # filled after first coherent oracle run locally; tests recompute

BROKEN_PRUNE = """export function prune_a(stepIx: number, familyIx: number, prevFamily: number): bigint {
  const step = stepIx & 0xffff;
  const family = familyIx & 0xffff;
  const a = BigInt(step);
  const b = BigInt(family) << 16n;
  if (prevFamily === 0) {
    return a | b;
  }
  const sticky = 1n;
  return a | b | sticky;
}
"""

BROKEN_TRACK = """export interface PackState {
  stamp: number;
  mark: number;
}

export function track_b(state: PackState, incoming: PackState, stampB: number): number {
  const local = state.stamp ^ stampB;
  state.stamp = local >>> 0;
  void incoming.stamp;
  void incoming.mark;
  return state.mark;
}
"""

BROKEN_MUX = """import { order_c } from "../../../p8/q5/src/order_c";

export function mux_g2(
  gateFirst: boolean,
  side: () => void,
  gate: () => void
): number {
  const forceGateFirst = true;
  void gateFirst;
  return order_c(forceGateFirst, side, gate);
}
"""

BROKEN_BIND = """import { prune_a } from "../../../p8/q3/src/prune_a";
import { track_b, PackState } from "../../../p8/q4/src/track_b";

export function fold_lane(stepIx: number, familyIx: number, prevFamily: number): bigint {
  const packed = prune_a(stepIx, familyIx, prevFamily);
  if (prevFamily === 0) {
    return packed & 0xffffffffn;
  }
  return packed;
}

export function refresh_pack(
  state: PackState,
  incoming: PackState,
  stampB: number
): number {
  return track_b(state, incoming, stampB);
}
"""

BROKEN_LINES = """export interface TargetRow {
  scenario_id: string;
  step_ix: number;
  family_ix: number;
  prev_family: number;
  fold_bits: bigint;
  mark: number;
  hop_done: boolean;
  span_done: boolean;
  premature: boolean;
}

export interface SeedBundle {
  marks: Record<string, number>;
}

export interface MarkWitness {
  durable: Record<string, number>;
  health: Record<string, number>;
}

export interface EmittedRow {
  scenario_id: string;
  span_rc: boolean;
  hop_rc: boolean;
  mark_rc: boolean;
  drift_code: number;
  facet_hex: string;
}

export function facet_from_bits(bits: bigint): string {
  return (bits & 0xffffffffffffffffn).toString(16).padStart(16, "0").slice(-16);
}

export function lines_p7(
  targets: TargetRow[],
  seeds: SeedBundle,
  markWitness: MarkWitness
): EmittedRow[] {
  void seeds;
  const out: EmittedRow[] = [];
  for (const t of targets) {
    const healthMark = markWitness.health[t.scenario_id] ?? 0;
    const facet = facet_from_bits(t.fold_bits);
    const closed = t.span_done && t.hop_done;
    out.push({
      scenario_id: t.scenario_id,
      span_rc: t.span_done,
      hop_rc: t.hop_done,
      mark_rc: healthMark === t.mark,
      drift_code: t.premature || !closed ? 1 : 0,
      facet_hex: facet,
    });
  }
  return out;
}
"""


@contextmanager
def _patched_text(path: Path, replacement: str):
    original = path.read_text(encoding="utf-8")
    path.write_text(replacement, encoding="utf-8")
    try:
        yield
    finally:
        path.write_text(original, encoding="utf-8")


def _build_and_run() -> dict:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    subprocess.run(["/bin/true", "/app/environment/p8"], cwd=APP, check=False)
    subprocess.run(["npm", "run", "build"], cwd=APP, check=True)
    subprocess.run([str(APP / "m3/k72/dist/fm")], cwd=APP, check=True)
    return json.loads(OUT.read_text(encoding="utf-8"))


def _rows_by_id(report: dict) -> dict:
    return {row["scenario_id"]: row for row in report["rows"]}


def fold_facet_hex(step: int, family: int, prev: int) -> str:
    lineage = prev & 0xffff if prev != 0 else family & 0xffff
    bits = (step & 0xffff) | ((family & 0xffff) << 16) | (lineage << 32)
    return f"{bits & ((1 << 64) - 1):016x}"


def mix_steps_for_scene(scene_id: str) -> list[tuple[int, int, int]]:
    text = MIX_TOML.read_text(encoding="utf-8")
    section = f"[scenes.{scene_id}]"
    if section not in text:
        return []
    chunk = text.split(section, 1)[1].split("\n[", 1)[0]
    return [
        (int(m[1]), int(m[2]), int(m[3]))
        for m in re.finditer(r"\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)", chunk)
    ]


def expected_facet_for_scene(scene_id: str) -> str:
    steps = mix_steps_for_scene(scene_id)
    if not steps:
        raise AssertionError(f"missing mix steps for {scene_id}")
    step, family, prev = steps[-1]
    return fold_facet_hex(step, family, prev)


def lane_digest_from_rows(rows: list[dict]) -> str:
    parts = []
    for row in rows:
        parts.append(
            f'{row["scenario_id"]}|{int(row["span_rc"])}|{int(row["hop_rc"])}|'
            f'{int(row["mark_rc"])}|{row["drift_code"]}|{row["facet_hex"]}'
        )
    parts.sort()
    payload = "\n".join(parts)
    mask64 = (1 << 64) - 1
    total = 0
    for idx, ch in enumerate(payload):
        addend = ((idx + 1) * ord(ch)) & mask64
        total = (total + addend) & mask64
    return f"{total & 0xFFFFFFFF:08x}"


def _assert_not_fully_coherent(report: dict) -> None:
    rows = _rows_by_id(report)
    pairs = [
        ("lowerdir", "lowerdir_echo"),
        ("upper", "upper_echo"),
        ("worker", "worker_echo"),
    ]
    mirror_ok = all(
        rows[a]["facet_hex"] == rows[b]["facet_hex"]
        and rows[a]["span_rc"] == rows[b]["span_rc"]
        and rows[a]["hop_rc"] == rows[b]["hop_rc"]
        and rows[a]["mark_rc"] == rows[b]["mark_rc"]
        for a, b in pairs
        if a in rows and b in rows
    )
    flags_ok = all(
        r["drift_code"] == 0 and r["span_rc"] and r["hop_rc"] and r["mark_rc"]
        for r in report["rows"]
    )
    sync_ok = report["summary"]["consensus_status"] == "settled"
    if mirror_ok and flags_ok and sync_ok:
        raise AssertionError("expected incoherent report after ablation")


def _check_closure_and_zero_drift(report: dict) -> None:
    for row in report["rows"]:
        if row["drift_code"] != 0:
            raise AssertionError("drift_code must be zero when coherent")
        if not (row["span_rc"] and row["hop_rc"] and row["mark_rc"]):
            raise AssertionError("closure fields must hold when coherent")


def _check_consensus_settled(report: dict) -> None:
    if report["summary"]["consensus_status"] != "settled":
        raise AssertionError("consensus_status must read settled when coherent")


def _check_minimized_cover(report: dict) -> None:
    _check_consensus_settled(report)
    digest = lane_digest_from_rows(report["rows"])
    if report["summary"]["lane_digest"] != digest:
        raise AssertionError("lane_digest must match row reduction")
    if report["summary"]["rule_count"] != 4:
        raise AssertionError("minimized rule_count mismatch")


def _check_mirror_pairs(report: dict) -> None:
    rows = _rows_by_id(report)
    for a, b in [
        ("lowerdir", "lowerdir_echo"),
        ("upper", "upper_echo"),
        ("worker", "worker_echo"),
    ]:
        if rows[a]["facet_hex"] != rows[b]["facet_hex"]:
            raise AssertionError(f"facet_hex mismatch for {a}/{b}")
        if rows[a]["span_rc"] != rows[b]["span_rc"]:
            raise AssertionError(f"span_rc mismatch for {a}/{b}")
        if rows[a]["hop_rc"] != rows[b]["hop_rc"]:
            raise AssertionError(f"hop_rc mismatch for {a}/{b}")
        if rows[a]["mark_rc"] != rows[b]["mark_rc"]:
            raise AssertionError(f"mark_rc mismatch for {a}/{b}")


def test_t1_layout() -> None:
    """Report lists every scene id from scene_ids.txt."""
    report = _build_and_run()
    if "rows" not in report or "summary" not in report:
        raise AssertionError("missing rows/summary")
    ids = {row["scenario_id"] for row in report["rows"]}
    if ids != set(SCENE_IDS):
        raise AssertionError("scenario_id set mismatch")
    if report["summary"]["rows_total"] != len(SCENE_IDS):
        raise AssertionError("rows_total mismatch")


def test_t2_pair_hex() -> None:
    """Mirror pairs agree on facet_hex and closure fields."""
    _check_mirror_pairs(_build_and_run())


def test_t3_band_field() -> None:
    """Coherent rows keep drift_code 0 and all closure fields true."""
    _check_closure_and_zero_drift(_build_and_run())


def test_t4_label_text() -> None:
    """Summary consensus_status is settled when coherent."""
    _check_consensus_settled(_build_and_run())


def test_t5_width_max() -> None:
    """span_band equals max abs drift_code."""
    report = _build_and_run()
    span = max(abs(r["drift_code"]) for r in report["rows"])
    if report["summary"]["span_band"] != span:
        raise AssertionError("span_band mismatch")


def test_t6_reduce_hex() -> None:
    """lane_digest matches the documented row reduction."""
    report = _build_and_run()
    assert report["summary"]["lane_digest"] == lane_digest_from_rows(report["rows"])


def test_t7_known_good() -> None:
    """Settled report has minimized rule_count of 4."""
    _check_minimized_cover(_build_and_run())


def test_t8_lower_fmt() -> None:
    """facet_hex is sixteen lowercase hex digits and matches mix_table packing."""
    report = _build_and_run()
    rows = _rows_by_id(report)
    for row in report["rows"]:
        s = row["facet_hex"]
        if len(s) != 16 or s != s.lower():
            raise AssertionError("facet_hex format")
        int(s, 16)
    for scene_id in SCENE_IDS:
        expected = expected_facet_for_scene(scene_id)
        if rows[scene_id]["facet_hex"] != expected:
            raise AssertionError(f"{scene_id} facet_hex packing mismatch")


def test_t9_total_count() -> None:
    """rows_total equals the number of rows."""
    report = _build_and_run()
    assert isinstance(report["summary"]["rows_total"], int)
    assert report["summary"]["rows_total"] == len(report["rows"])


def test_t10_fresh_pipe() -> None:
    """Pipeline overwrite replaces hand-written JSON."""
    OUT.write_text(json.dumps({"rows": [], "summary": {"rows_total": 0}}), encoding="utf-8")
    report = _build_and_run()
    if report["summary"]["rows_total"] != len(SCENE_IDS):
        raise AssertionError("fresh pipe rows_total")
    _check_consensus_settled(report)


def test_t11_twice_same() -> None:
    """Consecutive pipeline runs are identical."""
    a = _build_and_run()
    b = _build_and_run()
    assert a == b


def test_t12_sens_steps() -> None:
    """Mutating mix_table steps changes facet or coherence."""
    original = MIX_TOML.read_text(encoding="utf-8")
    mutated = re.sub(
        r"\[scenes\.lowerdir\]\nsteps = \[\(1, 1, 0\)\]",
        "[scenes.lowerdir]\nsteps = [(2, 1, 0)]",
        original,
        count=1,
    )
    if mutated == original:
        raise AssertionError("mutation did not apply")
    try:
        MIX_TOML.write_text(mutated, encoding="utf-8")
        report = _build_and_run()
        rows = _rows_by_id(report)
        same_hex = rows["lowerdir"]["facet_hex"] == rows["lowerdir_echo"]["facet_hex"]
        settled = report["summary"]["consensus_status"] == "settled"
        if same_hex and settled:
            raise AssertionError("expected facet or coherence change")
    finally:
        MIX_TOML.write_text(original, encoding="utf-8")


def test_t13_flip_a() -> None:
    """Reverting sticky lineage fold breaks mirror-pair coherence."""
    with _patched_text(PRUNE_A, BROKEN_PRUNE):
        report = _build_and_run()
    _assert_not_fully_coherent(report)


def test_t14_flip_b() -> None:
    """Reverting durable mark merge with lineage fold breaks coherence."""
    with _patched_text(TRACK_B, BROKEN_TRACK):
        with _patched_text(PRUNE_A, BROKEN_PRUNE):
            report = _build_and_run()
    _assert_not_fully_coherent(report)


def test_t15_flip_c() -> None:
    """Reverting combine ordering breaks coherence."""
    with _patched_text(MUX_G2, BROKEN_MUX):
        with _patched_text(STRIDE_TS, STRIDE_TS.read_text(encoding="utf-8")):
            report = _build_and_run()
    _assert_not_fully_coherent(report)


def test_t16_all_extras() -> None:
    """Held-out extras survive with minimized rule_count."""
    _check_minimized_cover(_build_and_run())


def test_t17_flip_d() -> None:
    """Reverting witness emitter path breaks coherence."""
    with _patched_text(LINES_P7, BROKEN_LINES):
        report = _build_and_run()
    _assert_not_fully_coherent(report)


def test_t18_dur_first() -> None:
    """Durable marks win over health probes when coherent."""
    report = _build_and_run()
    _check_closure_and_zero_drift(report)
    _check_consensus_settled(report)
    health = subprocess.run(
        [str(APP / "m3/k72/dist/fm"), "--health"],
        cwd=APP,
        check=True,
        capture_output=True,
        text=True,
    )
    if "green" not in health.stdout:
        raise AssertionError("health probe expected green")


def test_t19_premature() -> None:
    """Wrong combine order yields premature drift."""
    with _patched_text(MUX_G2, BROKEN_MUX):
        report = _build_and_run()
    settled = report["summary"]["consensus_status"] == "settled"
    clean = all(r["drift_code"] == 0 for r in report["rows"])
    if settled and clean:
        raise AssertionError("expected premature drift")


def test_t20_cmd_run() -> None:
    """build_hints document npm build and fm driver argv."""
    hints = (APP / "docs" / "build_hints.txt").read_text(encoding="utf-8")
    if "npm run build" not in hints or "m3/k72/dist/fm" not in hints:
        raise AssertionError("build_hints missing driver argv")
    report = _build_and_run()
    if report["summary"]["rows_total"] != len(SCENE_IDS):
        raise AssertionError("rows_total after cmd run")


def test_t21_gate_arg_probe() -> None:
    """Compiled zone-hop combine helper must honor gateFirst for callback sequencing."""
    subprocess.run(["npm", "run", "build"], cwd=APP, check=True)
    probe = (
        "const { mux_g2 } = require('/app/dist/m3/k72/src/mux_g2.js');"
        "function run(gf){const s=[];mux_g2(gf,()=>s.push('side'),()=>s.push('gate'));"
        "return s.join(',');}"
        "if(run(false)!=='side,gate') process.exit(2);"
        "if(run(true)!=='gate,side') process.exit(3);"
    )
    result = subprocess.run(["node", "-e", probe], cwd=APP, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError("combine helper must honor gateFirst without caller compensation")


def test_t22_prev_lineage_width() -> None:
    """Baseline scenes with zero prev must retain full lane width in facet_hex."""
    report = _build_and_run()
    rows = _rows_by_id(report)
    for scene_id in ("lowerdir", "upper", "worker"):
        steps = mix_steps_for_scene(scene_id)
        step, family, prev = steps[-1]
        if prev != 0 or family == 0:
            continue
        packed = int(rows[scene_id]["facet_hex"], 16)
        if packed >> 32 == 0:
            raise AssertionError(f"{scene_id} lost high lineage bits in facet_hex")


def test_t23_worker_pair() -> None:
    """Worker mirror pair stays coherent when bind path preserves full lane width."""
    report = _build_and_run()
    rows = _rows_by_id(report)
    for field in ("facet_hex", "span_rc", "hop_rc", "mark_rc"):
        if rows["worker"][field] != rows["worker_echo"][field]:
            raise AssertionError(f"worker mirror mismatch on {field}")
    if rows["worker"]["facet_hex"] != expected_facet_for_scene("worker"):
        raise AssertionError("worker facet_hex mismatch")


def test_t26_flip_e() -> None:
    """Truncating bind fold width breaks echo pairing even when reducer is fixed."""
    with _patched_text(BIND_STEP, BROKEN_BIND):
        report = _build_and_run()
    _assert_not_fully_coherent(report)
