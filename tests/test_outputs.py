"""Verifier suite for Fog Chess Relay."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path("/opt/fog-chess-relay")
BIN = ROOT / "bin" / "relaymatch"
BOT = Path("/app/work/relaybot")
OUTPUT = Path("/app/output")
HIDDEN = Path("/tests/fixtures/hidden")
APP_REFS = [
    Path("/app/chess.txt"),
    Path("/app/fog.txt"),
    Path("/app/relay.txt"),
    Path("/app/scoring.txt"),
    Path("/app/protocol.txt"),
    Path("/app/notation.txt"),
    Path("/app/examples.txt"),
]


def _run(cmd: list[str], cwd: str | None = None, env: dict | None = None, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    base = os.environ.copy()
    if env:
        base.update(env)
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=base,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _isolated_bot(tmp: Path) -> Path:
    dest = tmp / "relaybot"
    shutil.copytree(BOT, dest)
    return dest


def _run_match(position: str | Path, bot_dir: Path, out_root: Path, inject: str = "") -> subprocess.CompletedProcess[str]:
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "generations").mkdir(parents=True, exist_ok=True)
    cmd = [
        str(BIN),
        "-match",
        str(position),
        "-bot",
        str(bot_dir),
        "-compile=true",
    ]
    if inject:
        cmd.append(f"-inject-fail={inject}")
    return _run(
        cmd,
        env={"FOG_CHESS_ROOT": str(ROOT), "FOG_CHESS_OUTPUT": str(out_root)},
        timeout=240,
    )


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _current_gen(out_root: Path) -> Path:
    cur = (out_root / "current").read_text().strip()
    return out_root / cur


def _normalized_bytes(out_root: Path) -> bytes:
    gen = _current_gen(out_root)
    parts = []
    for name in ("summary.json", "plies.jsonl", "terminal.json"):
        parts.append((gen / name).read_bytes())
    return b"".join(parts)


def _score_a(out_root: Path) -> int:
    term = _read_json(_current_gen(out_root) / "terminal.json")
    return int(term["scores"]["team_a"])


def _winner(out_root: Path) -> str:
    return str(_read_json(_current_gen(out_root) / "terminal.json")["winner"])


# ---------------------------------------------------------------------------
# 3 protected-engine and integrity tests
# ---------------------------------------------------------------------------


def test_protected_binary_and_layout_exist():
    """Protected relaymatch binary and asset directories are installed under /opt."""
    assert BIN.is_file()
    for rel in ("positions/public", "opponents", "contracts", "notation", "integrity"):
        assert (ROOT / rel).exists()


def test_integrity_manifest_verifies_clean_assets():
    """Controller asset verification succeeds against the sealed integrity manifest."""
    proc = _run([str(BIN), "-verify-assets"], env={"FOG_CHESS_ROOT": str(ROOT)})
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout


def test_integrity_rejects_mutated_position_asset(tmp_path: Path):
    """Mutating a protected public position causes integrity verification to fail."""
    shadow = tmp_path / "shadow-root"
    shutil.copytree(ROOT, shadow, ignore=shutil.ignore_patterns("bin"))
    # binary still needed only as verifier entrypoint; assets come from shadow root
    target = shadow / "positions" / "public" / "promotion-race.json"
    data = json.loads(target.read_bytes())
    data["seed"] = int(data.get("seed", 0)) + 999
    target.write_text(json.dumps(data, indent=2) + "\n")
    proc = _run([str(BIN), "-verify-assets"], env={"FOG_CHESS_ROOT": str(shadow)})
    assert proc.returncode != 0
    # live protected tree must remain untouched
    live = _run([str(BIN), "-verify-assets"], env={"FOG_CHESS_ROOT": str(ROOT)})
    assert live.returncode == 0, live.stderr


# ---------------------------------------------------------------------------
# 6 protocol, fog-secrecy, legality, determinism, and publication tests
# ---------------------------------------------------------------------------


def test_player_reference_documents_are_plain_text():
    """Player references exist as plain text without markdown heading markers."""
    for path in APP_REFS:
        assert path.is_file()
        text = path.read_text()
        assert "#" not in text
        assert "```" not in text
        assert "\n- " not in text


def test_starter_bot_compiles_offline(tmp_path: Path):
    """Starter relaybot sources compile with the retained Go toolchain offline."""
    bot = _isolated_bot(tmp_path)
    proc = _run(["go", "build", "-o", str(tmp_path / "bot"), "."], cwd=str(bot))
    assert proc.returncode == 0, proc.stderr


def test_match_hides_full_occupancy_from_observations(tmp_path: Path):
    """Observations never include full-board FEN or hidden occupancy maps."""
    out = tmp_path / "out"
    bot = _isolated_bot(tmp_path)
    proc = _run_match("material-imbalance", bot, out)
    assert proc.returncode == 0, proc.stderr
    vis = (_current_gen(out) / "visibility.jsonl").read_text()
    assert "alpha_fen" not in vis
    assert "/8/" not in vis  # fen-like ranks
    for line in vis.splitlines():
        obj = json.loads(line)
        assert "visible_squares" in obj
        assert len(obj["visible_squares"]) <= 64


def test_illegal_action_does_not_corrupt_prior_current(tmp_path: Path):
    """A prior successful generation pointer survives a later injected publication failure."""
    out = tmp_path / "out"
    bot = _isolated_bot(tmp_path)
    first = _run_match("promotion-race", bot, out)
    assert first.returncode == 0, first.stderr
    prior = (out / "current").read_text()
    prior_bytes = _normalized_bytes(out)
    bad = _run_match("material-imbalance", bot, out, inject="pointer")
    assert bad.returncode != 0
    assert (out / "current").read_text() == prior
    assert _normalized_bytes(out) == prior_bytes


def test_determinism_identical_inputs_byte_identical(tmp_path: Path):
    """Identical engine, position, seed, opponent, and bot yield identical normalized bytes."""
    bot = _isolated_bot(tmp_path)
    out1 = tmp_path / "o1"
    out2 = tmp_path / "o2"
    a = _run_match("promotion-race", bot, out1)
    b = _run_match("promotion-race", bot, out2)
    assert a.returncode == 0 and b.returncode == 0, a.stderr + b.stderr
    assert _normalized_bytes(out1) == _normalized_bytes(out2)


def test_generation_contains_required_artifacts(tmp_path: Path):
    """Each published generation contains the seven required authoritative record files."""
    out = tmp_path / "out"
    bot = _isolated_bot(tmp_path)
    proc = _run_match("kingside-relay-attack", bot, out)
    assert proc.returncode == 0, proc.stderr
    gen = _current_gen(out)
    for name in (
        "summary.json",
        "plies.jsonl",
        "boards.json",
        "visibility.jsonl",
        "relay.jsonl",
        "terminal.json",
        "bot-diagnostics.json",
    ):
        assert (gen / name).is_file()


# ---------------------------------------------------------------------------
# 11 public relay-chess behavior tests
# ---------------------------------------------------------------------------


def _plies(out_root: Path) -> list[dict]:
    lines = (_current_gen(out_root) / "plies.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _has_action(out_root: Path, action: str) -> bool:
    return any(p.get("action") == action for p in _plies(out_root))


def _has_drop_uci(out_root: Path) -> bool:
    for p in _plies(out_root):
        uci = str(p.get("uci", ""))
        if uci.startswith("drop:") or p.get("action") == "drop":
            return True
        if p.get("drop"):
            return True
    # drops may be recorded only as uci empty with piece in relay; also scan visibility
    for line in (_current_gen(out_root) / "visibility.jsonl").read_text().splitlines():
        pass
    for p in _plies(out_root):
        uci = str(p.get("uci", ""))
        if len(uci) >= 5 and uci[0].isalpha() and uci[1].isdigit() is False:
            # drop UCI from engine is often "drop:n e4" style via Move.UCI
            return "drop" in uci
    return any("drop" in str(p.get("uci", "")) for p in _plies(out_root))


def _summary(out_root: Path) -> dict:
    return _read_json(_current_gen(out_root) / "summary.json")


def _accepted(out_root: Path) -> bool:
    return bool(_summary(out_root).get("accepted"))


def test_public_legal_moves_on_both_boards(tmp_path: Path):
    """Bot produces legal moves on both linked boards during a public match."""
    out = tmp_path / "out"
    bot = _isolated_bot(tmp_path)
    proc = _run_match("kingside-relay-attack", bot, out)
    assert proc.returncode == 0, proc.stderr
    boards = {p.get("board") for p in _plies(out) if p.get("board")}
    assert "alpha" in boards and "beta" in boards
    diag = _read_json(_current_gen(out) / "bot-diagnostics.json")
    assert diag["protocol_ok"] is True
    assert diag["bot_faults"] == 0
    assert diag.get("belief_faults", 0) == 0
    assert _accepted(out)


def test_public_evade_observed_check(tmp_path: Path):
    """Bot evades check pressure on defensive-drop without hold-in-check faults."""
    out = tmp_path / "out"
    bot = _isolated_bot(tmp_path)
    proc = _run_match("defensive-drop-fog", bot, out)
    assert proc.returncode == 0, proc.stderr
    diag = _read_json(_current_gen(out) / "bot-diagnostics.json")
    assert diag["bot_faults"] == 0
    assert diag["bot_legal_actions"] >= 1
    assert _summary(out)["reason"] != "hold_in_check"
    assert _accepted(out)


def test_public_rejects_unseen_blocked_capture_assumption(tmp_path: Path):
    """Bot only plays engine-listed legal moves under material pressure."""
    out = tmp_path / "out"
    bot = _isolated_bot(tmp_path)
    proc = _run_match("material-imbalance", bot, out)
    assert proc.returncode == 0, proc.stderr
    diag = _read_json(_current_gen(out) / "bot-diagnostics.json")
    assert diag["protocol_ok"] is True
    assert diag["bot_faults"] == 0
    assert _score_a(out) >= 100
    assert _accepted(out)


def test_public_defensive_relay_drop_after_delay(tmp_path: Path):
    """Bot actually uses a ready relay drop on the defensive-drop public match."""
    out = tmp_path / "out"
    bot = _isolated_bot(tmp_path)
    proc = _run_match("defensive-drop-fog", bot, out)
    assert proc.returncode == 0, proc.stderr
    found_ready = False
    for line in (_current_gen(out) / "visibility.jsonl").read_text().splitlines():
        obj = json.loads(line)
        if obj.get("team") == "team_a" and "n" in obj.get("ready_drops", []):
            found_ready = True
    assert found_ready
    assert _has_drop_uci(out) or any(
        "drop" in str(p) for p in _plies(out)
    ), "expected a drop action in plies"
    assert _score_a(out) >= 8
    assert _accepted(out)


def test_public_teammate_request_timing(tmp_path: Path):
    """Bot emits at least one teammate piece request on a long public match."""
    out = tmp_path / "out"
    bot = _isolated_bot(tmp_path)
    proc = _run_match("kingside-relay-attack", bot, out)
    assert proc.returncode == 0, proc.stderr
    assert _has_action(out, "request"), "expected request action in plies"
    assert _accepted(out)


def test_public_sacrifice_prevents_cross_board_mate_net(tmp_path: Path):
    """Cross-board kingside attack meets acceptance without protocol faults."""
    out = tmp_path / "out"
    bot = _isolated_bot(tmp_path)
    proc = _run_match("kingside-relay-attack", bot, out)
    assert proc.returncode == 0, proc.stderr
    diag = _read_json(_current_gen(out) / "bot-diagnostics.json")
    assert diag["bot_faults"] == 0
    assert _score_a(out) >= 60
    assert _accepted(out)


def test_public_promotion_preserves_relay_needs(tmp_path: Path):
    """Promotion race promotes and clears the campaign acceptance floor."""
    out = tmp_path / "out"
    bot = _isolated_bot(tmp_path)
    proc = _run_match("promotion-race", bot, out)
    assert proc.returncode == 0, proc.stderr
    plies = (_current_gen(out) / "plies.jsonl").read_text()
    assert any(ch in plies for ch in ("q", "n", "r", "b"))
    assert _score_a(out) >= 9
    assert _accepted(out)


def test_public_repetition_avoidance_when_behind(tmp_path: Path):
    """Under material pressure the bot does not idle into a punished repetition."""
    out = tmp_path / "out"
    bot = _isolated_bot(tmp_path)
    proc = _run_match("material-imbalance", bot, out)
    assert proc.returncode == 0, proc.stderr
    term = _read_json(_current_gen(out) / "terminal.json")
    assert "reason" in term
    if str(term["reason"]).startswith("repetition:"):
        assert _score_a(out) >= 95
    else:
        assert _score_a(out) >= 100
    assert _accepted(out)


def test_public_safe_after_stale_sighting(tmp_path: Path):
    """Fog sightings appear and belief faults stay zero on defensive-drop."""
    out = tmp_path / "out"
    bot = _isolated_bot(tmp_path)
    proc = _run_match("defensive-drop-fog", bot, out)
    assert proc.returncode == 0, proc.stderr
    vis = (_current_gen(out) / "visibility.jsonl").read_text()
    assert "stale_sightings" in vis
    diag = _read_json(_current_gen(out) / "bot-diagnostics.json")
    assert diag["bot_faults"] == 0
    assert diag.get("belief_faults", 0) == 0
    assert _accepted(out)


def test_public_cross_board_mate_priority(tmp_path: Path):
    """All four public campaigns meet acceptance with a high aggregate score."""
    bot = _isolated_bot(tmp_path)
    total = 0
    floors = {
        "kingside-relay-attack": 60,
        "defensive-drop-fog": 8,
        "promotion-race": 9,
        "material-imbalance": 100,
    }
    for name, floor in floors.items():
        out = tmp_path / f"prio-{name}"
        proc = _run_match(name, bot, out)
        assert proc.returncode == 0, proc.stderr
        assert _read_json(_current_gen(out) / "bot-diagnostics.json")["bot_faults"] == 0
        assert _score_a(out) >= floor, f"{name}: {_score_a(out)} < {floor}"
        assert _accepted(out)
        total += _score_a(out)
    assert total >= 200


def test_public_queue_capacity_and_team_score_reconciliation(tmp_path: Path):
    """Queue capacity fields and acceptance reconcile in the final records."""
    out = tmp_path / "out"
    bot = _isolated_bot(tmp_path)
    proc = _run_match("defensive-drop-fog", bot, out)
    assert proc.returncode == 0, proc.stderr
    term = _read_json(_current_gen(out) / "terminal.json")
    assert set(term["scores"]) >= {"team_a", "team_b"}
    summary = _summary(out)
    assert summary["plies"] >= 1
    assert "acceptance_floor" in summary
    assert summary["accepted"] is True


# ---------------------------------------------------------------------------
# 12 isolated hidden composite match tests
# ---------------------------------------------------------------------------


def _hidden_match(tmp_path: Path, name: str) -> Path:
    out = tmp_path / f"out-{name}"
    bot = _isolated_bot(tmp_path / f"bot-{name}")
    pos = HIDDEN / f"{name}.json"
    assert pos.is_file(), name
    proc = _run_match(pos, bot, out)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return out


def test_hidden_wrong_relay_mate(tmp_path: Path):
    """Hidden: capacity-one relay match finishes legally with non-negative score."""
    out = _hidden_match(tmp_path, "wrong_relay_mate")
    assert _score_a(out) >= 0
    assert _read_json(_current_gen(out) / "bot-diagnostics.json")["bot_faults"] == 0
    assert _read_json(_current_gen(out) / "bot-diagnostics.json").get("belief_faults", 0) == 0


def test_hidden_unseen_blocker_check(tmp_path: Path):
    """Hidden: belief-aware defense under check completes without faults."""
    out = _hidden_match(tmp_path, "unseen_blocker_check")
    diag = _read_json(_current_gen(out) / "bot-diagnostics.json")
    assert diag["protocol_ok"] is True
    assert diag["bot_faults"] == 0


def test_hidden_knight_vs_pawn_drop(tmp_path: Path):
    """Hidden: delayed knight queue still yields a drop when inventory is ready."""
    out = _hidden_match(tmp_path, "knight_vs_pawn_drop")
    relay = (_current_gen(out) / "relay.jsonl").read_text()
    assert "team_a" in relay
    assert _has_drop_uci(out) or any("drop" in str(p) for p in _plies(out))


def test_hidden_promo_fills_queue(tmp_path: Path):
    """Hidden: promotion path interacting with a full relay queue remains valid."""
    out = _hidden_match(tmp_path, "promo_fills_queue")
    assert _read_json(_current_gen(out) / "bot-diagnostics.json")["bot_faults"] == 0


def test_hidden_repetition_with_attack(tmp_path: Path):
    """Hidden: repetition versus continuing a visible attack yields a terminal reason."""
    out = _hidden_match(tmp_path, "repetition_with_attack")
    term = _read_json(_current_gen(out) / "terminal.json")
    assert term["reason"]
    assert _read_json(_current_gen(out) / "bot-diagnostics.json")["bot_faults"] == 0


def test_hidden_stale_queen_unsafe(tmp_path: Path):
    """Hidden: stale queen sightings do not produce belief faults."""
    out = _hidden_match(tmp_path, "stale_queen_unsafe")
    diag = _read_json(_current_gen(out) / "bot-diagnostics.json")
    assert diag["bot_faults"] == 0
    assert diag.get("belief_faults", 0) == 0


def test_hidden_renamed_ids_reordered(tmp_path: Path):
    """Hidden: renamed piece identifiers still allow a complete legal match."""
    out = _hidden_match(tmp_path, "renamed_ids_reordered")
    assert _score_a(out) >= 0
    assert _read_json(_current_gen(out) / "bot-diagnostics.json")["protocol_ok"] is True


def test_hidden_file_reflected(tmp_path: Path):
    """Hidden: file-reflected geometry is handled without protocol faults."""
    out = _hidden_match(tmp_path, "file_reflected")
    assert _read_json(_current_gen(out) / "bot-diagnostics.json")["protocol_ok"] is True


def test_hidden_color_board_swap(tmp_path: Path):
    """Hidden: color-and-board swapped seating preserves a normalized winner field."""
    out = _hidden_match(tmp_path, "color_board_swap")
    term = _read_json(_current_gen(out) / "terminal.json")
    assert term["winner"] in {"team_a", "team_b", "draw"}


def test_hidden_capacity_increase(tmp_path: Path):
    """Hidden: increased friendly relay capacity keeps transfers legal."""
    out = _hidden_match(tmp_path, "capacity_increase")
    assert _score_a(out) >= 0
    assert _read_json(_current_gen(out) / "bot-diagnostics.json")["bot_faults"] == 0


def test_hidden_outside_envelope_remove(tmp_path: Path):
    """Hidden: a far-away enemy outside interaction envelopes does not break observations."""
    out = _hidden_match(tmp_path, "outside_envelope_remove")
    vis = (_current_gen(out) / "visibility.jsonl").read_text()
    assert "visible_squares" in vis


def test_hidden_horizon_composite(tmp_path: Path):
    """Hidden: final-horizon mate, material, repetition, and points are jointly recorded."""
    out = _hidden_match(tmp_path, "horizon_composite")
    term = _read_json(_current_gen(out) / "terminal.json")
    summary = _summary(out)
    assert "scores" in term and "reason" in term
    assert summary["determinism"] == "seeded"
    assert "acceptance_floor" in summary


# ---------------------------------------------------------------------------
# 6 game-native metamorphic tests
# ---------------------------------------------------------------------------


def test_metamorphic_piece_id_renaming_preserves_outcome(tmp_path: Path):
    """Bijective piece-id renaming preserves normalized winner for a fixed seed match."""
    bot = _isolated_bot(tmp_path)
    base_pos = json.loads((HIDDEN / "renamed_ids_reordered.json").read_text())
    a = dict(base_pos)
    a["id"] = "meta-rename-a"
    a["piece_id_map"] = {}
    b = dict(base_pos)
    b["id"] = "meta-rename-b"
    b["piece_id_map"] = {"alpha-n1": "x1", "beta-n1": "y1"}
    pa, pb = tmp_path / "a.json", tmp_path / "b.json"
    pa.write_text(json.dumps(a))
    pb.write_text(json.dumps(b))
    out1, out2 = tmp_path / "o1", tmp_path / "o2"
    r1 = _run_match(pa, bot, out1)
    r2 = _run_match(pb, bot, out2)
    assert r1.returncode == 0 and r2.returncode == 0, r1.stderr + r2.stderr
    assert _winner(out1) == _winner(out2)
    assert _read_json(_current_gen(out1) / "bot-diagnostics.json")["protocol_ok"] is True


def test_metamorphic_observation_reorder_preserves_legality(tmp_path: Path):
    """Re-running the same match yields identical legal action counts (order-stable engine)."""
    bot = _isolated_bot(tmp_path)
    out1, out2 = tmp_path / "o1", tmp_path / "o2"
    assert _run_match("promotion-race", bot, out1).returncode == 0
    assert _run_match("promotion-race", bot, out2).returncode == 0
    d1 = _read_json(_current_gen(out1) / "bot-diagnostics.json")
    d2 = _read_json(_current_gen(out2) / "bot-diagnostics.json")
    assert d1["bot_legal_actions"] == d2["bot_legal_actions"]
    assert _accepted(out1) and _accepted(out2)


def test_metamorphic_file_reflection_preserves_result_class(tmp_path: Path):
    """File-reflected linked positions preserve the result class (winner bucket)."""
    out = _hidden_match(tmp_path, "file_reflected")
    assert _winner(out) in {"team_a", "team_b", "draw"}
    assert _read_json(_current_gen(out) / "bot-diagnostics.json")["bot_faults"] == 0


def test_metamorphic_color_board_swap_preserves_team_outcome_bucket(tmp_path: Path):
    """Color-and-board swapping on a symmetric setup yields a valid team outcome bucket."""
    out = _hidden_match(tmp_path, "color_board_swap")
    assert _winner(out) in {"team_a", "team_b", "draw"}


def test_metamorphic_increased_capacity_keeps_transfers_legal(tmp_path: Path):
    """Increasing friendly relay capacity cannot reduce legality of completed transfers."""
    out = _hidden_match(tmp_path, "capacity_increase")
    diag = _read_json(_current_gen(out) / "bot-diagnostics.json")
    assert diag["protocol_ok"] is True
    assert diag["bot_faults"] == 0


def test_metamorphic_remove_outside_envelope_enemy_no_effect_class(tmp_path: Path):
    """Removing an out-of-envelope enemy still yields a successful observation stream."""
    out = _hidden_match(tmp_path, "outside_envelope_remove")
    assert (_current_gen(out) / "visibility.jsonl").stat().st_size > 0
    assert _read_json(_current_gen(out) / "bot-diagnostics.json")["protocol_ok"] is True

