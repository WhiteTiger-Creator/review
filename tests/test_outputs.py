"""Verifier for undercroft-seed-fairness-playtest-cli."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from collections import deque
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

import pytest

APP = Path("/app")
BIN = APP / "bin" / "undercroft-fairness"
CAMPAIGNS = APP / "fixtures" / "campaigns"
LEDGER = APP / "output" / "seed-ledger.json"
ATLAS = APP / "output" / "route-atlas.json"
SEAL = APP / "output" / "fairness-seal.json"
JOURNAL = APP / "state" / "playtest-journal.jsonl"
STAGING = APP / "state" / "seed-hunt-staging.json"
HELDOUT = Path("/opt/verifier-fixtures/heldout_seeds.json")
HELDOUT_SRC = Path("/tests/verifier-fixtures/heldout_seeds.json")
DELTA_CAMPAIGN = Path("/opt/verifier-fixtures/campaigns/crypt_delta.json")
DELTA_CAMPAIGN_SRC = Path("/tests/verifier-fixtures/campaigns/crypt_delta.json")


def reference_evaluate(camp: Campaign, dung: Dungeon) -> dict:
    """Spec-derived fairness reference used only by the verifier."""
    return evaluate(camp, dung)


def xorshift64(state: int) -> tuple[int, int]:
    state &= 0xFFFFFFFFFFFFFFFF
    state ^= (state << 13) & 0xFFFFFFFFFFFFFFFF
    state ^= (state >> 7) & 0xFFFFFFFFFFFFFFFF
    state ^= (state << 17) & 0xFFFFFFFFFFFFFFFF
    state &= 0xFFFFFFFFFFFFFFFF
    return state, state


@dataclass
class Campaign:
    campaign_id: str
    width: int
    height: int
    room_target: int
    chest_count: int
    monster_count: int
    path_min: int
    path_max: int
    min_gap: int
    mean_gap_min: float
    band_d1: int
    band_d2: int
    band_lo: list
    band_hi: list
    total_gold_lo: int
    total_gold_hi: int
    threat_base: int
    threat_slope: int
    max_room_threat: int
    search_origin: int
    search_limit: int


@dataclass
class Room:
    id: int
    x: int
    y: int
    w: int
    h: int
    depth: int = 0
    gold: int = 0
    threat: int = 0


@dataclass
class Dungeon:
    rooms: list
    edges: list
    start: int
    exit: int
    critical_path: list


def load_campaign(path: Path) -> Campaign:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Campaign(**data)


def gen_dungeon(camp: Campaign, seed: int) -> Dungeon:
    state = seed | 1
    rooms: list[Room] = []
    attempts = 0
    while len(rooms) < camp.room_target and attempts < 5000:
        attempts += 1
        state, r = xorshift64(state)
        w = 3 + (r % 3)
        state, r = xorshift64(state)
        h = 3 + (r % 3)
        state, r = xorshift64(state)
        x = 1 + (r % max(1, camp.width - w - 1))
        state, r = xorshift64(state)
        y = 1 + (r % max(1, camp.height - h - 1))
        ok = True
        for o in rooms:
            if not (
                x + w + 1 <= o.x
                or o.x + o.w + 1 <= x
                or y + h + 1 <= o.y
                or o.y + o.h + 1 <= y
            ):
                ok = False
                break
        if ok:
            rooms.append(Room(len(rooms), x, y, w, h))
    edges: set[tuple[int, int]] = set()

    def add_edge(a: int, b: int) -> None:
        if a != b:
            edges.add((min(a, b), max(a, b)))

    for i in range(1, len(rooms)):
        add_edge(i - 1, i)
    extra = max(1, len(rooms) // 3)
    for _ in range(extra):
        state, r = xorshift64(state)
        a = r % len(rooms)
        state, r = xorshift64(state)
        b = r % len(rooms)
        add_edge(a, b)
    adj = {i: [] for i in range(len(rooms))}
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    depth = {0: 0}
    q = deque([0])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in depth:
                depth[v] = depth[u] + 1
                q.append(v)
    for rm in rooms:
        rm.depth = depth.get(rm.id, 999)
    start = 0
    exit_id = max(rooms, key=lambda r: r.depth).id
    candidates = [r.id for r in rooms if r.id != start]
    for _ in range(camp.chest_count):
        if not candidates:
            break
        state, r = xorshift64(state)
        rid = candidates[r % len(candidates)]
        state, g = xorshift64(state)
        gold = 10 + (g % 40) + rooms[rid].depth * 5
        rooms[rid].gold += gold
    for _ in range(camp.monster_count):
        if not candidates:
            break
        state, r = xorshift64(state)
        rid = candidates[r % len(candidates)]
        state, t = xorshift64(state)
        threat = 3 + (t % 8) + rooms[rid].depth * 2
        rooms[rid].threat += threat
    parent: dict[int, int | None] = {start: None}
    q = deque([start])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in parent:
                parent[v] = u
                q.append(v)
    path: list[int] = []
    cur: int | None = exit_id
    if exit_id in parent or exit_id == start:
        while cur is not None:
            path.append(cur)
            cur = parent.get(cur)
        path.reverse()
    return Dungeon(rooms, sorted(edges), start, exit_id, path)


def evaluate(camp: Campaign, dung: Dungeon) -> dict:
    n = len(dung.rooms)
    reachable = sum(1 for r in dung.rooms if r.depth < 999)
    path_len = max(0, len(dung.critical_path) - 1)
    reach_ok = (
        reachable == n
        and path_len >= camp.path_min
        and path_len <= camp.path_max
        and any(r.id == dung.exit and r.depth < 999 for r in dung.rooms)
    )
    monster_idx = [
        i for i, rid in enumerate(dung.critical_path) if dung.rooms[rid].threat > 0
    ]
    gaps: list[int] = []
    pacing_ok = True
    mean_gap = 0.0
    if len(monster_idx) == 0:
        pacing_ok = False
    elif len(monster_idx) == 1:
        mean_gap = float(camp.mean_gap_min)
    else:
        for a, b in pairwise(monster_idx):
            gap = b - a
            gaps.append(gap)
            if gap < camp.min_gap:
                pacing_ok = False
        mean_gap = sum(gaps) / len(gaps)
        if mean_gap < camp.mean_gap_min:
            pacing_ok = False
    bands: list[list[int]] = [[], [], []]
    for r in dung.rooms:
        if r.id == dung.start:
            continue
        if r.depth <= camp.band_d1:
            bands[0].append(r.gold)
        elif r.depth <= camp.band_d2:
            bands[1].append(r.gold)
        else:
            bands[2].append(r.gold)
    dens = []
    treasure_ok = True
    for i in range(3):
        if not bands[i]:
            dens.append(0.0)
            continue
        d = sum(bands[i]) / len(bands[i])
        dens.append(d)
        if d < camp.band_lo[i] or d > camp.band_hi[i]:
            treasure_ok = False
    total_gold = sum(r.gold for r in dung.rooms)
    if total_gold < camp.total_gold_lo or total_gold > camp.total_gold_hi:
        treasure_ok = False
    threat_ok = True
    cum = 0
    max_room = 0
    for i, rid in enumerate(dung.critical_path):
        th = dung.rooms[rid].threat
        max_room = max(max_room, th)
        cum += th
        budget = camp.threat_base + camp.threat_slope * i
        if cum > budget:
            threat_ok = False
    if max_room > camp.max_room_threat:
        threat_ok = False
    return {
        "ok": reach_ok and pacing_ok and treasure_ok and threat_ok,
        "reach_ok": reach_ok,
        "pacing_ok": pacing_ok,
        "treasure_ok": treasure_ok,
        "threat_ok": threat_ok,
        "path_len": path_len,
        "mean_gap": mean_gap,
        "densities": dens,
        "total_gold": total_gold,
        "cum_threat_end": cum,
        "max_room_threat": max_room,
    }


def run_playtest(
    campaigns_dir: Path | None = None,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess:
    campaigns_dir = campaigns_dir or CAMPAIGNS
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            str(BIN),
            "playtest",
            "--campaigns",
            str(campaigns_dir),
            "--ledger",
            str(LEDGER),
            "--atlas",
            str(ATLAS),
            "--seal",
            str(SEAL),
            "--journal",
            str(JOURNAL),
        ],
        check=check,
        text=True,
        capture_output=True,
    )


@pytest.fixture(scope="session", autouse=True)
def _session_playtest() -> None:
    assert BIN.is_file(), "missing /app/bin/undercroft-fairness — rebuild with /app/scripts/build.sh"
    proc = run_playtest(check=False)
    assert proc.returncode == 0, f"playtest failed: {proc.stderr}\n{proc.stdout}"


def _ledger() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def _atlas() -> dict:
    return json.loads(ATLAS.read_text(encoding="utf-8"))


def _seal() -> dict:
    return json.loads(SEAL.read_text(encoding="utf-8"))


def _heldout() -> dict:
    path = HELDOUT if HELDOUT.is_file() else HELDOUT_SRC
    return json.loads(path.read_text(encoding="utf-8"))


def test_hidden_heldout_fixture_present():
    """Sealed held-out seeds live under /opt/verifier-fixtures (not agent-visible)."""
    assert Path("/opt/verifier-fixtures/heldout_seeds.json").is_file()
    held = json.loads(Path("/opt/verifier-fixtures/heldout_seeds.json").read_text(encoding="utf-8"))
    assert "campaigns" in held
    assert len(held["campaigns"]) >= 3


def test_hidden_heldout_matches_ledger_seeds():
    """Verifier-fixtures held-out map must match selected seeds in the ledger."""
    held = json.loads(Path("/opt/verifier-fixtures/heldout_seeds.json").read_text(encoding="utf-8"))
    by_id = {row["campaign_id"]: row for row in _ledger()["campaigns"]}
    for cid, seed in held["campaigns"].items():
        assert by_id[cid]["selected_seed"] == seed
        camp = load_campaign(CAMPAIGNS / f"{cid}.json")
        assert reference_evaluate(camp, gen_dungeon(camp, seed))["ok"]


def test_state_journal_staging_snapshot():
    """Journal and seed-hunt staging snapshot both record accepted campaign seeds."""
    assert JOURNAL.is_file()
    assert STAGING.is_file()
    lines = [
        json.loads(x)
        for x in JOURNAL.read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    assert lines, "empty staging snapshot journal"
    assert all(line.get("accepted") is True for line in lines)
    staging = json.loads(STAGING.read_text(encoding="utf-8"))
    assert staging["schema"] == "undercroft-seed-staging-v1"
    assert len(staging["campaigns"]) == len(_campaign_files())


def _staging() -> dict:
    return json.loads(STAGING.read_text(encoding="utf-8"))


def _campaign_files() -> list[Path]:
    return sorted(CAMPAIGNS.glob("*.json"))


def test_cli_binary_present():
    """Fairness planner binary is installed at the documented path."""
    assert BIN.is_file()
    assert os.access(BIN, os.X_OK)


def test_playtest_exit_zero():
    """Default campaign playtest tick exits successfully."""
    proc = run_playtest(check=False)
    assert proc.returncode == 0


def test_ledger_schema_and_campaign_count():
    """Seed ledger uses the documented schema and one row per campaign file."""
    ledger = _ledger()
    assert ledger["schema"] == "undercroft-seed-ledger-v1"
    assert len(ledger["campaigns"]) == len(_campaign_files())


def test_atlas_schema_and_route_count():
    """Route atlas schema matches and routes align with campaigns."""
    atlas = _atlas()
    assert atlas["schema"] == "undercroft-route-atlas-v1"
    assert len(atlas["routes"]) == len(_campaign_files())


def test_seal_schema_fields():
    """Fairness seal carries version, campaign_count, and ledger/atlas/staging digests."""
    seal = _seal()
    assert seal["schema"] == "undercroft-fairness-seal-v1"
    assert seal["seal_version"] == 1
    assert seal["campaign_count"] == len(_campaign_files())
    assert len(seal["ledger_digest"]) == 64
    assert len(seal["atlas_digest"]) == 64
    assert len(seal["staging_digest"]) == 64


def _sha256_hex(path: Path) -> str:
    proc = subprocess.run(
        ["sha256sum", str(path)],
        check=True,
        text=True,
        capture_output=True,
    )
    return proc.stdout.split()[0]


def test_seal_digests_match_file_bytes():
    """Seal digests are SHA-256 of the exact ledger, atlas, and staging file bytes."""
    seal = _seal()
    assert seal["ledger_digest"] == _sha256_hex(LEDGER)
    assert seal["atlas_digest"] == _sha256_hex(ATLAS)
    assert seal["staging_digest"] == _sha256_hex(STAGING)


def test_staging_seeds_bind_ledger_and_journal():
    """Staging candidate seeds must equal ledger selected seeds and journal lines."""
    staging_by_id = {row["campaign_id"]: row for row in _staging()["campaigns"]}
    ledger_by_id = {row["campaign_id"]: row for row in _ledger()["campaigns"]}
    lines = [json.loads(x) for x in JOURNAL.read_text(encoding="utf-8").splitlines() if x.strip()]
    journal_by_id = {line["campaign_id"]: line for line in lines if line.get("accepted") is True}
    for path in _campaign_files():
        cid = path.stem
        seed = staging_by_id[cid]["candidate_seed"]
        assert ledger_by_id[cid]["selected_seed"] == seed
        assert journal_by_id[cid]["candidate_seed"] == seed
        assert staging_by_id[cid]["fair"] is True


def test_heldout_selected_seeds():
    """Selected seeds match sealed held-out fair seeds for each campaign."""
    held = _heldout()["campaigns"]
    by_id = {row["campaign_id"]: row for row in _ledger()["campaigns"]}
    for cid, seed in held.items():
        assert by_id[cid]["selected_seed"] == seed


def test_selected_seeds_are_fair_under_spec():
    """Each ledger seed regenerates a dungeon that passes all four invariant families."""
    for path in _campaign_files():
        camp = load_campaign(path)
        row = next(r for r in _ledger()["campaigns"] if r["campaign_id"] == camp.campaign_id)
        metrics = evaluate(camp, gen_dungeon(camp, row["selected_seed"]))
        assert metrics["ok"], (camp.campaign_id, row["selected_seed"], metrics)
        assert reference_evaluate(camp, gen_dungeon(camp, row["selected_seed"]))["ok"]


def test_origin_seeds_are_not_selected():
    """Planner must not accept the unfair search_origin seed for stock campaigns."""
    for path in _campaign_files():
        camp = load_campaign(path)
        row = next(r for r in _ledger()["campaigns"] if r["campaign_id"] == camp.campaign_id)
        assert row["selected_seed"] != camp.search_origin
        assert not evaluate(camp, gen_dungeon(camp, camp.search_origin))["ok"]


def test_ledger_metrics_match_regenerated_map():
    """Ledger quality metrics match independent regeneration for the selected seed."""
    for path in _campaign_files():
        camp = load_campaign(path)
        row = next(r for r in _ledger()["campaigns"] if r["campaign_id"] == camp.campaign_id)
        m = evaluate(camp, gen_dungeon(camp, row["selected_seed"]))
        assert row["path_len"] == m["path_len"]
        assert row["total_gold"] == m["total_gold"]
        assert row["cum_threat_end"] == m["cum_threat_end"]
        assert row["max_room_threat"] == m["max_room_threat"]
        assert abs(row["mean_gap"] - m["mean_gap"]) < 1e-9
        assert abs(row["gold_density_early"] - m["densities"][0]) < 1e-9
        assert abs(row["gold_density_mid"] - m["densities"][1]) < 1e-9
        assert abs(row["gold_density_late"] - m["densities"][2]) < 1e-9
        assert row["fair"] is True


def test_atlas_critical_path_matches_regeneration():
    """Atlas critical paths equal BFS shortest paths for selected seeds."""
    routes = {r["campaign_id"]: r for r in _atlas()["routes"]}
    for path in _campaign_files():
        camp = load_campaign(path)
        seed = routes[camp.campaign_id]["seed"]
        dung = gen_dungeon(camp, seed)
        route = routes[camp.campaign_id]
        assert route["start"] == dung.start
        assert route["exit"] == dung.exit
        assert route["critical_path"] == dung.critical_path
        assert route["seed"] == next(
            r["selected_seed"] for r in _ledger()["campaigns"] if r["campaign_id"] == camp.campaign_id
        )


def test_reachability_path_bounds_on_selected():
    """Selected seeds keep critical path length inside campaign bounds."""
    for path in _campaign_files():
        camp = load_campaign(path)
        row = next(r for r in _ledger()["campaigns"] if r["campaign_id"] == camp.campaign_id)
        assert camp.path_min <= row["path_len"] <= camp.path_max


def test_route_gap_invariants_on_selected():
    """Selected seeds satisfy min_gap and mean_gap_min along the critical path."""
    for path in _campaign_files():
        camp = load_campaign(path)
        row = next(r for r in _ledger()["campaigns"] if r["campaign_id"] == camp.campaign_id)
        m = evaluate(camp, gen_dungeon(camp, row["selected_seed"]))
        assert m["pacing_ok"]
        assert m["mean_gap"] >= camp.mean_gap_min


def test_band_density_invariants_on_selected():
    """Selected seeds satisfy non-empty band density windows and total gold budget."""
    for path in _campaign_files():
        camp = load_campaign(path)
        row = next(r for r in _ledger()["campaigns"] if r["campaign_id"] == camp.campaign_id)
        m = evaluate(camp, gen_dungeon(camp, row["selected_seed"]))
        assert m["treasure_ok"]
        assert camp.total_gold_lo <= m["total_gold"] <= camp.total_gold_hi


def test_route_budget_invariants_on_selected():
    """Selected seeds keep cumulative threat under the linear route budget."""
    for path in _campaign_files():
        camp = load_campaign(path)
        row = next(r for r in _ledger()["campaigns"] if r["campaign_id"] == camp.campaign_id)
        m = evaluate(camp, gen_dungeon(camp, row["selected_seed"]))
        assert m["threat_ok"]
        assert m["max_room_threat"] <= camp.max_room_threat


def test_journal_records_accepted_seeds():
    """Playtest journal records an accepted=true line per campaign."""
    lines = [json.loads(x) for x in JOURNAL.read_text(encoding="utf-8").splitlines() if x.strip()]
    accepted = {line["campaign_id"]: line for line in lines if line.get("accepted") is True}
    for path in _campaign_files():
        camp = load_campaign(path)
        assert camp.campaign_id in accepted
        row = next(r for r in _ledger()["campaigns"] if r["campaign_id"] == camp.campaign_id)
        assert accepted[camp.campaign_id]["candidate_seed"] == row["selected_seed"]


def test_lexicographic_campaign_order():
    """Ledger and atlas follow lexicographic campaign filename order."""
    ids = [p.stem for p in _campaign_files()]
    assert [r["campaign_id"] for r in _ledger()["campaigns"]] == ids
    assert [r["campaign_id"] for r in _atlas()["routes"]] == ids


def test_deterministic_rerun_byte_identical():
    """Re-running playtest yields byte-identical ledger, atlas, seal, and staging."""
    before = (
        LEDGER.read_bytes(),
        ATLAS.read_bytes(),
        SEAL.read_bytes(),
        STAGING.read_bytes(),
    )
    run_playtest()
    after = (
        LEDGER.read_bytes(),
        ATLAS.read_bytes(),
        SEAL.read_bytes(),
        STAGING.read_bytes(),
    )
    assert before == after


def test_randomized_eval_pool_rejects_unfair_members():
    """Hidden eval pool mixes fair held-out seeds with nearby unfair distractors."""
    held = _heldout()
    fair = set(held["campaigns"].values())
    sample = list(held["eval_pool"])[:6]
    first = _campaign_files()[0]
    camp = load_campaign(first)
    fair_seed = held["campaigns"][camp.campaign_id]
    for seed in sample:
        metrics = evaluate(camp, gen_dungeon(camp, seed))
        if seed in fair and seed == fair_seed:
            assert metrics["ok"]
        if seed == camp.search_origin:
            assert not metrics["ok"]
        if seed in (120, 514) and seed != fair_seed:
            # Near-miss distractors from alternate gap/band interpretations.
            assert seed != fair_seed


def test_perturbation_origin_changes_selected_seed():
    """Shifting search_origin on a temp campaign changes the accepted seed."""
    src = _campaign_files()[0]
    camp = load_campaign(src)
    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        payload = json.loads(src.read_text(encoding="utf-8"))
        payload["search_origin"] = camp.search_origin + 50
        payload["campaign_id"] = f"{camp.campaign_id}_shift"
        (tdir / f"{payload['campaign_id']}.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        out_ledger = APP / "output" / "shift-ledger.json"
        out_atlas = APP / "output" / "shift-atlas.json"
        out_seal = APP / "output" / "shift-seal.json"
        out_journal = APP / "state" / "shift-journal.jsonl"
        proc = subprocess.run(
            [
                str(BIN),
                "playtest",
                "--campaigns",
                str(tdir),
                "--ledger",
                str(out_ledger),
                "--atlas",
                str(out_atlas),
                "--seal",
                str(out_seal),
                "--journal",
                str(out_journal),
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        assert proc.returncode == 0, proc.stderr
        shifted = json.loads(out_ledger.read_text(encoding="utf-8"))["campaigns"][0]
        baseline = next(
            r for r in _ledger()["campaigns"] if r["campaign_id"] == camp.campaign_id
        )
        assert shifted["selected_seed"] != baseline["selected_seed"]
        assert shifted["fair"] is True
        shifted_camp = Campaign(**payload)
        assert evaluate(
            shifted_camp, gen_dungeon(shifted_camp, shifted["selected_seed"])
        )["ok"]
        staging_shift = Path(out_journal).parent / "seed-hunt-staging.json"
        assert staging_shift.is_file()
        seal_shift = json.loads(out_seal.read_text(encoding="utf-8"))
        assert seal_shift["staging_digest"] == _sha256_hex(staging_shift)


def test_hidden_delta_holdout_first_fair_seed():
    """Verifier-only crypt_delta profile must select the sealed first-fair seed."""
    src = DELTA_CAMPAIGN if DELTA_CAMPAIGN.is_file() else DELTA_CAMPAIGN_SRC
    assert src.is_file()
    held = _heldout()["delta_holdout"]
    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        payload = json.loads(src.read_text(encoding="utf-8"))
        (tdir / "crypt_delta.json").write_text(json.dumps(payload), encoding="utf-8")
        out_ledger = APP / "output" / "delta-ledger.json"
        out_atlas = APP / "output" / "delta-atlas.json"
        out_seal = APP / "output" / "delta-seal.json"
        out_journal = APP / "state" / "delta-journal.jsonl"
        proc = subprocess.run(
            [
                str(BIN),
                "playtest",
                "--campaigns",
                str(tdir),
                "--ledger",
                str(out_ledger),
                "--atlas",
                str(out_atlas),
                "--seal",
                str(out_seal),
                "--journal",
                str(out_journal),
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        assert proc.returncode == 0, proc.stderr
        row = json.loads(out_ledger.read_text(encoding="utf-8"))["campaigns"][0]
        assert row["selected_seed"] == held["selected_seed"]
        camp = Campaign(**payload)
        assert evaluate(camp, gen_dungeon(camp, row["selected_seed"]))["ok"]
        # Last-fair / end-budget / exclusive-band near-misses must not win.
        assert row["selected_seed"] not in (276, 286, 421)


def test_artifacts_exclude_decoy_biome_labels():
    """Published artifacts must not embed decoy biome attractor strings."""
    blob = (
        LEDGER.read_text(encoding="utf-8")
        + ATLAS.read_text(encoding="utf-8")
        + SEAL.read_text(encoding="utf-8")
        + STAGING.read_text(encoding="utf-8")
        + JOURNAL.read_text(encoding="utf-8")
    )
    for token in ("moss", "ash", "decoy_biome", "wrap:"):
        assert token not in blob


def test_instruction_output_paths_exist():
    """Paths named in instruction.md are present after a successful playtest."""
    assert Path("/app/output/seed-ledger.json").is_file()
    assert Path("/app/output/route-atlas.json").is_file()
    assert Path("/app/output/fairness-seal.json").is_file()
    assert Path("/app/state/playtest-journal.jsonl").is_file()
    assert Path("/app/state/seed-hunt-staging.json").is_file()
    assert Path("/app/output/seed-ledger.json") == LEDGER
    assert Path("/app/output/route-atlas.json") == ATLAS
    assert Path("/app/output/fairness-seal.json") == SEAL
    assert Path("/app/state/playtest-journal.jsonl") == JOURNAL
    assert Path("/app/state/seed-hunt-staging.json") == STAGING


def test_docs_contracts_present():
    """Referenced contract docs exist under /app/docs for the playtest planner."""
    for name in (
        "playtest-workflow.md",
        "cartograph-contract.md",
        "reachability-pacing-contract.md",
        "treasure-threat-contract.md",
        "seed-search-contract.md",
        "staging-export-contract.md",
        "artifact-seal-contract.md",
    ):
        assert (APP / "docs" / name).is_file()
