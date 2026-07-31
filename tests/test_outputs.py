from __future__ import annotations

import json
import subprocess
from contextlib import contextmanager
from pathlib import Path

APP = Path("/app")
SCAN_OUT = APP / "output" / "inv_scan.tsv"
MERGED_OUT = APP / "output" / "merged.tsv"
REPORT_OUT = APP / "output" / "inventory_report.json"
LED = APP / "data" / "led_rows.tsv"
GEN = APP / "data" / "gen_sheet.dat"
MESH = APP / "etc" / "mesh_table.tsv"
RANK = APP / "docs" / "rank_buried.txt"
DIRECT = APP / "etc" / "frags" / "direct.list"
INDIRECT = APP / "etc" / "frags" / "indirect.list"
T4 = APP / "s2" / "q6" / "exec" / "t4_scan.sh"
W2 = APP / "m8" / "t1" / "lib" / "w2_merge.sh"
K9 = APP / "v3" / "d4" / "lib" / "k9_phase.sh"

BROKEN_T4 = r'''#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "$ROOT/lib/common.sh"
# shellcheck source=/dev/null
source "$ROOT/lib/name_list.sh"

op_t4() {
  local led_path="$1"
  local mesh_path="$2"
  local out_path="$3"
  name_list /app/etc/frags >/dev/null
  {
    printf 'lane\tedition\tmark\n'
    awk 'NR>1 {print $1 "\t" $2 "\t" $3}' "$led_path"
  } > "$out_path"
  mesh_stamp_for "noop" "$mesh_path" >/dev/null || true
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  mkdir -p "$(dirname "$3")"
  op_t4 "$1" "$2" "$3"
fi
'''

BROKEN_W2 = r'''#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source "$ROOT/lib/table_io.sh"
# shellcheck source=/dev/null
source "$ROOT/lib/lane_fold.sh"

fn_w2() {
  local direct_path="$1"
  local indirect_path="$2"
  local rank_path="$3"
  local out_path="$4"
  lane_fold "$rank_path" >/dev/null
  {
    printf 'lane\tedition\tlayer\n'
    declare -A seen=()
    while IFS=$'\t' read -r k v; do
      [ -z "$k" ] && continue
      printf '%s\t%s\tdirect\n' "$k" "$v"
      seen["$k"]=1
    done < <(load_frag_map "$direct_path")
    while IFS=$'\t' read -r k v; do
      [ -z "$k" ] && continue
      if [ -z "${seen[$k]:-}" ]; then
        printf '%s\t%s\tindirect\n' "$k" "$v"
      fi
    done < <(load_frag_map "$indirect_path")
  } > "$out_path"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  fn_w2 "$1" "$2" "$3" "$4"
fi
'''

BROKEN_K9 = r'''#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=/dev/null
source /app/s2/q6/lib/common.sh
# shellcheck source=/dev/null
source "$ROOT/lib/json_emit.sh"
# shellcheck source=/dev/null
source "$ROOT/lib/tree_pretty.sh"

phase_k9() {
  local table_path="$1"
  local gen_path="$2"
  local mesh_path="$3"
  local out_json="$4"
  tree_pretty "$mesh_path" >/dev/null
  printf '{' > "$out_json"
  local args=()
  while IFS=$'\t' read -r lane edition layer; do
    [ -z "$lane" ] && continue
    [ "$lane" = "lane" ] && continue
    local pick stamp dig
    pick="$(awk -v p="$lane" 'NR>1 && $1==p && $3=="live" {print $2; exit}' /app/data/led_rows.tsv)"
    if [ -z "$pick" ]; then
      pick="$edition"
    fi
    stamp="$(mesh_stamp_for "$pick" "$mesh_path")"
    dig="$(digest16 "$lane" "$pick" "$stamp")"
    args+=("$lane" "$stamp" "$dig" "$pick")
  done < "$table_path"
  emit_rows_json "$out_json" "${args[@]}"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  phase_k9 "$1" "$2" "$3" "$4"
fi
'''


def inventory_digest(lane_id: str, selected_edition: str, edition_stamp: str) -> str:
    script = (
        "source /app/s2/q6/lib/common.sh; "
        f'digest16 "{lane_id}" "{selected_edition}" "{edition_stamp}"'
    )
    return subprocess.check_output(["bash", "-c", script], text=True).strip()


def gen_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in GEN.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        lane, edition, _gen = line.split("|")
        out[lane] = edition
    return out


def mesh_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in MESH.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        host, stamp = line.split("\t")
        out[host] = stamp
    return out


def rank_weights() -> dict[str, int]:
    out: dict[str, int] = {}
    for line in RANK.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, weight = line.split()
        out[name] = int(weight)
    return out


def run_scan() -> None:
    SCAN_OUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "bash",
            "/app/s2/q6/exec/t4_scan.sh",
            "/app/data/led_rows.tsv",
            "/app/etc/mesh_table.tsv",
            "/app/output/inv_scan.tsv",
        ],
        check=True,
        cwd=APP,
    )


def run_merge() -> None:
    MERGED_OUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "bash",
            "/app/m8/t1/exec/w2_run.sh",
            "/app/etc/frags/direct.list",
            "/app/etc/frags/indirect.list",
            "/app/docs/rank_buried.txt",
            "/app/output/merged.tsv",
        ],
        check=True,
        cwd=APP,
    )


def run_batch() -> dict:
    subprocess.run(
        ["bash", "/app/scripts/run_batch.sh"],
        check=True,
        cwd=APP,
    )
    return json.loads(REPORT_OUT.read_text(encoding="utf-8"))


def load_scan_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in SCAN_OUT.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        lane, edition, mark = line.split("\t")
        rows.append({"lane": lane, "edition": edition, "mark": mark})
    return rows


def load_merged() -> dict[str, tuple[str, str]]:
    rows: dict[str, tuple[str, str]] = {}
    for line in MERGED_OUT.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        lane, edition, layer = line.split("\t")
        rows[lane] = (edition, layer)
    return rows


def report_row(data: dict, lane_id: str) -> dict:
    for row in data["rows"]:
        if row["lane_id"] == lane_id:
            return row
    raise AssertionError(f"missing lane {lane_id}")


@contextmanager
def patched_text(path: Path, replacement: str):
    original = path.read_text(encoding="utf-8")
    path.write_text(replacement, encoding="utf-8")
    try:
        yield
    finally:
        path.write_text(original, encoding="utf-8")


def test_x9_q01_shape() -> None:
    """Scan table rows expose lane, edition, and mark columns used by later stages."""
    run_scan()
    rows = load_scan_rows()
    assert rows
    for row in rows:
        assert "lane" in row and "edition" in row and "mark" in row
        assert row["mark"] in {"live", "tomb"}


def test_x9_q02_c2() -> None:
    """Effective c2 scan marks align with generation-stamped live editions."""
    run_scan()
    rows = [r for r in load_scan_rows() if r["lane"] == "c2"]
    live = {r["edition"] for r in rows if r["mark"] == "live"}
    tomb = {r["edition"] for r in rows if r["mark"] == "tomb"}
    want = gen_map()["c2"]
    led_eds = [
        line.split("\t")[1]
        for line in LED.read_text(encoding="utf-8").splitlines()[1:]
        if line.startswith("c2\t")
    ]
    stale = next(h for h in led_eds if h != want)
    assert want in live
    assert stale in tomb
    assert stale not in live


def test_x9_q05_tomb() -> None:
    """Retired editions remain visible as tomb marks for later emit stages."""
    run_scan()
    want = gen_map()
    for lane, edition, mark in (
        (r["lane"], r["edition"], r["mark"]) for r in load_scan_rows()
    ):
        if lane in want and edition != want[lane]:
            assert mark == "tomb"
    assert any(r["mark"] == "tomb" for r in load_scan_rows())


def test_x9_a01_flip_s2() -> None:
    """Reverting the s2 scan module collapses effective-ledger tomb alignment."""
    want = gen_map()["c2"]
    led_eds = [
        line.split("\t")[1]
        for line in LED.read_text(encoding="utf-8").splitlines()[1:]
        if line.startswith("c2\t")
    ]
    stale = next(h for h in led_eds if h != want)
    with patched_text(T4, BROKEN_T4):
        run_scan()
        rows = [r for r in load_scan_rows() if r["lane"] == "c2"]
        live = {r["edition"] for r in rows if r["mark"] == "live"}
        assert stale in live
    run_scan()
    rows = [r for r in load_scan_rows() if r["lane"] == "c2"]
    live = {r["edition"] for r in rows if r["mark"] == "live"}
    assert want in live
    assert stale not in live


def test_x9_q03_r7() -> None:
    """Merged r7 edition follows the higher-weight fragment layer."""
    run_merge()
    edition, layer = load_merged()["r7"]
    assert edition == gen_map()["r7"]
    weights = rank_weights()
    winner = max(weights, key=weights.get)
    assert layer == winner


def test_x9_q04_clash() -> None:
    """Overlapping keys resolve to a single merged edition per lane."""
    run_merge()
    merged = load_merged()
    want = gen_map()
    assert set(merged.keys()) == set(want.keys())
    for lane, edition in want.items():
        assert merged[lane][0] == edition
    direct_eds = {
        line.split("\t")[0]: line.split("\t")[1]
        for line in DIRECT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    for lane in want:
        assert merged[lane][0] != direct_eds[lane]


def test_x9_q08_layer_order() -> None:
    """Layer labels on merged rows follow buried weight ordering."""
    run_merge()
    merged = load_merged()
    winner = max(rank_weights(), key=rank_weights().get)
    for lane in gen_map():
        assert merged[lane][1] == winner


def test_x9_a02_flip_m8() -> None:
    """Reverting the m8 merge module prefers lower-weight editions on clash."""
    direct_eds = {
        line.split("\t")[0]: line.split("\t")[1]
        for line in DIRECT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    loser = min(rank_weights(), key=rank_weights().get)
    winner = max(rank_weights(), key=rank_weights().get)
    with patched_text(W2, BROKEN_W2):
        run_merge()
        merged = load_merged()
        assert merged["c2"][0] == direct_eds["c2"]
        assert merged["c2"][1] == loser
    run_merge()
    merged = load_merged()
    assert merged["c2"][0] == gen_map()["c2"]
    assert merged["c2"][1] == winner


def test_x9_q06_twice() -> None:
    """Consecutive full harness runs produce identical inventory reports."""
    first = run_batch()
    second = run_batch()
    assert first == second


def test_x9_q07_tomb_clear() -> None:
    """Selected editions never include rows marked tomb in the scan inventory."""
    run_scan()
    tombs = {r["edition"] for r in load_scan_rows() if r["mark"] == "tomb"}
    data = run_batch()
    for row in data["rows"]:
        assert row["selected_edition"] not in tombs


def test_x9_q09_alt_pick() -> None:
    """Generation sheet editions win over first-live ledger picks in the inventory report."""
    data = run_batch()
    stamps = mesh_map()
    want = gen_map()
    for lane, edition in want.items():
        row = report_row(data, lane)
        assert row["selected_edition"] == edition
        assert row["edition_stamp"] == stamps[edition]
        assert row["inventory_digest"] == inventory_digest(lane, edition, stamps[edition])
    led_first_live = next(
        parts[1]
        for line in LED.read_text(encoding="utf-8").splitlines()[1:]
        for parts in [line.split("\t")]
        if parts and parts[0] == "c2" and parts[-1] == "live"
    )
    assert report_row(data, "c2")["selected_edition"] != led_first_live


def test_x9_a03_flip_v3() -> None:
    """Reverting the v3 emit module reintroduces first-live ledger editions."""
    led_first_live = next(
        parts[1]
        for line in LED.read_text(encoding="utf-8").splitlines()[1:]
        for parts in [line.split("\t")]
        if parts and parts[0] == "c2" and parts[-1] == "live"
    )
    with patched_text(K9, BROKEN_K9):
        data = run_batch()
        assert report_row(data, "c2")["selected_edition"] == led_first_live
    data = run_batch()
    assert report_row(data, "c2")["selected_edition"] == gen_map()["c2"]
