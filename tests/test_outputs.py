"""Verifier for the lantern-grid board-game referee."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import stat
import subprocess
from itertools import pairwise
from pathlib import Path

APP = Path("/app")
PUBLIC = APP / "task_file" / "public_ledger.json"
BIN = APP / "bin" / "lantern-referee"
OUT_DIR = APP / "out"
REASONS = [
    "unknown_house",
    "style_miss",
    "late",
    "spent",
    "space_miss",
    "level_miss",
    "heat_limit",
    "badge_miss",
    "pair_miss",
    "booster_missing",
    "empty_piece",
]
PUBLIC_SHA256 = "7f05602c32b7d61eedb89b216553335973d1d3145bfe3a4302f14b31cb34e947"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def same_subject_pieces(ledger: dict, turn: dict) -> list[dict]:
    return [tok for tok in ledger["pieces"] if tok["subject"] == turn["subject"]]


def option_failures(ledger: dict, piece: dict, turn: dict) -> list[str]:
    clubs = {club["id"]: club for club in ledger["clubs"]}
    playable = set(ledger["playable_houses"])
    style_order = ledger["style_order"]
    club = clubs.get(piece["club"])
    failures: list[str] = []

    if club is None or club.get("disabled", False) or club.get("house") not in playable:
        failures.append("unknown_house")
    if piece["style"] not in style_order or club is None or piece["style"] not in club["allowed_styles"]:
        failures.append("style_miss")
    if turn["at"] < piece["start_tick"] or turn["at"] > piece["end_tick"]:
        failures.append("late")
    if piece.get("spent_tick") is not None and turn["at"] >= piece["spent_tick"]:
        failures.append("spent")
    if turn["space"] not in piece["spaces"] or turn["stance"] not in piece["stances"]:
        failures.append("space_miss")
    if piece["level"] < turn["level"]:
        failures.append("level_miss")
    if club is None or turn["heat"] > club.get("max_heat", 0):
        failures.append("heat_limit")
    if not set(turn.get("badge", [])).issubset(set(piece.get("labels", []))):
        failures.append("badge_miss")
    if piece["pair"] != turn["pair"]:
        failures.append("pair_miss")
    if turn["booster_required"] and not piece["booster"]:
        failures.append("booster_missing")
    if piece["remaining"] <= 0:
        failures.append("empty_piece")
    return [reason for reason in REASONS if reason in failures]


def track_delta(track_name: str, turn: dict, piece: dict) -> int:
    prefix = f"track:{track_name}:{turn['id']}:"
    labels = sorted(label for label in piece.get("labels", []) if label.startswith(prefix))
    if labels:
        return int(labels[0].rsplit(":", 1)[1])
    return turn["priority"] - turn["heat"]


def playable_pairs(ledger: dict) -> list[list[int | None]]:
    choices: list[list[int | None]] = []
    for turn in ledger["turns"]:
        turn_choices: list[int | None] = [None]
        for idx, piece in enumerate(ledger["pieces"]):
            if piece["subject"] == turn["subject"] and not option_failures(ledger, piece, turn):
                turn_choices.append(idx)
        choices.append(turn_choices)
    return choices


def score_plan(ledger: dict, assignment: tuple[int | None, ...]) -> tuple | None:
    clubs = {club["id"]: club for club in ledger["clubs"]}
    house_limit = ledger["limits"]["per_house"]
    space_limit = ledger["limits"]["per_space"]
    subject_limit = ledger["limits"]["per_subject"]
    subject_house_limit = ledger["limits"].get("per_subject_house", {})
    subject_style_limit = ledger["limits"].get("per_subject_style", {})
    house_space_limit = ledger["limits"]["per_house_space"]
    house_style_limit = ledger["limits"]["per_house_style"]
    round_limit = ledger["limits"]["per_round"]
    subject_round_gap = ledger["limits"]["subject_round_gap"]
    badge_limit = ledger["limits"]["per_badge"]
    allowed_transitions = ledger["limits"]["allowed_transitions"]
    allowed_house_handoffs = ledger["limits"]["allowed_house_handoffs"]
    house_heat_budget = ledger["limits"]["house_heat_budget"]
    stance_space_gap = ledger["limits"]["stance_space_gap"]
    split_badge = set(ledger["limits"].get("split_badge", []))
    family_cap = ledger["limits"].get("family_cap", {})
    club_round_gap = ledger["limits"].get("club_round_gap", {})
    blocked_house_pairs = ledger["limits"].get("blocked_house_pairs", [])
    round_heat_budget = ledger["limits"].get("round_heat_budget", {})
    mutex_labels = set(ledger["limits"].get("mutex_labels", []))
    style_level = {style: idx + 1 for idx, style in enumerate(ledger["style_order"])}
    piece_use = {piece["id"]: 0 for piece in ledger["pieces"]}
    piece_rounds: dict[str, list[int]] = {piece["id"]: [] for piece in ledger["pieces"]}
    house_use: dict[str, int] = {}
    space_use: dict[str, int] = {}
    subject_use: dict[str, int] = {}
    subject_house_use: dict[str, int] = {}
    subject_style_use: dict[str, int] = {}
    house_space_use: dict[str, int] = {}
    house_style_use: dict[str, int] = {}
    round_use: dict[str, int] = {}
    badge_use: dict[str, int] = {}
    house_heat_use: dict[str, int] = {}
    family_use: dict[str, int] = {}
    round_heat_use: dict[str, int] = {}
    mutex_use: dict[str, list[dict]] = {}
    selected: dict[str, dict] = {}
    selected_turns: dict[str, dict] = {}
    selected_input_order: dict[str, int] = {}
    scored_priority = 0
    scored_heat = 0
    burden = 0
    used_pieces: set[str] = set()
    joined: list[str] = []

    for req_idx, piece_idx in enumerate(assignment):
        if piece_idx is None:
            continue
        turn = ledger["turns"][req_idx]
        piece = ledger["pieces"][piece_idx]
        club = clubs[piece["club"]]
        house = club["house"]
        piece_use[piece["id"]] += 1
        piece_rounds[piece["id"]].append(turn["round"])
        house_use[house] = house_use.get(house, 0) + 1
        space_use[turn["space"]] = space_use.get(turn["space"], 0) + 1
        subject_use[turn["subject"]] = subject_use.get(turn["subject"], 0) + 1
        subject_house_key = f"{turn['subject']}\x00{house}"
        subject_house_use[subject_house_key] = subject_house_use.get(subject_house_key, 0) + 1
        subject_style_key = f"{turn['subject']}\x00{piece['style']}"
        subject_style_use[subject_style_key] = subject_style_use.get(subject_style_key, 0) + 1
        house_space_key = f"{house}\x00{turn['space']}"
        house_space_use[house_space_key] = house_space_use.get(house_space_key, 0) + 1
        house_style_key = f"{house}\x00{piece['style']}"
        house_style_use[house_style_key] = house_style_use.get(house_style_key, 0) + 1
        round_key = str(turn["round"])
        round_use[round_key] = round_use.get(round_key, 0) + 1
        selected[turn["id"]] = piece
        selected_turns[turn["id"]] = turn
        selected_input_order[turn["id"]] = req_idx
        if piece_use[piece["id"]] > piece["remaining"]:
            return None
        if house_use[house] > house_limit.get(house, 0):
            return None
        if space_use[turn["space"]] > space_limit.get(turn["space"], 0):
            return None
        if subject_use[turn["subject"]] > subject_limit.get(turn["subject"], 0):
            return None
        if subject_house_use[subject_house_key] > subject_house_limit.get(turn["subject"], {}).get(house, 0):
            return None
        if subject_style_use[subject_style_key] > subject_style_limit.get(turn["subject"], {}).get(piece["style"], 0):
            return None
        if house_space_use[house_space_key] > house_space_limit.get(house, {}).get(turn["space"], 0):
            return None
        if house_style_use[house_style_key] > house_style_limit.get(house, {}).get(piece["style"], 0):
            return None
        if round_use[round_key] > round_limit.get(round_key, 0):
            return None
        if f"round-heat-waive:{round_key}" not in piece.get("labels", []):
            round_heat_use[round_key] = round_heat_use.get(round_key, 0) + turn["heat"]
            if round_heat_use[round_key] > round_heat_budget.get(round_key, 0):
                return None
        for label in piece.get("labels", []):
            if not label.startswith("family:"):
                continue
            family = label.split(":", 1)[1]
            family_use[family] = family_use.get(family, 0) + 1
            if family_use[family] > family_cap.get(family, 0):
                return None
        for label in piece.get("labels", []):
            if label in mutex_labels:
                mutex_use.setdefault(label, []).append(piece)
        if "heat-waive" not in piece.get("labels", []):
            house_heat_use[house] = house_heat_use.get(house, 0) + turn["heat"]
            if house_heat_use[house] > house_heat_budget.get(house, 0):
                return None
        for badge in turn.get("badge", []):
            if f"pool:{badge}" in piece.get("labels", []):
                continue
            badge_use[badge] = badge_use.get(badge, 0) + 1
            if badge_use[badge] > badge_limit.get(badge, 0):
                return None
        rounds = piece_rounds[piece["id"]]
        for left, right in itertools.combinations(rounds, 2):
            if abs(left - right) <= piece.get("cooldown", 0):
                return None
        scored_priority += turn["priority"]
        scored_heat += turn["heat"]
        burden += style_level[piece["style"]]
        used_pieces.add(piece["id"])
        joined.append(f"{turn['id']}={piece['id']}")

    for label, pieces in mutex_use.items():
        if len(pieces) > 1 and not all(f"mutex-ok:{label}" in piece.get("labels", []) for piece in pieces):
            return None

    for exclusion in ledger.get("exclusions", []):
        left = selected.get(exclusion["left"])
        right = selected.get(exclusion["right"])
        if left is None or right is None:
            continue
        label = exclusion["unless_label"]
        if label not in left.get("labels", []) or label not in right.get("labels", []):
            return None
    selected_houses: dict[str, list[dict]] = {}
    for piece in selected.values():
        selected_houses.setdefault(clubs[piece["club"]]["house"], []).append(piece)
    for left_house, right_house in blocked_house_pairs:
        if left_house not in selected_houses or right_house not in selected_houses:
            continue
        label = f"bridge:{left_house}:{right_house}"
        if not any(label in piece.get("labels", []) for piece in selected_houses[left_house]):
            return None
        if not any(label in piece.get("labels", []) for piece in selected_houses[right_house]):
            return None
    selected_ids = list(selected)
    for left_id, right_id in itertools.combinations(selected_ids, 2):
        left_turn = selected_turns[left_id]
        right_turn = selected_turns[right_id]
        left_piece = selected[left_id]
        right_piece = selected[right_id]
        left_house = clubs[left_piece["club"]]["house"]
        right_house = clubs[right_piece["club"]]["house"]
        if left_piece["club"] == right_piece["club"]:
            gap = club_round_gap.get(left_piece["club"], 0)
            label = f"club-burst:{left_piece['club']}"
            if (
                abs(left_turn["round"] - right_turn["round"]) <= gap
                and (
                    label not in left_piece.get("labels", [])
                    or label not in right_piece.get("labels", [])
                )
            ):
                return None
        shared_badge = set(left_turn.get("badge", [])) & set(right_turn.get("badge", [])) & split_badge
        for badge in sorted(shared_badge):
            if left_house == right_house:
                label = f"share:{badge}"
                if label not in left_piece.get("labels", []) or label not in right_piece.get("labels", []):
                    return None
        if left_turn["stance"] == right_turn["stance"] and left_turn["space"] == right_turn["space"]:
            gap = stance_space_gap.get(left_turn["stance"], {}).get(left_turn["space"], 0)
            label = f"parallel:{left_turn['stance']}:{left_turn['space']}"
            if (
                abs(left_turn["round"] - right_turn["round"]) <= gap
                and (
                    label not in left_piece.get("labels", [])
                    or label not in right_piece.get("labels", [])
                )
            ):
                return None
        if left_turn["subject"] != right_turn["subject"]:
            continue
        if "rapid" in left_piece.get("labels", []) and "rapid" in right_piece.get("labels", []):
            continue
        gap = subject_round_gap.get(left_turn["subject"], 0)
        if abs(left_turn["round"] - right_turn["round"]) <= gap:
            return None
    subject_ids: dict[str, list[str]] = {}
    for turn_id, turn in selected_turns.items():
        subject_ids.setdefault(turn["subject"], []).append(turn_id)
    for turn_ids in subject_ids.values():
        turn_ids.sort(key=lambda turn_id: (selected_turns[turn_id]["round"], selected_input_order[turn_id]))
        for left_id, right_id in pairwise(turn_ids):
            left_turn = selected_turns[left_id]
            right_turn = selected_turns[right_id]
            left_house = clubs[selected[left_id]["club"]]["house"]
            right_house = clubs[selected[right_id]["club"]]["house"]
            transition = f"route:{left_turn['space']}:{right_turn['space']}"
            left_piece = selected[left_id]
            right_piece = selected[right_id]
            has_route_label = transition in left_piece.get("labels", []) or transition in right_piece.get("labels", [])
            if not has_route_label and right_turn["space"] not in allowed_transitions.get(left_turn["space"], []):
                return None
            if left_house != right_house:
                handoff = f"{left_house}->{right_house}"
                handoff_label = f"handoff:{left_house}:{right_house}"
                if handoff_label in left_piece.get("labels", []) or handoff_label in right_piece.get("labels", []):
                    continue
                if handoff not in allowed_house_handoffs.get(left_turn["subject"], []):
                    return None
    for turn in ledger["turns"]:
        piece = selected.get(turn["id"])
        if piece is None:
            continue
        links = turn.get("links", [])
        link_label = turn.get("link_label", "")
        if link_label and link_label in piece.get("labels", []):
            continue
        for required_id in links:
            if required_id not in selected:
                return None
            required_turn = selected_turns[required_id]
            if required_turn["round"] > turn["round"] and f"late-link:{required_id}" not in piece.get("labels", []):
                return None
    for cohort in ledger.get("cohorts", []):
        cohort_members = [member for member in cohort["members"] if member in selected]
        cohort_pieces = [selected[member] for member in cohort_members]
        count = len(cohort_pieces)
        if count == 0:
            continue
        if count < cohort["min_score"] or count > cohort["max_score"]:
            return None
        houses = {clubs[piece["club"]]["house"] for piece in cohort_pieces}
        styles = {piece["style"] for piece in cohort_pieces}
        if len(houses) < cohort["min_houses"] or len(styles) < cohort["min_styles"]:
            return None
        cohort_heat = sum(selected_turns[member]["heat"] for member in cohort_members)
        if cohort_heat > cohort.get("max_heat", 0):
            return None
    for board in ledger.get("review_boards", []):
        member_pieces = [selected[member] for member in board["members"] if member in selected]
        if not member_pieces:
            continue
        chair_count = sum(1 for piece in member_pieces if board["chair_label"] in piece.get("labels", []))
        if chair_count < board["min_chairs"]:
            return None
        houses = {clubs[piece["club"]]["house"] for piece in member_pieces}
        styles = {piece["style"] for piece in member_pieces}
        if len(houses) < board["min_houses"] or len(styles) < board["min_styles"]:
            return None
        club_counts: dict[str, int] = {}
        for piece in member_pieces:
            club_counts[piece["club"]] = club_counts.get(piece["club"], 0) + 1
        if any(count > board["max_same_club"] for count in club_counts.values()):
            return None
    for window in ledger.get("surge_windows", []):
        rounds = set(window["rounds"])
        window_ids = [
            turn_id
            for turn_id, turn in selected_turns.items()
            if turn["round"] in rounds
        ]
        if not window_ids:
            continue
        name = window["name"]
        houses = set()
        spaces = set()
        subject_counts: dict[str, int] = {}
        window_heat = 0
        has_anchor = False
        for turn_id in window_ids:
            turn = selected_turns[turn_id]
            piece = selected[turn_id]
            labels = piece.get("labels", [])
            houses.add(clubs[piece["club"]]["house"])
            spaces.add(turn["space"])
            subject_counts[turn["subject"]] = subject_counts.get(turn["subject"], 0) + 1
            if f"surge-waive:{name}" not in labels:
                window_heat += turn["heat"]
            if window["anchor_label"] in labels:
                has_anchor = True
        if window_heat > window["max_heat"]:
            return None
        if len(houses) < window["min_houses"] or len(spaces) < window["min_spaces"]:
            return None
        if not has_anchor:
            return None
        for subject, count in subject_counts.items():
            if count <= window["max_same_subject"]:
                continue
            repeat_label = f"surge-repeat:{name}:{subject}"
            for turn_id in window_ids:
                turn = selected_turns[turn_id]
                if turn["subject"] == subject and repeat_label not in selected[turn_id].get("labels", []):
                    return None
    for path in ledger.get("relay_paths", []):
        member_ids = [member for member in path["members"] if member in selected]
        if not member_ids:
            continue
        if len(member_ids) < path["min_score"]:
            return None
        rounds = [selected_turns[member]["round"] for member in member_ids]
        pieces = [selected[member] for member in member_ids]
        name = path["name"]
        if max(rounds) - min(rounds) > path["max_round_span"]:
            wide_label = f"relay-wide:{name}"
            if not all(wide_label in piece.get("labels", []) for piece in pieces):
                return None
        if len({piece["id"] for piece in pieces}) < path["min_distinct_pieces"]:
            return None
        for left_id, right_id in pairwise(member_ids):
            left_turn = selected_turns[left_id]
            right_turn = selected_turns[right_id]
            left_piece = selected[left_id]
            right_piece = selected[right_id]
            edge_label = f"{path['edge_label_prefix']}:{left_id}:{right_id}"
            if edge_label not in left_piece.get("labels", []) and edge_label not in right_piece.get("labels", []):
                return None
            if left_turn["subject"] != right_turn["subject"]:
                continue
            subject_label = f"relay-subject:{name}:{left_turn['subject']}"
            if subject_label not in left_piece.get("labels", []) or subject_label not in right_piece.get("labels", []):
                return None
    for track in ledger.get("score_tracks", []):
        member_ids = [member for member in track["members"] if member in selected]
        if not member_ids:
            continue
        member_ids.sort(key=lambda turn_id: (selected_turns[turn_id]["round"], selected_input_order[turn_id]))
        name = track["name"]
        value = track["start"]
        for turn_id in member_ids:
            turn = selected_turns[turn_id]
            piece = selected[turn_id]
            labels = piece.get("labels", [])
            if f"track-reset:{name}" in labels:
                value = track["start"]
            value += track_delta(name, turn, piece)
            if f"track-guard:{name}" not in labels and not (track["min_value"] <= value <= track["max_value"]):
                return None
        if not (track["finish_min"] <= value <= track["finish_max"]):
            return None
    for backup_set in ledger.get("backup_sets", []):
        member_ids = [member for member in backup_set["members"] if member in selected]
        if not member_ids:
            continue
        for turn_id in member_ids:
            turn = selected_turns[turn_id]
            selected_piece_id = selected[turn_id]["id"]
            backups = [
                piece
                for piece in ledger["pieces"]
                if piece["id"] != selected_piece_id
                and backup_set["backup_label"] in piece.get("labels", [])
                and piece["subject"] == turn["subject"]
                and not option_failures(ledger, piece, turn)
            ]
            backups.sort(key=lambda piece: piece["id"])
            checked = backups[: backup_set["min_backups"]]
            if len(checked) < backup_set["min_backups"]:
                return None
            houses = {clubs[piece["club"]]["house"] for piece in checked}
            burden = sum(style_level[piece["style"]] for piece in checked)
            if len(houses) < backup_set["min_backup_houses"] or burden > backup_set["max_backup_burden"]:
                return None
    for market in ledger.get("claim_markets", []):
        member_ids = [member for member in market["members"] if member in selected]
        if not member_ids:
            continue
        member_ids.sort(key=lambda turn_id: selected_input_order[turn_id])
        claimed = []
        claimed_ids = set()
        for turn_id in member_ids:
            turn = selected_turns[turn_id]
            selected_piece_id = selected[turn_id]["id"]
            reserves = [
                piece
                for piece in ledger["pieces"]
                if piece["id"] != selected_piece_id
                and piece["id"] not in claimed_ids
                and piece["subject"] == turn["subject"]
                and market["claim_label"] in piece.get("labels", [])
                and not option_failures(ledger, piece, turn)
            ]
            reserves.sort(key=lambda piece: piece["id"])
            if not reserves:
                return None
            claimed.append(reserves[0])
            claimed_ids.add(reserves[0]["id"])
        houses = {clubs[piece["club"]]["house"] for piece in claimed}
        burden = sum(style_level[piece["style"]] for piece in claimed)
        if len(claimed) < market["min_claims"]:
            return None
        if len(houses) < market["min_claim_houses"] or burden > market["max_claim_burden"]:
            return None
    for ladder in ledger.get("round_ladders", []):
        member_ids = [member for member in ladder["members"] if member in selected]
        if not member_ids:
            continue
        member_ids.sort(key=lambda turn_id: (selected_turns[turn_id]["round"], selected_input_order[turn_id]))
        if len(member_ids) < ladder["min_score"]:
            return None
        name = ladder["name"]
        for index, (left_id, right_id) in enumerate(pairwise(member_ids)):
            left_turn = selected_turns[left_id]
            right_turn = selected_turns[right_id]
            left_piece = selected[left_id]
            right_piece = selected[right_id]
            if (
                right_turn["round"] - left_turn["round"] > ladder["max_round_gap"]
                and f"ladder-wide:{name}" not in left_piece.get("labels", [])
                and f"ladder-wide:{name}" not in right_piece.get("labels", [])
            ):
                return None
            left_style = style_level[left_piece["style"]]
            right_style = style_level[right_piece["style"]]
            wants_up = index % 2 == 0
            if ladder["pattern"] == "down-up":
                wants_up = not wants_up
            movement_ok = right_style > left_style if wants_up else right_style < left_style
            if movement_ok:
                continue
            free_label = f"{ladder['free_label_prefix']}:{left_id}:{right_id}"
            if free_label not in left_piece.get("labels", []) or free_label not in right_piece.get("labels", []):
                return None

    return (
        scored_priority,
        -scored_heat,
        -burden,
        -len(used_pieces),
        "\uffff" if not joined else "|".join(sorted(joined)),
    )


def expected_scorecard(ledger: dict) -> dict:
    choices = playable_pairs(ledger)
    best_assignment: tuple[int | None, ...] | None = None
    best_score: tuple | None = None
    for assignment in itertools.product(*choices):
        score = score_plan(ledger, assignment)
        if score is None:
            continue
        comparable = score[:-1] + (tuple([-ord(ch) for ch in score[-1]]),)
        if best_score is None or comparable > best_score:
            best_score = comparable
            best_assignment = assignment
    assert best_assignment is not None

    clubs = {club["id"]: club for club in ledger["clubs"]}
    style_level = {style: idx + 1 for idx, style in enumerate(ledger["style_order"])}
    scored = []
    missed = []
    priority = 0
    heat = 0
    burden = 0
    used_pieces: set[str] = set()
    choices_by_req = playable_pairs(ledger)

    for req_idx, turn in enumerate(ledger["turns"]):
        piece_idx = best_assignment[req_idx]
        if piece_idx is not None:
            piece = ledger["pieces"][piece_idx]
            house = clubs[piece["club"]]["house"]
            scored.append(
                {
                    "turn_id": turn["id"],
                    "piece_id": piece["id"],
                    "house": house,
                    "space": turn["space"],
                    "priority": turn["priority"],
                    "heat": turn["heat"],
                }
            )
            priority += turn["priority"]
            heat += turn["heat"]
            burden += style_level[piece["style"]]
            used_pieces.add(piece["id"])
            continue

        if len(choices_by_req[req_idx]) > 1:
            reasons = ["not_selected"]
        else:
            matching = same_subject_pieces(ledger, turn)
            if not matching:
                reasons = ["no_subject_piece"]
            else:
                seen = {
                    reason
                    for piece in matching
                    for reason in option_failures(ledger, piece, turn)
                }
                reasons = [reason for reason in REASONS if reason in seen]
        missed.append({"turn_id": turn["id"], "reasons": reasons})

    return {
        "scored": scored,
        "missed": missed,
        "summary": {
            "scored_count": len(scored),
            "priority": priority,
            "heat": heat,
            "style_burden": burden,
            "distinct_pieces": len(used_pieces),
        },
    }


def run_gate(ledger: dict, name: str) -> dict:
    input_path = OUT_DIR / f"{name}.input.json"
    output_path = OUT_DIR / f"{name}.scorecard.json"
    input_path.write_text(json.dumps(ledger, separators=(",", ":")), encoding="utf-8")
    if output_path.exists():
        output_path.unlink()
    result = subprocess.run(
        [str(BIN), "--input", str(input_path), "--output", str(output_path)],
        cwd=APP,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert output_path.exists(), f"{output_path} was not created"
    return load_json(output_path)


def variant_base() -> dict:
    return {
        "playable_houses": ["house-a", "house-b"],
        "style_order": ["spark", "hinge", "tower"],
        "clubs": [
            {"id": "ia", "house": "house-a", "disabled": False, "allowed_styles": ["spark", "hinge"], "max_heat": 8},
            {"id": "ib", "house": "house-b", "disabled": False, "allowed_styles": ["hinge", "tower"], "max_heat": 7},
            {"id": "ic", "house": "house-c", "disabled": True, "allowed_styles": ["spark"], "max_heat": 9},
        ],
        "limits": {
            "per_house": {"house-a": 2, "house-b": 2},
            "per_space": {"vault": 2, "ops": 1, "lab": 1},
            "per_subject": {"ada": 2, "ben": 2, "cy": 1, "dee": 1},
            "per_subject_house": {
                "ada": {"house-a": 4, "house-b": 2, "house-c": 0},
                "ben": {"house-a": 2, "house-b": 4, "house-c": 0},
                "cy": {"house-a": 0, "house-b": 0, "house-c": 1},
                "dee": {"house-a": 1, "house-b": 1, "house-c": 0},
            },
            "per_subject_style": {
                "ada": {"spark": 4, "hinge": 3, "tower": 0},
                "ben": {"spark": 0, "hinge": 4, "tower": 3},
                "cy": {"spark": 1, "hinge": 0, "tower": 0},
                "dee": {"spark": 1, "hinge": 1, "tower": 0},
            },
            "per_house_space": {
                "house-a": {"vault": 2, "ops": 1, "lab": 0},
                "house-b": {"vault": 1, "ops": 1, "lab": 1},
                "house-c": {"vault": 0, "ops": 0, "lab": 1},
            },
            "per_house_style": {
                "house-a": {"spark": 2, "hinge": 1, "tower": 0},
                "house-b": {"spark": 0, "hinge": 1, "tower": 1},
                "house-c": {"spark": 1, "hinge": 0, "tower": 0},
            },
            "per_round": {"1": 2, "2": 1, "3": 1, "4": 2, "5": 1, "6": 1},
            "subject_round_gap": {"ada": 1, "ben": 1, "cy": 0, "dee": 0},
            "per_badge": {"door": 2, "crest": 2, "rune": 2, "anvil": 2, "banner": 2},
            "allowed_transitions": {"vault": ["ops", "vault"], "ops": ["vault", "lab"], "lab": ["ops"]},
            "allowed_house_handoffs": {"ada": ["house-a->house-a"], "ben": ["house-b->house-b"], "cy": [], "dee": []},
            "house_heat_budget": {"house-a": 12, "house-b": 10, "house-c": 2},
            "stance_space_gap": {"forge": {"vault": 0, "ops": 0, "lab": 0}, "scout": {"vault": 0, "ops": 0, "lab": 0}, "captain": {"vault": 0, "ops": 0, "lab": 0}},
            "split_badge": [],
            "family_cap": {},
            "club_round_gap": {},
            "blocked_house_pairs": [],
            "round_heat_budget": {"1": 20, "2": 20, "3": 20, "4": 20, "5": 20, "6": 20},
            "mutex_labels": [],
        },
        "exclusions": [
            {"left": "r1", "right": "r2", "unless_label": "dual"},
            {"left": "r3", "right": "r4", "unless_label": "banner"},
        ],
        "cohorts": [
            {"members": ["r1", "r2", "r6"], "min_score": 0, "max_score": 2, "min_houses": 0, "min_styles": 0, "max_heat": 20},
            {"members": ["r3", "r4", "r5"], "min_score": 2, "max_score": 2, "min_houses": 1, "min_styles": 2, "max_heat": 10},
        ],
        "pieces": [
            {"id": "a1", "subject": "ada", "club": "ia", "style": "spark", "start_tick": 10, "end_tick": 90, "spent_tick": None, "spaces": ["vault", "ops"], "stances": ["captain", "forge"], "level": 4, "pair": "k1", "remaining": 2, "booster": True, "labels": ["door", "crest", "rune", "rapid"], "cooldown": 1},
            {"id": "a2", "subject": "ada", "club": "ia", "style": "hinge", "start_tick": 10, "end_tick": 90, "spent_tick": 62, "spaces": ["vault"], "stances": ["forge"], "level": 3, "pair": "k1", "remaining": 1, "booster": False, "labels": ["door"], "cooldown": 0},
            {"id": "b1", "subject": "ben", "club": "ib", "style": "hinge", "start_tick": 20, "end_tick": 100, "spent_tick": None, "spaces": ["ops", "lab"], "stances": ["forge", "scout"], "level": 3, "pair": "k2", "remaining": 2, "booster": False, "labels": ["rune", "anvil"], "cooldown": 2},
            {"id": "b2", "subject": "ben", "club": "ib", "style": "tower", "start_tick": 15, "end_tick": 95, "spent_tick": None, "spaces": ["vault", "ops"], "stances": ["scout"], "level": 5, "pair": "k2", "remaining": 1, "booster": True, "labels": ["crest", "banner", "rune"], "cooldown": 0},
            {"id": "c1", "subject": "cy", "club": "ic", "style": "spark", "start_tick": 10, "end_tick": 100, "spent_tick": None, "spaces": ["lab"], "stances": ["captain"], "level": 5, "pair": "k3", "remaining": 1, "booster": True, "labels": ["anvil", "banner"], "cooldown": 0},
        ],
        "turns": [
            {"id": "r1", "subject": "ada", "space": "vault", "stance": "forge", "at": 50, "level": 3, "pair": "k1", "booster_required": False, "priority": 8, "heat": 7, "badge": ["door"], "round": 1, "links": [], "link_label": ""},
            {"id": "r2", "subject": "ada", "space": "ops", "stance": "captain", "at": 60, "level": 4, "pair": "k1", "booster_required": True, "priority": 6, "heat": 1, "badge": ["rune"], "round": 2, "links": ["r1"], "link_label": "override"},
            {"id": "r3", "subject": "ben", "space": "lab", "stance": "forge", "at": 65, "level": 2, "pair": "k2", "booster_required": False, "priority": 5, "heat": 2, "badge": ["anvil"], "round": 1, "links": [], "link_label": ""},
            {"id": "r4", "subject": "ben", "space": "vault", "stance": "scout", "at": 70, "level": 5, "pair": "k2", "booster_required": True, "priority": 7, "heat": 4, "badge": ["crest", "banner"], "round": 3, "links": ["r3"], "link_label": "banner"},
            {"id": "r5", "subject": "cy", "space": "lab", "stance": "captain", "at": 70, "level": 5, "pair": "k3", "booster_required": True, "priority": 4, "heat": 1, "badge": ["anvil", "banner"], "round": 4, "links": [], "link_label": ""},
        ],
    }


def generated_variants() -> list[dict]:
    variants = []
    base = variant_base()
    variants.append(base)

    v = copy.deepcopy(base)
    v["limits"]["per_space"]["vault"] = 1
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "captain", "at": 72, "level": 4, "pair": "k1", "booster_required": True, "priority": 9, "heat": 8, "badge": ["crest"], "round": 4, "links": ["r2"], "link_label": "dual"})
    variants.append(v)

    v = copy.deepcopy(base)
    v["style_order"] = ["hinge", "spark", "tower"]
    variants.append(v)

    v = copy.deepcopy(base)
    v["pieces"][0]["remaining"] = 1
    v["turns"].append({"id": "r6", "subject": "ada", "space": "ops", "stance": "forge", "at": 55, "level": 3, "pair": "k1", "booster_required": False, "priority": 7, "heat": 2, "badge": ["rune"], "round": 3, "links": [], "link_label": ""})
    variants.append(v)

    v = copy.deepcopy(base)
    v["pieces"][2]["pair"] = "wrong"
    v["pieces"][2]["end_tick"] = 40
    variants.append(v)

    v = copy.deepcopy(base)
    v["playable_houses"] = ["house-a"]
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["per_house"]["house-a"] = 1
    v["limits"]["per_house"]["house-b"] = 1
    variants.append(v)

    v = copy.deepcopy(base)
    v["turns"].append({"id": "r6", "subject": "dee", "space": "ops", "stance": "forge", "at": 50, "level": 1, "pair": "k9", "booster_required": False, "priority": 3, "heat": 1, "badge": ["rune"], "round": 1, "links": [], "link_label": ""})
    variants.append(v)

    v = copy.deepcopy(base)
    v["pieces"].append({"id": "a3", "subject": "ada", "club": "ia", "style": "spark", "start_tick": 10, "end_tick": 90, "spaces": ["vault"], "stances": ["forge"], "level": 4, "pair": "k1", "remaining": 1, "booster": True, "labels": ["door"], "cooldown": 0})
    variants.append(v)

    v = copy.deepcopy(base)
    v["turns"][0]["priority"] = 6
    v["turns"][1]["priority"] = 8
    v["turns"][0]["heat"] = 1
    v["turns"][1]["heat"] = 7
    variants.append(v)

    v = copy.deepcopy(base)
    v["pieces"][1]["remaining"] = 0
    v["pieces"][1]["level"] = 1
    variants.append(v)

    v = copy.deepcopy(base)
    v["clubs"][1]["allowed_styles"] = ["tower"]
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["per_space"] = {"vault": 1, "ops": 1, "lab": 1}
    v["turns"].append({"id": "r6", "subject": "ben", "space": "ops", "stance": "scout", "at": 75, "level": 4, "pair": "k2", "booster_required": True, "priority": 9, "heat": 7, "badge": ["rune"], "round": 5, "links": ["r4"], "link_label": "banner"})
    variants.append(v)

    v = copy.deepcopy(base)
    v["pieces"][3]["id"] = "b0"
    v["pieces"].append({"id": "b3", "subject": "ben", "club": "ib", "style": "tower", "start_tick": 15, "end_tick": 95, "spaces": ["vault"], "stances": ["scout"], "level": 5, "pair": "k2", "remaining": 1, "booster": True, "labels": ["crest", "banner"], "cooldown": 0})
    variants.append(v)

    v = copy.deepcopy(base)
    v["clubs"][0]["max_heat"] = 3
    variants.append(v)

    v = copy.deepcopy(base)
    v["turns"][1]["badge"] = ["rune", "banner"]
    v["pieces"][0]["labels"] = ["door", "rune"]
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["per_subject"]["ada"] = 1
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "captain", "at": 80, "level": 4, "pair": "k1", "booster_required": True, "priority": 10, "heat": 2, "badge": ["crest"], "round": 5, "links": ["r2"], "link_label": "dual"})
    variants.append(v)

    v = copy.deepcopy(base)
    v["pieces"][0]["remaining"] = 3
    v["pieces"][0]["cooldown"] = 2
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "captain", "at": 75, "level": 4, "pair": "k1", "booster_required": True, "priority": 9, "heat": 2, "badge": ["crest"], "round": 3, "links": [], "link_label": ""})
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_subject"]["ada"] = 3
    variants.append(v)

    v = copy.deepcopy(base)
    v["style_order"] = ["tower", "hinge", "spark"]
    v["limits"]["per_house"]["house-b"] = 1
    v["pieces"][2]["remaining"] = 1
    v["pieces"][3]["remaining"] = 2
    v["turns"].append({"id": "r6", "subject": "ben", "space": "ops", "stance": "scout", "at": 78, "level": 4, "pair": "k2", "booster_required": True, "priority": 8, "heat": 6, "badge": ["rune"], "round": 6, "links": ["r3"], "link_label": "rune"})
    variants.append(v)

    v = copy.deepcopy(base)
    v["playable_houses"] = ["house-a", "house-b", "house-c"]
    v["clubs"][2]["disabled"] = False
    v["limits"]["per_house"]["house-c"] = 1
    v["limits"]["per_house_space"]["house-c"]["lab"] = 1
    v["limits"]["per_house_style"]["house-c"]["spark"] = 1
    variants.append(v)

    v = copy.deepcopy(base)
    v["pieces"][0]["spent_tick"] = 61
    variants.append(v)

    v = copy.deepcopy(base)
    v["pieces"][0]["labels"].append("dual")
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 9, "heat": 3, "badge": ["door"], "round": 5, "links": ["r2"], "link_label": "dual"})
    v["exclusions"].append({"left": "r1", "right": "r6", "unless_label": "dual"})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["per_house_space"]["house-a"]["vault"] = 1
    v["limits"]["per_space"]["vault"] = 3
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 58, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    variants.append(v)

    v = copy.deepcopy(base)
    v["exclusions"] = [
        {"left": "r2", "right": "r4", "unless_label": "rune"},
        {"left": "r1", "right": "r3", "unless_label": "scout-bridge"},
    ]
    variants.append(v)

    v = copy.deepcopy(base)
    v["pieces"][2]["spent_tick"] = 65
    v["pieces"][3]["remaining"] = 2
    v["turns"].append({"id": "r6", "subject": "ben", "space": "ops", "stance": "scout", "at": 66, "level": 4, "pair": "k2", "booster_required": True, "priority": 8, "heat": 6, "badge": ["rune"], "round": 5, "links": ["r4"], "link_label": "banner"})
    v["limits"]["per_subject"]["ben"] = 3
    v["limits"]["per_space"]["ops"] = 2
    v["limits"]["per_house_space"]["house-b"]["ops"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["pieces"].append({"id": "a4", "subject": "ada", "club": "ia", "style": "hinge", "start_tick": 10, "end_tick": 90, "spent_tick": None, "spaces": ["ops", "vault"], "stances": ["captain", "forge"], "level": 4, "pair": "k1", "remaining": 2, "booster": True, "labels": ["door", "crest", "rune", "dual"], "cooldown": 3})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "captain", "at": 85, "level": 4, "pair": "k1", "booster_required": True, "priority": 9, "heat": 1, "badge": ["crest"], "round": 4, "links": ["r2"], "link_label": "dual"})
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["per_round"]["1"] = 1
    variants.append(v)

    v = copy.deepcopy(base)
    v["pieces"][0]["labels"].append("override")
    v["turns"][1]["priority"] = 11
    v["turns"][0]["priority"] = 1
    variants.append(v)

    v = copy.deepcopy(base)
    v["turns"][4]["links"] = ["r4"]
    v["turns"][4]["link_label"] = "anvil"
    v["clubs"][2]["disabled"] = False
    v["playable_houses"].append("house-c")
    v["limits"]["per_house"]["house-c"] = 1
    v["limits"]["per_house_space"]["house-c"]["lab"] = 1
    v["limits"]["per_house_style"]["house-c"]["spark"] = 1
    variants.append(v)

    v = copy.deepcopy(base)
    v["turns"].append({"id": "r6", "subject": "ben", "space": "lab", "stance": "forge", "at": 80, "level": 2, "pair": "k2", "booster_required": False, "priority": 9, "heat": 2, "badge": ["anvil"], "round": 1, "links": ["r4"], "link_label": ""})
    v["limits"]["per_subject"]["ben"] = 3
    v["limits"]["per_space"]["lab"] = 2
    v["limits"]["per_house_space"]["house-b"]["lab"] = 2
    v["limits"]["per_round"]["1"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["per_house_style"]["house-a"]["spark"] = 1
    v["pieces"].append({"id": "a4", "subject": "ada", "club": "ia", "style": "hinge", "start_tick": 10, "end_tick": 90, "spent_tick": None, "spaces": ["vault", "ops"], "stances": ["captain", "forge"], "level": 4, "pair": "k1", "remaining": 2, "booster": True, "labels": ["door", "crest", "rune", "dual"], "cooldown": 0})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 11, "heat": 2, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    variants.append(v)

    v = copy.deepcopy(base)
    v["cohorts"] = [
        {"members": ["r1", "r2", "r6"], "min_score": 2, "max_score": 2, "min_houses": 1, "min_styles": 2, "max_heat": 20},
        {"members": ["r3", "r4", "r5"], "min_score": 2, "max_score": 2, "min_houses": 1, "min_styles": 2, "max_heat": 10},
    ]
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "captain", "at": 84, "level": 4, "pair": "k1", "booster_required": True, "priority": 10, "heat": 1, "badge": ["crest"], "round": 6, "links": ["r2"], "link_label": "dual"})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    variants.append(v)

    v = copy.deepcopy(base)
    v["cohorts"] = [
        {"members": ["r1", "r2"], "min_score": 1, "max_score": 1, "min_houses": 1, "min_styles": 1, "max_heat": 10},
        {"members": ["r3", "r4", "r6"], "min_score": 2, "max_score": 2, "min_houses": 1, "min_styles": 2, "max_heat": 10},
    ]
    v["turns"].append({"id": "r6", "subject": "ben", "space": "ops", "stance": "scout", "at": 85, "level": 4, "pair": "k2", "booster_required": True, "priority": 10, "heat": 4, "badge": ["rune"], "round": 6, "links": ["r3"], "link_label": "rune"})
    v["pieces"][3]["remaining"] = 2
    v["limits"]["per_subject"]["ben"] = 3
    v["limits"]["per_space"]["ops"] = 2
    v["limits"]["per_house_space"]["house-b"]["ops"] = 2
    v["limits"]["per_house_style"]["house-b"]["tower"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["cohorts"] = [
        {"members": ["r1", "r2", "r6"], "min_score": 2, "max_score": 2, "min_houses": 1, "min_styles": 2, "max_heat": 20},
        {"members": ["r3", "r4", "r5"], "min_score": 2, "max_score": 2, "min_houses": 1, "min_styles": 2, "max_heat": 10},
    ]
    v["pieces"].append({"id": "a4", "subject": "ada", "club": "ia", "style": "hinge", "start_tick": 10, "end_tick": 90, "spent_tick": None, "spaces": ["vault", "ops"], "stances": ["captain", "forge"], "level": 4, "pair": "k1", "remaining": 1, "booster": True, "labels": ["door", "crest", "rune", "dual"], "cooldown": 0})
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 83, "level": 3, "pair": "k1", "booster_required": False, "priority": 9, "heat": 2, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    v["limits"]["per_house_style"]["house-a"]["hinge"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["playable_houses"].append("house-c")
    v["clubs"][2]["disabled"] = False
    v["limits"]["per_house"]["house-c"] = 1
    v["limits"]["per_house_space"]["house-c"]["lab"] = 1
    v["limits"]["per_house_style"]["house-c"]["spark"] = 1
    v["cohorts"] = [
        {"members": ["r3", "r4", "r5"], "min_score": 2, "max_score": 3, "min_houses": 2, "min_styles": 2, "max_heat": 10},
    ]
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["subject_round_gap"]["ada"] = 2
    v["pieces"][0]["labels"] = ["door", "crest", "rune"]
    v["pieces"].append({"id": "a4", "subject": "ada", "club": "ia", "style": "hinge", "start_tick": 10, "end_tick": 90, "spent_tick": None, "spaces": ["vault", "ops"], "stances": ["captain", "forge"], "level": 4, "pair": "k1", "remaining": 1, "booster": True, "labels": ["door", "crest", "rune"], "cooldown": 0})
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 3, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    v["limits"]["per_house_style"]["house-a"]["hinge"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["subject_round_gap"]["ben"] = 2
    v["pieces"][2]["labels"].append("rapid")
    v["pieces"][3]["labels"].append("rapid")
    v["pieces"][3]["remaining"] = 2
    v["turns"].append({"id": "r6", "subject": "ben", "space": "ops", "stance": "scout", "at": 82, "level": 4, "pair": "k2", "booster_required": True, "priority": 9, "heat": 5, "badge": ["rune"], "round": 5, "links": ["r3"], "link_label": "rune"})
    v["limits"]["per_subject"]["ben"] = 3
    v["limits"]["per_space"]["ops"] = 2
    v["limits"]["per_house_space"]["house-b"]["ops"] = 2
    v["limits"]["per_house_style"]["house-b"]["tower"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["per_badge"]["door"] = 1
    v["pieces"].append({"id": "a4", "subject": "ada", "club": "ia", "style": "hinge", "start_tick": 10, "end_tick": 90, "spent_tick": None, "spaces": ["vault", "ops"], "stances": ["captain", "forge"], "level": 4, "pair": "k1", "remaining": 2, "booster": True, "labels": ["door", "crest", "rune", "pool:door"], "cooldown": 0})
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    v["limits"]["per_house_style"]["house-a"]["hinge"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["per_badge"]["rune"] = 1
    v["pieces"][0]["labels"] = ["door", "crest", "rune", "rapid", "pool:rune"]
    v["pieces"][2]["labels"] = ["rune", "anvil"]
    v["turns"].append({"id": "r6", "subject": "ben", "space": "ops", "stance": "forge", "at": 82, "level": 2, "pair": "k2", "booster_required": False, "priority": 9, "heat": 3, "badge": ["rune"], "round": 5, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ben"] = 3
    v["limits"]["per_space"]["ops"] = 2
    v["limits"]["per_house_space"]["house-b"]["ops"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["per_badge"]["crest"] = 1
    v["turns"][3]["badge"] = ["crest", "crest", "banner"]
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["allowed_transitions"] = {"vault": ["ops"], "ops": ["lab"], "lab": ["ops"]}
    v["pieces"][0]["labels"] = ["door", "crest", "rune", "rapid", "route:ops:vault"]
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["allowed_transitions"] = {"vault": ["ops"], "ops": ["vault"], "lab": []}
    v["pieces"][2]["remaining"] = 2
    v["turns"].append({"id": "r6", "subject": "ben", "space": "lab", "stance": "forge", "at": 82, "level": 2, "pair": "k2", "booster_required": False, "priority": 9, "heat": 3, "badge": ["anvil"], "round": 4, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ben"] = 3
    v["limits"]["per_space"]["lab"] = 2
    v["limits"]["per_house_space"]["house-b"]["lab"] = 2
    v["limits"]["per_round"]["4"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["allowed_transitions"]["vault"] = ["ops"]
    v["pieces"].append({"id": "a4", "subject": "ada", "club": "ia", "style": "hinge", "start_tick": 10, "end_tick": 90, "spent_tick": None, "spaces": ["vault"], "stances": ["forge"], "level": 4, "pair": "k1", "remaining": 1, "booster": True, "labels": ["door", "route:vault:vault"], "cooldown": 0})
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    v["limits"]["per_house_style"]["house-a"]["hinge"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["pieces"].append({"id": "b3", "subject": "ben", "club": "ia", "style": "hinge", "start_tick": 20, "end_tick": 100, "spent_tick": None, "spaces": ["lab", "ops"], "stances": ["forge", "scout"], "level": 4, "pair": "k2", "remaining": 1, "booster": True, "labels": ["anvil", "rune"], "cooldown": 0})
    v["turns"].append({"id": "r6", "subject": "ben", "space": "ops", "stance": "scout", "at": 82, "level": 3, "pair": "k2", "booster_required": True, "priority": 11, "heat": 3, "badge": ["rune"], "round": 5, "links": ["r3"], "link_label": ""})
    v["limits"]["per_subject"]["ben"] = 3
    v["limits"]["per_space"]["ops"] = 2
    v["limits"]["per_house"]["house-a"] = 3
    v["limits"]["per_house_space"]["house-a"]["ops"] = 2
    v["limits"]["per_house_style"]["house-a"]["hinge"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["allowed_house_handoffs"]["ben"] = ["house-b->house-a"]
    v["pieces"].append({"id": "b3", "subject": "ben", "club": "ia", "style": "hinge", "start_tick": 20, "end_tick": 100, "spent_tick": None, "spaces": ["ops"], "stances": ["scout"], "level": 4, "pair": "k2", "remaining": 1, "booster": True, "labels": ["rune"], "cooldown": 0})
    v["turns"].append({"id": "r6", "subject": "ben", "space": "ops", "stance": "scout", "at": 82, "level": 3, "pair": "k2", "booster_required": True, "priority": 11, "heat": 3, "badge": ["rune"], "round": 5, "links": ["r3"], "link_label": ""})
    v["limits"]["per_subject"]["ben"] = 3
    v["limits"]["per_space"]["ops"] = 2
    v["limits"]["per_house"]["house-a"] = 3
    v["limits"]["per_house_space"]["house-a"]["ops"] = 2
    v["limits"]["per_house_style"]["house-a"]["hinge"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["pieces"].append({"id": "b3", "subject": "ben", "club": "ia", "style": "hinge", "start_tick": 20, "end_tick": 100, "spent_tick": None, "spaces": ["ops"], "stances": ["scout"], "level": 4, "pair": "k2", "remaining": 1, "booster": True, "labels": ["rune", "handoff:house-b:house-a"], "cooldown": 0})
    v["turns"].append({"id": "r6", "subject": "ben", "space": "ops", "stance": "scout", "at": 82, "level": 3, "pair": "k2", "booster_required": True, "priority": 11, "heat": 3, "badge": ["rune"], "round": 5, "links": ["r3"], "link_label": ""})
    v["limits"]["per_subject"]["ben"] = 3
    v["limits"]["per_space"]["ops"] = 2
    v["limits"]["per_house"]["house-a"] = 3
    v["limits"]["per_house_space"]["house-a"]["ops"] = 2
    v["limits"]["per_house_style"]["house-a"]["hinge"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["house_heat_budget"]["house-a"] = 8
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 5, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["house_heat_budget"]["house-a"] = 8
    v["pieces"][0]["labels"].append("heat-waive")
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 5, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["house_heat_budget"]["house-b"] = 5
    v["pieces"][3]["remaining"] = 2
    v["turns"].append({"id": "r6", "subject": "ben", "space": "ops", "stance": "scout", "at": 82, "level": 4, "pair": "k2", "booster_required": True, "priority": 9, "heat": 5, "badge": ["rune"], "round": 5, "links": ["r4"], "link_label": "rune"})
    v["limits"]["per_subject"]["ben"] = 3
    v["limits"]["per_space"]["ops"] = 2
    v["limits"]["per_house_space"]["house-b"]["ops"] = 2
    v["limits"]["per_house_style"]["house-b"]["tower"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["stance_space_gap"]["forge"]["vault"] = 3
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 3, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["stance_space_gap"]["forge"]["vault"] = 3
    v["pieces"][0]["labels"].append("parallel:forge:vault")
    v["pieces"].append({"id": "a4", "subject": "ada", "club": "ia", "style": "hinge", "start_tick": 10, "end_tick": 90, "spent_tick": None, "spaces": ["vault"], "stances": ["forge"], "level": 4, "pair": "k1", "remaining": 1, "booster": True, "labels": ["door", "parallel:forge:vault"], "cooldown": 0})
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 3, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    v["limits"]["per_house_style"]["house-a"]["hinge"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["stance_space_gap"]["forge"]["lab"] = 4
    v["turns"].append({"id": "r6", "subject": "ben", "space": "lab", "stance": "forge", "at": 82, "level": 2, "pair": "k2", "booster_required": False, "priority": 9, "heat": 2, "badge": ["anvil"], "round": 4, "links": [], "link_label": ""})
    v["pieces"][2]["remaining"] = 2
    v["limits"]["per_subject"]["ben"] = 3
    v["limits"]["per_space"]["lab"] = 2
    v["limits"]["per_house_space"]["house-b"]["lab"] = 2
    v["limits"]["per_round"]["4"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["split_badge"] = ["door"]
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["split_badge"] = ["door"]
    v["pieces"][0]["labels"].append("share:door")
    v["pieces"].append({"id": "a4", "subject": "ada", "club": "ia", "style": "hinge", "start_tick": 10, "end_tick": 90, "spent_tick": None, "spaces": ["vault"], "stances": ["forge"], "level": 4, "pair": "k1", "remaining": 1, "booster": True, "labels": ["door", "share:door"], "cooldown": 0})
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    v["limits"]["per_house_style"]["house-a"]["hinge"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["split_badge"] = ["rune"]
    v["turns"].append({"id": "r6", "subject": "ben", "space": "ops", "stance": "scout", "at": 82, "level": 4, "pair": "k2", "booster_required": True, "priority": 9, "heat": 5, "badge": ["rune"], "round": 5, "links": ["r4"], "link_label": "rune"})
    v["pieces"][3]["remaining"] = 2
    v["limits"]["per_subject"]["ben"] = 3
    v["limits"]["per_space"]["ops"] = 2
    v["limits"]["per_house_space"]["house-b"]["ops"] = 2
    v["limits"]["per_house_style"]["house-b"]["tower"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["family_cap"] = {"alpha": 1}
    v["pieces"][0]["labels"].append("family:alpha")
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["family_cap"] = {"alpha": 1, "beta": 1}
    v["pieces"][0]["labels"].append("family:alpha")
    v["pieces"].append({"id": "a4", "subject": "ada", "club": "ia", "style": "hinge", "start_tick": 10, "end_tick": 90, "spent_tick": None, "spaces": ["vault"], "stances": ["forge"], "level": 4, "pair": "k1", "remaining": 1, "booster": True, "labels": ["door", "family:beta"], "cooldown": 0})
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    v["limits"]["per_house_style"]["house-a"]["hinge"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["family_cap"] = {"gamma": 1}
    v["pieces"][3]["labels"].append("family:gamma")
    v["pieces"][3]["remaining"] = 2
    v["turns"].append({"id": "r6", "subject": "ben", "space": "ops", "stance": "scout", "at": 82, "level": 4, "pair": "k2", "booster_required": True, "priority": 9, "heat": 5, "badge": ["rune"], "round": 5, "links": ["r4"], "link_label": "rune"})
    v["limits"]["per_subject"]["ben"] = 3
    v["limits"]["per_space"]["ops"] = 2
    v["limits"]["per_house_space"]["house-b"]["ops"] = 2
    v["limits"]["per_house_style"]["house-b"]["tower"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["cohorts"][1]["max_heat"] = 5
    variants.append(v)

    v = copy.deepcopy(base)
    v["cohorts"][1]["max_heat"] = 6
    v["turns"][3]["heat"] = 5
    v["turns"][4]["heat"] = 1
    variants.append(v)

    v = copy.deepcopy(base)
    v["cohorts"][0] = {"members": ["r1", "r2", "r6"], "min_score": 2, "max_score": 2, "min_houses": 1, "min_styles": 1, "max_heat": 8}
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["club_round_gap"] = {"ia": 2}
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 3, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["club_round_gap"] = {"ia": 2}
    v["pieces"][0]["labels"].append("club-burst:ia")
    v["pieces"].append({"id": "a4", "subject": "ada", "club": "ia", "style": "hinge", "start_tick": 10, "end_tick": 90, "spent_tick": None, "spaces": ["vault"], "stances": ["forge"], "level": 4, "pair": "k1", "remaining": 1, "booster": True, "labels": ["door", "club-burst:ia"], "cooldown": 0})
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 3, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    v["limits"]["per_house_style"]["house-a"]["hinge"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["club_round_gap"] = {"ib": 4}
    v["pieces"][3]["remaining"] = 2
    v["turns"].append({"id": "r6", "subject": "ben", "space": "ops", "stance": "scout", "at": 82, "level": 4, "pair": "k2", "booster_required": True, "priority": 9, "heat": 5, "badge": ["rune"], "round": 5, "links": ["r4"], "link_label": "rune"})
    v["limits"]["per_subject"]["ben"] = 3
    v["limits"]["per_space"]["ops"] = 2
    v["limits"]["per_house_space"]["house-b"]["ops"] = 2
    v["limits"]["per_house_style"]["house-b"]["tower"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["turns"][1]["round"] = 1
    v["turns"][0]["round"] = 3
    v["limits"]["per_round"]["1"] = 2
    v["limits"]["per_round"]["3"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["turns"][1]["round"] = 1
    v["turns"][0]["round"] = 3
    v["pieces"][0]["labels"].append("late-link:r1")
    v["limits"]["per_round"]["1"] = 2
    v["limits"]["per_round"]["3"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["turns"][3]["round"] = 1
    v["turns"][2]["round"] = 4
    v["pieces"][3]["remaining"] = 2
    v["limits"]["per_round"]["1"] = 2
    v["limits"]["per_round"]["4"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["blocked_house_pairs"] = [["house-a", "house-b"]]
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["blocked_house_pairs"] = [["house-a", "house-b"]]
    v["pieces"][0]["labels"].append("bridge:house-a:house-b")
    v["pieces"][3]["labels"].append("bridge:house-a:house-b")
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["blocked_house_pairs"] = [["house-b", "house-a"]]
    v["pieces"][0]["labels"].append("bridge:house-a:house-b")
    v["pieces"][3]["labels"].append("bridge:house-a:house-b")
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["round_heat_budget"]["1"] = 8
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["round_heat_budget"]["1"] = 8
    v["pieces"][0]["labels"].append("round-heat-waive:1")
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["round_heat_budget"]["4"] = 2
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 4, "links": [], "link_label": ""})
    v["limits"]["per_round"]["4"] = 3
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["mutex_labels"] = ["hot"]
    v["pieces"][0]["labels"].append("hot")
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["mutex_labels"] = ["hot"]
    v["pieces"][0]["labels"].extend(["hot", "mutex-ok:hot"])
    v["pieces"].append({"id": "a4", "subject": "ada", "club": "ia", "style": "hinge", "start_tick": 10, "end_tick": 90, "spent_tick": None, "spaces": ["vault"], "stances": ["forge"], "level": 4, "pair": "k1", "remaining": 1, "booster": True, "labels": ["door", "hot", "mutex-ok:hot"], "cooldown": 0})
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    v["limits"]["per_house_style"]["house-a"]["hinge"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["mutex_labels"] = ["hot"]
    v["pieces"][0]["labels"].extend(["hot", "mutex-ok:hot"])
    v["pieces"].append({"id": "a4", "subject": "ada", "club": "ia", "style": "hinge", "start_tick": 10, "end_tick": 90, "spent_tick": None, "spaces": ["vault"], "stances": ["forge"], "level": 4, "pair": "k1", "remaining": 1, "booster": True, "labels": ["door", "hot"], "cooldown": 0})
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    v["limits"]["per_house_style"]["house-a"]["hinge"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["per_subject_house"]["ada"]["house-a"] = 1
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["per_subject_house"]["ada"]["house-a"] = 1
    v["limits"]["per_subject_house"]["ada"]["house-b"] = 2
    v["pieces"].append({"id": "a4", "subject": "ada", "club": "ib", "style": "hinge", "start_tick": 10, "end_tick": 90, "spent_tick": None, "spaces": ["vault"], "stances": ["forge"], "level": 4, "pair": "k1", "remaining": 1, "booster": True, "labels": ["door"], "cooldown": 0})
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_house"]["house-b"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-b"]["vault"] = 2
    v["limits"]["per_house_style"]["house-b"]["hinge"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["per_subject_house"]["ben"]["house-b"] = 1
    v["pieces"][3]["remaining"] = 2
    v["turns"].append({"id": "r6", "subject": "ben", "space": "ops", "stance": "scout", "at": 82, "level": 4, "pair": "k2", "booster_required": True, "priority": 9, "heat": 5, "badge": ["rune"], "round": 5, "links": ["r4"], "link_label": "rune"})
    v["limits"]["per_subject"]["ben"] = 3
    v["limits"]["per_space"]["ops"] = 2
    v["limits"]["per_house_space"]["house-b"]["ops"] = 2
    v["limits"]["per_house_style"]["house-b"]["tower"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["per_subject_style"]["ada"]["spark"] = 1
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["per_subject_style"]["ada"]["spark"] = 1
    v["limits"]["per_subject_style"]["ada"]["hinge"] = 2
    v["pieces"].append({"id": "a4", "subject": "ada", "club": "ia", "style": "hinge", "start_tick": 10, "end_tick": 90, "spent_tick": None, "spaces": ["vault"], "stances": ["forge"], "level": 4, "pair": "k1", "remaining": 1, "booster": True, "labels": ["door"], "cooldown": 0})
    v["turns"].append({"id": "r6", "subject": "ada", "space": "vault", "stance": "forge", "at": 82, "level": 3, "pair": "k1", "booster_required": False, "priority": 10, "heat": 2, "badge": ["door"], "round": 6, "links": [], "link_label": ""})
    v["limits"]["per_subject"]["ada"] = 3
    v["limits"]["per_space"]["vault"] = 3
    v["limits"]["per_house_space"]["house-a"]["vault"] = 3
    v["limits"]["per_house_style"]["house-a"]["hinge"] = 2
    variants.append(v)

    v = copy.deepcopy(base)
    v["limits"]["per_subject_style"]["ben"]["tower"] = 1
    v["pieces"][3]["remaining"] = 2
    v["turns"].append({"id": "r6", "subject": "ben", "space": "ops", "stance": "scout", "at": 82, "level": 4, "pair": "k2", "booster_required": True, "priority": 9, "heat": 5, "badge": ["rune"], "round": 5, "links": ["r4"], "link_label": "rune"})
    v["limits"]["per_subject"]["ben"] = 3
    v["limits"]["per_space"]["ops"] = 2
    v["limits"]["per_house_space"]["house-b"]["ops"] = 2
    v["limits"]["per_house_style"]["house-b"]["tower"] = 2
    variants.append(v)

    return variants


def dense_frontier_ledger() -> dict:
    """Build a ledger with several valid full-plan choices competing at once."""
    ledger = copy.deepcopy(variant_base())
    ledger["pieces"][0]["labels"].extend(["dual", "pool:door", "bridge:house-b:house-a"])
    ledger["pieces"][2]["labels"].extend(["banner", "route:lab:vault", "bridge:house-b:house-a"])
    ledger["pieces"][3]["labels"].extend(["banner", "route:lab:vault", "bridge:house-b:house-a"])
    ledger["pieces"].append(
        {
            "id": "a3",
            "subject": "ada",
            "club": "ia",
            "style": "hinge",
            "start_tick": 10,
            "end_tick": 90,
            "spent_tick": None,
            "spaces": ["ops", "vault"],
            "stances": ["captain", "forge"],
            "level": 4,
            "pair": "k1",
            "remaining": 1,
            "booster": True,
            "labels": ["rune", "crest", "dual", "rapid", "bridge:house-b:house-a"],
            "cooldown": 0,
        }
    )
    ledger["turns"].append(
        {
            "id": "r6",
            "subject": "ada",
            "space": "vault",
            "stance": "forge",
            "at": 80,
            "level": 3,
            "pair": "k1",
            "booster_required": False,
            "priority": 9,
            "heat": 2,
            "badge": ["door", "door"],
            "round": 6,
            "links": ["r2"],
            "link_label": "override",
        }
    )
    ledger["limits"]["per_house"]["house-a"] = 4
    ledger["limits"]["per_house"]["house-b"] = 3
    ledger["limits"]["per_space"]["vault"] = 4
    ledger["limits"]["per_space"]["ops"] = 2
    ledger["limits"]["per_space"]["lab"] = 2
    ledger["limits"]["per_subject"]["ada"] = 4
    ledger["limits"]["per_subject"]["ben"] = 3
    ledger["limits"]["per_subject_house"]["ada"]["house-a"] = 4
    ledger["limits"]["per_subject_style"]["ada"]["hinge"] = 3
    ledger["limits"]["per_house_space"]["house-a"]["vault"] = 4
    ledger["limits"]["per_house_space"]["house-a"]["ops"] = 2
    ledger["limits"]["per_house_space"]["house-b"]["vault"] = 2
    ledger["limits"]["per_house_space"]["house-b"]["lab"] = 2
    ledger["limits"]["per_house_style"]["house-a"]["spark"] = 3
    ledger["limits"]["per_house_style"]["house-a"]["hinge"] = 3
    ledger["limits"]["per_house_style"]["house-b"]["hinge"] = 2
    ledger["limits"]["per_house_style"]["house-b"]["tower"] = 2
    ledger["limits"]["per_round"]["6"] = 2
    ledger["limits"]["house_heat_budget"]["house-a"] = 30
    ledger["limits"]["house_heat_budget"]["house-b"] = 20
    ledger["limits"]["round_heat_budget"]["6"] = 20
    ledger["cohorts"][0] = {
        "members": ["r1", "r2", "r6"],
        "min_score": 2,
        "max_score": 3,
        "min_houses": 1,
        "min_styles": 2,
        "max_heat": 12,
    }
    return ledger


def reviewed_dense_ledger() -> dict:
    """Build a dense ledger with one extra piece that can satisfy review-board pressure."""
    ledger = dense_frontier_ledger()
    ledger["pieces"][0]["labels"].append("chair:night")
    ledger["pieces"][2]["labels"].append("chair:night")
    ledger["pieces"].append(
        {
            "id": "b4",
            "subject": "ben",
            "club": "ia",
            "style": "spark",
            "start_tick": 20,
            "end_tick": 100,
            "spent_tick": None,
            "spaces": ["lab", "vault"],
            "stances": ["forge", "scout"],
            "level": 5,
            "pair": "k2",
            "remaining": 1,
            "booster": True,
            "labels": ["anvil", "crest", "banner", "chair:night", "route:lab:vault", "dual"],
            "cooldown": 0,
        }
    )
    ledger["limits"]["per_house"]["house-a"] = 5
    ledger["limits"]["per_house_space"]["house-a"]["lab"] = 1
    ledger["limits"]["per_house_style"]["house-a"]["spark"] = 4
    ledger["limits"]["per_subject_house"]["ben"]["house-a"] = 1
    ledger["limits"]["per_subject_style"]["ben"]["spark"] = 1
    ledger["limits"]["allowed_house_handoffs"]["ben"] = ["house-b->house-a", "house-a->house-b", "house-b->house-b"]
    return ledger


def surge_dense_ledger(
    *,
    anchor: bool = True,
    waived: bool = True,
    repeat: bool = True,
    min_spaces: int = 3,
    min_houses: int = 2,
    max_heat: int = 3,
) -> dict:
    """Build a dense ledger where a round window constrains the final scoring row."""
    ledger = dense_frontier_ledger()
    if anchor:
        ledger["pieces"][5]["labels"].append("anchor:storm")
    if waived:
        ledger["pieces"][0]["labels"].append("surge-waive:storm")
    if repeat:
        ledger["pieces"][0]["labels"].append("surge-repeat:storm:ada")
        ledger["pieces"][5]["labels"].append("surge-repeat:storm:ada")
    ledger["surge_windows"] = [
        {
            "name": "storm",
            "rounds": [1, 2, 6],
            "max_heat": max_heat,
            "min_houses": min_houses,
            "min_spaces": min_spaces,
            "max_same_subject": 2,
            "anchor_label": "anchor:storm",
        }
    ]
    return ledger


def surge_window_variants() -> list[dict]:
    """Generate surge-window variants that bind with the existing frontier rules."""
    variants: list[dict] = []
    for anchor, waived, repeat, min_houses, min_spaces, max_heat in itertools.product(
        [False, True],
        [False, True],
        [False, True],
        [1, 2],
        [2, 3],
        [3, 9],
    ):
        ledger = surge_dense_ledger(
            anchor=anchor,
            waived=waived,
            repeat=repeat,
            min_houses=min_houses,
            min_spaces=min_spaces,
            max_heat=max_heat,
        )
        if not repeat:
            ledger["limits"]["per_subject_house"]["ada"]["house-b"] = 2
            ledger["limits"]["per_house"]["house-b"] = 4
            ledger["limits"]["per_house_space"]["house-b"]["vault"] = 2
            ledger["limits"]["per_house_style"]["house-b"]["hinge"] = 2
            ledger["limits"]["allowed_house_handoffs"]["ada"] = ["house-a->house-a"]
            ledger["pieces"].append(
                {
                    "id": "a4",
                    "subject": "ada",
                    "club": "ib",
                    "style": "hinge",
                    "start_tick": 10,
                    "end_tick": 90,
                    "spent_tick": None,
                    "spaces": ["vault"],
                    "stances": ["forge"],
                    "level": 4,
                    "pair": "k1",
                    "remaining": 1,
                    "booster": True,
                    "labels": ["door", "pool:door", "handoff:house-a:house-b"],
                    "cooldown": 0,
                }
            )
        variants.append(ledger)
    return variants


def relay_dense_ledger(
    *,
    first_edge: bool = True,
    second_edge: bool = True,
    subject_labels: bool = True,
    wide: bool = False,
    span: int = 6,
    distinct: int = 3,
    min_score: int = 4,
    member_order: list[str] | None = None,
) -> dict:
    """Build a dense ledger where explicit relay order changes the scoring row."""
    ledger = dense_frontier_ledger()
    members = member_order or ["r1", "r6", "r2", "r4"]
    if first_edge:
        ledger["pieces"][0]["labels"].append("relay:storm:r1:r6")
    if second_edge:
        ledger["pieces"][5]["labels"].append("relay:storm:r6:r2")
        ledger["pieces"][5]["labels"].append("relay:storm:r2:r4")
        ledger["pieces"][0]["labels"].append("relay:storm:r1:r2")
        ledger["pieces"][5]["labels"].append("relay:storm:r2:r6")
        ledger["pieces"][0]["labels"].append("relay:storm:r6:r4")
    if subject_labels:
        ledger["pieces"][0]["labels"].append("relay-subject:storm:ada")
        ledger["pieces"][5]["labels"].append("relay-subject:storm:ada")
    if wide:
        ledger["pieces"][0]["labels"].append("relay-wide:storm")
        ledger["pieces"][3]["labels"].append("relay-wide:storm")
        ledger["pieces"][5]["labels"].append("relay-wide:storm")
    ledger["relay_paths"] = [
        {
            "name": "storm",
            "members": members,
            "min_score": min_score,
            "max_round_span": span,
            "min_distinct_pieces": distinct,
            "edge_label_prefix": "relay:storm",
        }
    ]
    return ledger


def relay_path_variants() -> list[dict]:
    """Generate relay-path variants over edge labels, path order, round span, and piece spread."""
    variants: list[dict] = []
    orders = [
        ["r1", "r6", "r2", "r4"],
        ["r1", "r2", "r6", "r4"],
    ]
    for first_edge, second_edge, subject_labels, wide, span, distinct, min_score, order in itertools.product(
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [3, 6],
        [3, 5],
        [3, 4],
        orders,
    ):
        ledger = relay_dense_ledger(
            first_edge=first_edge,
            second_edge=second_edge,
            subject_labels=subject_labels,
            wide=wide,
            span=span,
            distinct=distinct,
            min_score=min_score,
            member_order=order,
        )
        variants.append(ledger)
    return variants


def track_dense_ledger(
    *,
    override: bool = True,
    duplicate_override: bool = False,
    reset: bool = False,
    guard: bool = False,
    spike: bool = False,
    finish_min: int = 7,
    finish_max: int = 9,
    max_value: int = 10,
) -> dict:
    """Build a dense ledger where an ordered score track constrains the final line."""
    ledger = dense_frontier_ledger()
    if override:
        ledger["pieces"][0]["labels"].append("track:storm:r6:-2")
    if duplicate_override:
        ledger["pieces"][0]["labels"].append("track:storm:r6:-5")
    if spike:
        ledger["pieces"][5]["labels"].append("track:storm:r2:12")
    if guard:
        ledger["pieces"][5]["labels"].append("track-guard:storm")
    if reset:
        ledger["pieces"][3]["labels"].append("track-reset:storm")
    ledger["score_tracks"] = [
        {
            "name": "storm",
            "members": ["r1", "r2", "r4", "r6"],
            "start": 0,
            "min_value": 0,
            "max_value": max_value,
            "finish_min": finish_min,
            "finish_max": finish_max,
        }
    ]
    return ledger


def score_track_variants() -> list[dict]:
    """Generate score-track variants over override, guard, reset, and finish boundaries."""
    variants: list[dict] = []
    for override, duplicate, reset, guard, spike, finish_band in itertools.product(
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [(1, 3), (7, 9)],
    ):
        finish_min, finish_max = finish_band
        ledger = track_dense_ledger(
            override=override,
            duplicate_override=duplicate,
            reset=reset,
            guard=guard,
            spike=spike,
            finish_min=finish_min,
            finish_max=finish_max,
        )
        variants.append(ledger)
    return variants


def backup_dense_ledger(
    *,
    label_a: bool = True,
    label_b: bool = True,
    house_diverse: bool = True,
    burden_cap: int = 3,
    min_backups: int = 2,
    min_backup_houses: int = 2,
    members: list[str] | None = None,
    add_early_heavy: bool = False,
) -> dict:
    """Build a dense ledger where scored turns need playable backup pieces."""
    ledger = dense_frontier_ledger()
    backup_label = "backup:storm"
    ledger["pieces"].append(
        {
            "id": "a0-heavy" if add_early_heavy else "a5",
            "subject": "ada",
            "club": "ia",
            "style": "hinge" if add_early_heavy else "spark",
            "start_tick": 10,
            "end_tick": 90,
            "spent_tick": None,
            "spaces": ["vault", "ops"],
            "stances": ["forge", "captain"],
            "level": 4,
            "pair": "k1",
            "remaining": 1,
            "booster": True,
            "labels": ["door", "rune", "crest"] + ([backup_label] if label_a else []),
            "cooldown": 0,
        }
    )
    ledger["pieces"].append(
        {
            "id": "a6",
            "subject": "ada",
            "club": "ib" if house_diverse else "ia",
            "style": "hinge",
            "start_tick": 10,
            "end_tick": 90,
            "spent_tick": None,
            "spaces": ["vault", "ops"],
            "stances": ["forge", "captain"],
            "level": 4,
            "pair": "k1",
            "remaining": 1,
            "booster": True,
            "labels": ["door", "rune", "crest"] + ([backup_label] if label_b else []),
            "cooldown": 0,
        }
    )
    ledger["backup_sets"] = [
        {
            "name": "storm",
            "members": members or ["r1", "r2", "r6"],
            "min_backups": min_backups,
            "min_backup_houses": min_backup_houses,
            "max_backup_burden": burden_cap,
            "backup_label": backup_label,
        }
    ]
    return ledger


def backup_set_variants() -> list[dict]:
    """Generate backup-set variants over labels, houses, burden cap, and member scope."""
    variants: list[dict] = []
    member_sets = [["r1", "r2", "r6"], ["r1"], ["r2", "r6"]]
    for label_a, label_b, house_diverse, burden_cap, min_backups, members, early in itertools.product(
        [False, True],
        [False, True],
        [False, True],
        [2, 3, 4],
        [1, 2],
        member_sets,
        [False, True],
    ):
        variants.append(
            backup_dense_ledger(
                label_a=label_a,
                label_b=label_b,
                house_diverse=house_diverse,
                burden_cap=burden_cap,
                min_backups=min_backups,
                min_backup_houses=min(2, min_backups),
                members=members,
                add_early_heavy=early,
            )
        )
    return variants


def lexicographic_tie_ledger() -> dict:
    """Build a tiny ledger where only the final turn=piece string breaks the tie."""
    return {
        "playable_houses": ["house-a"],
        "style_order": ["spark"],
        "clubs": [
            {"id": "ia", "house": "house-a", "disabled": False, "allowed_styles": ["spark"], "max_heat": 10}
        ],
        "limits": {
            "per_house": {"house-a": 2},
            "per_space": {"vault": 2},
            "per_subject": {"ada": 2},
            "per_subject_house": {"ada": {"house-a": 2}},
            "per_subject_style": {"ada": {"spark": 2}},
            "per_house_space": {"house-a": {"vault": 2}},
            "per_house_style": {"house-a": {"spark": 2}},
            "per_round": {"1": 1},
            "subject_round_gap": {"ada": 0},
            "per_badge": {"door": 3},
            "allowed_transitions": {"vault": ["vault"]},
            "allowed_house_handoffs": {"ada": ["house-a->house-a"]},
            "house_heat_budget": {"house-a": 10},
            "stance_space_gap": {"forge": {"vault": 0}},
            "split_badge": [],
            "family_cap": {},
            "club_round_gap": {},
            "blocked_house_pairs": [],
            "round_heat_budget": {"1": 10},
            "mutex_labels": [],
        },
        "exclusions": [],
        "cohorts": [],
        "pieces": [
            {
                "id": "z-piece",
                "subject": "ada",
                "club": "ia",
                "style": "spark",
                "start_tick": 0,
                "end_tick": 10,
                "spent_tick": None,
                "spaces": ["vault"],
                "stances": ["forge"],
                "level": 3,
                "pair": "k",
                "remaining": 1,
                "booster": True,
                "labels": ["door"],
                "cooldown": 0,
            },
            {
                "id": "a-piece",
                "subject": "ada",
                "club": "ia",
                "style": "spark",
                "start_tick": 0,
                "end_tick": 10,
                "spent_tick": None,
                "spaces": ["vault"],
                "stances": ["forge"],
                "level": 3,
                "pair": "k",
                "remaining": 1,
                "booster": True,
                "labels": ["door"],
                "cooldown": 0,
            },
        ],
        "turns": [
            {
                "id": "r1",
                "subject": "ada",
                "space": "vault",
                "stance": "forge",
                "at": 1,
                "level": 2,
                "pair": "k",
                "booster_required": False,
                "priority": 5,
                "heat": 2,
                "badge": ["door"],
                "round": 1,
                "links": [],
                "link_label": "",
            }
        ],
    }


def frontier_pressure_variants() -> list[dict]:
    """Generate dense ledgers that combine independent hard constraints."""
    variants: list[dict] = []
    for (
        pooled,
        ordered_bridge,
        rapid,
        routed,
        waived_heat,
        parallel,
        cohort_open,
        split_shared,
        exclusion_waived,
        club_burst,
        family_open,
        prerequisite_waived,
    ) in itertools.product(
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [False, True],
        [False, True],
    ):
        ledger = dense_frontier_ledger()
        if not pooled:
            ledger["pieces"][0]["labels"].remove("pool:door")
        ledger["limits"]["blocked_house_pairs"] = [["house-b", "house-a"]]
        if not ordered_bridge:
            for piece in ledger["pieces"]:
                piece["labels"] = [label for label in piece["labels"] if label != "bridge:house-b:house-a"]
                piece["labels"].append("bridge:house-a:house-b")
        ledger["limits"]["subject_round_gap"]["ada"] = 10
        if not rapid:
            ledger["pieces"][0]["labels"] = [label for label in ledger["pieces"][0]["labels"] if label != "rapid"]
            ledger["pieces"][5]["labels"] = [label for label in ledger["pieces"][5]["labels"] if label != "rapid"]
        ledger["limits"]["allowed_transitions"]["vault"] = []
        if routed:
            ledger["pieces"][0]["labels"].append("route:vault:ops")
        ledger["limits"]["house_heat_budget"]["house-a"] = 8
        ledger["limits"]["round_heat_budget"]["1"] = 8
        if waived_heat:
            ledger["pieces"][0]["labels"].extend(["heat-waive", "round-heat-waive:1"])
        ledger["limits"]["stance_space_gap"]["forge"]["vault"] = 6
        if parallel:
            ledger["pieces"][0]["labels"].append("parallel:forge:vault")
        if not cohort_open:
            ledger["cohorts"][0]["min_styles"] = 3
        ledger["limits"]["split_badge"] = ["door"]
        if split_shared:
            ledger["pieces"][0]["labels"].append("share:door")
        if not exclusion_waived:
            ledger["pieces"][0]["labels"] = [label for label in ledger["pieces"][0]["labels"] if label != "dual"]
            ledger["pieces"][5]["labels"] = [label for label in ledger["pieces"][5]["labels"] if label != "dual"]
        ledger["limits"]["club_round_gap"] = {"ia": 6}
        if club_burst:
            ledger["pieces"][0]["labels"].append("club-burst:ia")
            ledger["pieces"][5]["labels"].append("club-burst:ia")
        ledger["limits"]["family_cap"] = {"alpha": 2, "beta": 1 if family_open else 0}
        ledger["pieces"][0]["labels"].append("family:alpha")
        ledger["pieces"][5]["labels"].append("family:alpha")
        ledger["pieces"][2]["labels"].append("family:beta")
        ledger["pieces"][3]["labels"].append("family:beta")
        ledger["turns"][-1]["links"] = ["ghost"]
        ledger["turns"][-1]["link_label"] = "pool:door" if prerequisite_waived else "override"
        variants.append(ledger)
    return variants


def claim_market_ledger(
    *,
    second_house: bool = True,
    early_heavy: bool = False,
    claim_burden: int = 5,
    min_claims: int = 2,
) -> dict:
    """Build a dense ledger where selected pieces consume a shared reserve market."""
    ledger = dense_frontier_ledger()
    claim_label = "claim:storm"
    ledger["pieces"].append(
        {
            "id": "a0-heavy" if early_heavy else "a5",
            "subject": "ada",
            "club": "ia",
            "style": "tower" if early_heavy else "spark",
            "start_tick": 10,
            "end_tick": 90,
            "spent_tick": None,
            "spaces": ["vault", "ops"],
            "stances": ["forge", "captain"],
            "level": 4,
            "pair": "k1",
            "remaining": 1,
            "booster": True,
            "labels": ["door", "rune", "crest", claim_label],
            "cooldown": 0,
        }
    )
    ledger["pieces"].append(
        {
            "id": "a6",
            "subject": "ada",
            "club": "ib" if second_house else "ia",
            "style": "hinge",
            "start_tick": 10,
            "end_tick": 90,
            "spent_tick": None,
            "spaces": ["vault", "ops"],
            "stances": ["forge", "captain"],
            "level": 4,
            "pair": "k1",
            "remaining": 1,
            "booster": True,
            "labels": ["door", "rune", "crest", claim_label],
            "cooldown": 0,
        }
    )
    ledger["pieces"].append(
        {
            "id": "a7",
            "subject": "ada",
            "club": "ib" if second_house else "ia",
            "style": "hinge",
            "start_tick": 10,
            "end_tick": 90,
            "spent_tick": None,
            "spaces": ["vault", "ops"],
            "stances": ["forge", "captain"],
            "level": 4,
            "pair": "k1",
            "remaining": 1,
            "booster": True,
            "labels": ["door", "rune", "crest", claim_label],
            "cooldown": 0,
        }
    )
    ledger["claim_markets"] = [
        {
            "name": "storm",
            "members": ["r1", "r2", "r6"],
            "min_claims": min_claims,
            "min_claim_houses": 2,
            "max_claim_burden": claim_burden,
            "claim_label": claim_label,
        }
    ]
    ledger["limits"]["per_subject_house"]["ada"]["house-b"] = 2
    ledger["limits"]["per_house"]["house-b"] = 4
    ledger["limits"]["per_house_space"]["house-b"]["vault"] = 2
    ledger["limits"]["per_house_style"]["house-b"]["hinge"] = 2
    return ledger


def claim_market_variants() -> list[dict]:
    """Generate claim-market variants over reserve order, house spread, and burden limits."""
    variants: list[dict] = []
    for second_house, early_heavy, burden, min_claims in itertools.product(
        [False, True],
        [False, True],
        [3, 4, 5],
        [1, 2, 3],
    ):
        variants.append(
            claim_market_ledger(
                second_house=second_house,
                early_heavy=early_heavy,
                claim_burden=burden,
                min_claims=min_claims,
            )
        )
    return variants


def ladder_ledger(
    *,
    pattern: str = "up-down",
    max_gap: int = 5,
    free_pair: bool = False,
    wide: bool = False,
    min_score: int = 4,
) -> dict:
    """Build a dense ledger where ordered style movement constrains the scoring row."""
    ledger = dense_frontier_ledger()
    if free_pair:
        ledger["pieces"][0]["labels"].append("ladder-free:storm:r1:r2")
        ledger["pieces"][5]["labels"].append("ladder-free:storm:r1:r2")
    if wide:
        ledger["pieces"][0]["labels"].append("ladder-wide:storm")
    ledger["round_ladders"] = [
        {
            "name": "storm",
            "members": ["r1", "r2", "r4", "r6"],
            "min_score": min_score,
            "pattern": pattern,
            "max_round_gap": max_gap,
            "free_label_prefix": "ladder-free:storm",
        }
    ]
    return ledger


def ladder_variants() -> list[dict]:
    """Generate round-ladder variants over pattern, round span, and pair waivers."""
    variants: list[dict] = []
    for pattern, max_gap, free_pair, wide, min_score in itertools.product(
        ["up-down", "down-up"],
        [2, 5],
        [False, True],
        [False, True],
        [3, 4],
    ):
        variants.append(
            ladder_ledger(
                pattern=pattern,
                max_gap=max_gap,
                free_pair=free_pair,
                wide=wide,
                min_score=min_score,
            )
        )
    return variants


def test_public_input_has_not_been_changed():
    """Verify the public ledger remains the original task input."""
    digest = hashlib.sha256(PUBLIC.read_bytes()).hexdigest()
    assert digest == PUBLIC_SHA256


def test_lantern_table_scorer_is_present():
    """Verify the lantern-grid referee exists at the required path and is runnable."""
    assert BIN.exists(), f"{BIN} does not exist"
    mode = BIN.stat().st_mode
    assert mode & stat.S_IXUSR, f"{BIN} is not runnable"


def test_public_match_ledger_follows_rule_sheet():
    """Verify the public match ledger follows the documented rule sheet."""
    ledger = load_json(PUBLIC)
    actual = run_gate(ledger, "public")
    assert actual == expected_scorecard(ledger)


def test_generated_match_drills_follow_the_same_rules():
    """Verify match drills covering quotas, ordering, playability failures, and ties."""
    for idx, ledger in enumerate(generated_variants()):
        actual = run_gate(ledger, f"variant_{idx:02d}")
        assert actual == expected_scorecard(ledger)


def test_combined_frontier_pressure_matrix_links_global_rule_composition():
    """Verify combined dense variants where several optional final-plan rules interact at once."""
    observed_summaries = set()
    for idx, ledger in enumerate(frontier_pressure_variants()):
        actual = run_gate(ledger, f"frontier_pressure_{idx:02d}")
        expected = expected_scorecard(ledger)
        assert actual == expected
        observed_summaries.add(tuple(expected["summary"].values()))
    assert len(observed_summaries) >= 2


def test_repeated_badge_links_pooling_before_high_priority_admission():
    """Verify repeated badge strings consume repeated slots unless a piece pools that badge."""
    pooled = dense_frontier_ledger()
    actual = run_gate(pooled, "dense_repeated_badge_pool")
    expected = expected_scorecard(pooled)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5
    assert any(item["turn_id"] == "r6" and item["piece_id"] == "a1" for item in actual["scored"])

    unpooled = dense_frontier_ledger()
    unpooled["pieces"][0]["labels"].remove("pool:door")
    actual = run_gate(unpooled, "dense_repeated_badge_no_pool")
    expected = expected_scorecard(unpooled)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 4
    assert any(item["turn_id"] == "r6" and item["reasons"] == ["not_selected"] for item in actual["missed"])


def test_blocked_house_pair_bridge_uses_ledger_pair_order():
    """Verify bridge labels are checked with the left/right house order from the ledger."""
    correct_order = dense_frontier_ledger()
    correct_order["limits"]["blocked_house_pairs"] = [["house-b", "house-a"]]
    actual = run_gate(correct_order, "dense_ordered_bridge_ok")
    expected = expected_scorecard(correct_order)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5

    wrong_order = dense_frontier_ledger()
    wrong_order["limits"]["blocked_house_pairs"] = [["house-a", "house-b"]]
    actual = run_gate(wrong_order, "dense_ordered_bridge_wrong")
    expected = expected_scorecard(wrong_order)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 3
    assert [item["turn_id"] for item in actual["scored"]] == ["r1", "r2", "r6"]


def test_family_and_mutex_caps_are_applied_to_the_final_global_plan():
    """Verify dense final-state caps can force a lower-priority subset after all options are playable."""
    family_limited = dense_frontier_ledger()
    family_limited["limits"]["family_cap"] = {"alpha": 2, "beta": 1}
    family_limited["pieces"][0]["labels"].append("family:alpha")
    family_limited["pieces"][4]["labels"].append("family:alpha")
    family_limited["pieces"][2]["labels"].append("family:beta")
    family_limited["pieces"][3]["labels"].append("family:beta")
    actual = run_gate(family_limited, "dense_family_cap")
    expected = expected_scorecard(family_limited)
    assert actual == expected
    assert expected["summary"] == {
        "scored_count": 3,
        "priority": 23,
        "heat": 10,
        "style_burden": 4,
        "distinct_pieces": 2,
    }

    mutex_limited = dense_frontier_ledger()
    mutex_limited["limits"]["mutex_labels"] = ["hot"]
    mutex_limited["pieces"][2]["labels"].extend(["hot", "mutex-ok:hot"])
    mutex_limited["pieces"][3]["labels"].append("hot")
    actual = run_gate(mutex_limited, "dense_mutex_cap")
    expected = expected_scorecard(mutex_limited)
    assert actual == expected
    assert [item["turn_id"] for item in actual["scored"]] == ["r1", "r2", "r6"]


def test_additive_miss_reasons_are_aggregated_in_contract_order():
    """Verify no-option misss union same-subject piece failures without short-circuiting."""
    ledger = copy.deepcopy(variant_base())
    ledger["turns"] = [
        {
            "id": "rx",
            "subject": "ada",
            "space": "lab",
            "stance": "scout",
            "at": 200,
            "level": 9,
            "pair": "bad",
            "booster_required": True,
            "priority": 1,
            "heat": 99,
            "badge": ["missing"],
            "round": 1,
            "links": [],
            "link_label": "",
        }
    ]
    actual = run_gate(ledger, "dense_additive_miss")
    expected = expected_scorecard(ledger)
    assert actual == expected
    assert actual["missed"] == [
        {
            "turn_id": "rx",
            "reasons": [
                "late",
                "spent",
                "space_miss",
                "level_miss",
                "heat_limit",
                "badge_miss",
                "pair_miss",
                "booster_missing",
            ],
        }
    ]


def test_plan_leveling_prefers_style_burden_before_piece_id_lexicographic_order():
    """Verify a lower-burden style wins even when the lower piece id would sort first."""
    ledger = {
        "playable_houses": ["house-a", "house-b"],
        "style_order": ["spark", "hinge", "tower"],
        "clubs": [
            {"id": "ia", "house": "house-a", "disabled": False, "allowed_styles": ["spark", "hinge"], "max_heat": 10},
            {"id": "ib", "house": "house-b", "disabled": False, "allowed_styles": ["hinge"], "max_heat": 10},
        ],
        "limits": {
            "per_house": {"house-a": 2, "house-b": 2},
            "per_space": {"vault": 2},
            "per_subject": {"ada": 2},
            "per_subject_house": {"ada": {"house-a": 2, "house-b": 2}},
            "per_subject_style": {"ada": {"spark": 2, "hinge": 2, "tower": 0}},
            "per_house_space": {"house-a": {"vault": 2}, "house-b": {"vault": 2}},
            "per_house_style": {"house-a": {"spark": 2, "hinge": 2}, "house-b": {"hinge": 2}},
            "per_round": {"1": 1},
            "subject_round_gap": {"ada": 0},
            "per_badge": {"door": 2},
            "allowed_transitions": {"vault": ["vault"]},
            "allowed_house_handoffs": {"ada": ["house-a->house-a", "house-a->house-b", "house-b->house-a", "house-b->house-b"]},
            "house_heat_budget": {"house-a": 10, "house-b": 10},
            "stance_space_gap": {"forge": {"vault": 0}},
            "split_badge": [],
            "family_cap": {},
            "club_round_gap": {},
            "blocked_house_pairs": [],
            "round_heat_budget": {"1": 10},
            "mutex_labels": [],
        },
        "exclusions": [],
        "cohorts": [],
        "pieces": [
            {
                "id": "p-piece",
                "subject": "ada",
                "club": "ib",
                "style": "hinge",
                "start_tick": 0,
                "end_tick": 10,
                "spent_tick": None,
                "spaces": ["vault"],
                "stances": ["forge"],
                "level": 3,
                "pair": "k",
                "remaining": 1,
                "booster": True,
                "labels": ["door"],
                "cooldown": 0,
            },
            {
                "id": "e-piece",
                "subject": "ada",
                "club": "ia",
                "style": "spark",
                "start_tick": 0,
                "end_tick": 10,
                "spent_tick": None,
                "spaces": ["vault"],
                "stances": ["forge"],
                "level": 3,
                "pair": "k",
                "remaining": 1,
                "booster": True,
                "labels": ["door"],
                "cooldown": 0,
            },
        ],
        "turns": [
            {
                "id": "r1",
                "subject": "ada",
                "space": "vault",
                "stance": "forge",
                "at": 1,
                "level": 2,
                "pair": "k",
                "booster_required": False,
                "priority": 5,
                "heat": 2,
                "badge": ["door"],
                "round": 1,
                "links": [],
                "link_label": "",
            }
        ],
    }
    actual = run_gate(ledger, "dense_style_burden_tie")
    expected = expected_scorecard(ledger)
    assert actual == expected
    assert actual["scored"][0]["piece_id"] == "e-piece"
    assert actual["summary"]["style_burden"] == 1


def test_house_and_round_heat_waivers_are_scoped_to_selected_piece_labels():
    """Verify heat waivers only remove the selected piece's house and round budget pressure."""
    no_waiver = dense_frontier_ledger()
    no_waiver["limits"]["house_heat_budget"]["house-a"] = 8
    no_waiver["limits"]["round_heat_budget"]["1"] = 8
    actual = run_gate(no_waiver, "dense_heat_no_waiver")
    expected = expected_scorecard(no_waiver)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 2

    waived = dense_frontier_ledger()
    waived["limits"]["house_heat_budget"]["house-a"] = 8
    waived["limits"]["round_heat_budget"]["1"] = 8
    waived["pieces"][0]["labels"].extend(["heat-waive", "round-heat-waive:1"])
    actual = run_gate(waived, "dense_heat_waiver")
    expected = expected_scorecard(waived)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5


def test_split_badge_links_share_label_for_same_house_reuse():
    """Verify split badge blocks same-house reuse unless every affected piece carries share:<badge>."""
    no_share = dense_frontier_ledger()
    no_share["limits"]["split_badge"] = ["door"]
    actual = run_gate(no_share, "dense_split_badge_no_share")
    expected = expected_scorecard(no_share)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 4
    assert any(item["turn_id"] == "r6" and item["reasons"] == ["not_selected"] for item in actual["missed"])

    shared = dense_frontier_ledger()
    shared["limits"]["split_badge"] = ["door"]
    shared["pieces"][0]["labels"].append("share:door")
    actual = run_gate(shared, "dense_split_badge_share")
    expected = expected_scorecard(shared)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5


def test_subject_house_handoff_label_can_unlock_cross_house_replacement_plan():
    """Verify consecutive same-subject house changes use ordered handoff labels from the selected piece."""
    no_handoff = dense_frontier_ledger()
    no_handoff["limits"]["allowed_house_handoffs"]["ada"] = ["house-a->house-a"]
    no_handoff["limits"]["per_subject_house"]["ada"]["house-a"] = 2
    no_handoff["limits"]["per_subject_house"]["ada"]["house-b"] = 2
    no_handoff["limits"]["per_house"]["house-b"] = 4
    no_handoff["limits"]["per_house_space"]["house-b"]["vault"] = 2
    no_handoff["limits"]["per_house_style"]["house-b"]["hinge"] = 2
    no_handoff["pieces"].append(
        {
            "id": "a4",
            "subject": "ada",
            "club": "ib",
            "style": "hinge",
            "start_tick": 10,
            "end_tick": 90,
            "spent_tick": None,
            "spaces": ["vault"],
            "stances": ["forge"],
            "level": 4,
            "pair": "k1",
            "remaining": 1,
            "booster": True,
            "labels": ["door", "pool:door"],
            "cooldown": 0,
        }
    )
    actual = run_gate(no_handoff, "dense_handoff_no_label")
    expected = expected_scorecard(no_handoff)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 4

    with_handoff = copy.deepcopy(no_handoff)
    with_handoff["pieces"][-1]["labels"].append("handoff:house-a:house-b")
    actual = run_gate(with_handoff, "dense_handoff_label")
    expected = expected_scorecard(with_handoff)
    assert actual == expected
    assert any(item["turn_id"] == "r6" and item["piece_id"] == "a4" for item in actual["scored"])


def test_final_leveling_uses_lexicographic_joined_assignment_as_last_tiebreak():
    """Verify the last comparator is the sorted turn_id=piece_id string, not piece input order."""
    ledger = lexicographic_tie_ledger()
    actual = run_gate(ledger, "dense_lexicographic_tie")
    expected = expected_scorecard(ledger)
    assert actual == expected
    assert actual["scored"] == [
        {"turn_id": "r1", "piece_id": "a-piece", "house": "house-a", "space": "vault", "priority": 5, "heat": 2}
    ]


def test_same_piece_cooldown_forces_distinct_replacement_piece():
    """Verify the same-piece cooldown is evaluated across the final selected turn rounds."""
    blocked = dense_frontier_ledger()
    blocked["pieces"][0]["cooldown"] = 10
    actual = run_gate(blocked, "dense_cooldown_blocked")
    expected = expected_scorecard(blocked)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 4

    alternate = dense_frontier_ledger()
    alternate["pieces"][0]["cooldown"] = 10
    alternate["limits"]["per_house_style"]["house-a"]["spark"] = 4
    alternate["pieces"].append(
        {
            "id": "a4",
            "subject": "ada",
            "club": "ia",
            "style": "spark",
            "start_tick": 10,
            "end_tick": 90,
            "spent_tick": None,
            "spaces": ["vault"],
            "stances": ["forge"],
            "level": 4,
            "pair": "k1",
            "remaining": 1,
            "booster": True,
            "labels": ["door", "pool:door"],
            "cooldown": 0,
        }
    )
    actual = run_gate(alternate, "dense_cooldown_alternate")
    expected = expected_scorecard(alternate)
    assert actual == expected
    assert any(item["turn_id"] == "r6" and item["piece_id"] == "a4" for item in actual["scored"])


def test_same_stance_space_gap_links_parallel_label_on_both_selected_pieces():
    """Verify same stance/space round spacing is waived only by parallel:<stance>:<space> labels."""
    no_parallel = dense_frontier_ledger()
    no_parallel["limits"]["stance_space_gap"]["forge"]["vault"] = 6
    actual = run_gate(no_parallel, "dense_stance_space_gap_no_parallel")
    expected = expected_scorecard(no_parallel)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 4

    parallel = dense_frontier_ledger()
    parallel["limits"]["stance_space_gap"]["forge"]["vault"] = 6
    parallel["pieces"][0]["labels"].append("parallel:forge:vault")
    actual = run_gate(parallel, "dense_stance_space_gap_parallel")
    expected = expected_scorecard(parallel)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5


def test_exclusion_unless_label_must_be_present_on_both_selected_sides():
    """Verify exclusion waivers are bilateral and apply to the final selected pieces."""
    blocked = dense_frontier_ledger()
    blocked["pieces"][0]["labels"].remove("dual")
    blocked["pieces"][5]["labels"].remove("dual")
    actual = run_gate(blocked, "dense_exclusion_no_dual")
    expected = expected_scorecard(blocked)
    assert actual == expected
    assert [item["turn_id"] for item in actual["scored"]] == ["r3", "r4"]

    waived = dense_frontier_ledger()
    actual = run_gate(waived, "dense_exclusion_dual")
    expected = expected_scorecard(waived)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5


def test_cohort_diversity_limits_can_reject_high_priority_member_block():
    """Verify cohort min-houses and min-styles constraints are enforced after option selection."""
    min_styles = dense_frontier_ledger()
    min_styles["cohorts"][0]["min_styles"] = 3
    actual = run_gate(min_styles, "dense_cohort_min_styles")
    expected = expected_scorecard(min_styles)
    assert actual == expected
    assert [item["turn_id"] for item in actual["scored"]] == ["r3", "r4"]

    min_houses = dense_frontier_ledger()
    min_houses["cohorts"][0]["min_houses"] = 2
    actual = run_gate(min_houses, "dense_cohort_min_houses")
    expected = expected_scorecard(min_houses)
    assert actual == expected
    assert [item["turn_id"] for item in actual["scored"]] == ["r3", "r4"]


def test_review_board_chair_quorum_can_force_replacement_piece():
    """Verify review board chair labels are counted per scored member turn."""
    ledger = reviewed_dense_ledger()
    ledger["review_boards"] = [
        {
            "name": "night",
            "members": ["r1", "r2", "r3", "r4", "r6"],
            "chair_label": "chair:night",
            "min_chairs": 3,
            "min_houses": 1,
            "min_styles": 1,
            "max_same_club": 5,
        }
    ]
    actual = run_gate(ledger, "dense_review_chair_quorum")
    expected = expected_scorecard(ledger)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5
    assert any(item["turn_id"] == "r4" and item["piece_id"] == "b4" for item in actual["scored"])


def test_review_board_house_and_style_diversity_bind_after_leveling():
    """Verify review board house and style diversity apply to the selected member pieces."""
    house_diverse = reviewed_dense_ledger()
    house_diverse["review_boards"] = [
        {
            "name": "night",
            "members": ["r3", "r4"],
            "chair_label": "chair:night",
            "min_chairs": 1,
            "min_houses": 2,
            "min_styles": 1,
            "max_same_club": 2,
        }
    ]
    actual = run_gate(house_diverse, "dense_review_house_diverse")
    expected = expected_scorecard(house_diverse)
    assert actual == expected
    assert any(item["turn_id"] == "r4" and item["piece_id"] == "b4" for item in actual["scored"])

    style_diverse = reviewed_dense_ledger()
    style_diverse["review_boards"] = [
        {
            "name": "night",
            "members": ["r3", "r4"],
            "chair_label": "chair:night",
            "min_chairs": 1,
            "min_houses": 1,
            "min_styles": 2,
            "max_same_club": 2,
        }
    ]
    actual = run_gate(style_diverse, "dense_review_style_diverse")
    expected = expected_scorecard(style_diverse)
    assert actual == expected
    assert any(item["turn_id"] == "r4" and item["piece_id"] == "b4" for item in actual["scored"])


def test_review_board_same_club_cap_can_reject_otherwise_best_block():
    """Verify review board max_same_club counts scored member turns sharing an club."""
    ledger = reviewed_dense_ledger()
    ledger["review_boards"] = [
        {
            "name": "night",
            "members": ["r1", "r2", "r6"],
            "chair_label": "chair:night",
            "min_chairs": 1,
            "min_houses": 1,
            "min_styles": 1,
            "max_same_club": 2,
        }
    ]
    actual = run_gate(ledger, "dense_review_club_cap")
    expected = expected_scorecard(ledger)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 4
    assert any(item["turn_id"] == "r6" and item["reasons"] == ["not_selected"] for item in actual["missed"])


def test_surge_window_anchor_and_heat_waiver_bind_to_selected_pieces():
    """Verify surge windows require an anchor piece and apply heat waivers per selected turn."""
    scored = surge_dense_ledger()
    actual = run_gate(scored, "dense_surge_window_full")
    expected = expected_scorecard(scored)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5

    no_anchor = surge_dense_ledger(anchor=False)
    actual = run_gate(no_anchor, "dense_surge_window_no_anchor")
    expected = expected_scorecard(no_anchor)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5

    no_waiver = surge_dense_ledger(waived=False)
    actual = run_gate(no_waiver, "dense_surge_window_no_waiver")
    expected = expected_scorecard(no_waiver)
    assert actual == expected
    assert expected["summary"]["heat"] < 16


def test_surge_window_repeat_subject_and_spread_rules_change_the_frontier():
    """Verify surge windows enforce repeated-subject waivers plus house and space spread together."""
    no_repeat = surge_dense_ledger(repeat=False)
    actual = run_gate(no_repeat, "dense_surge_window_no_repeat")
    expected = expected_scorecard(no_repeat)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5

    too_many_spaces = surge_dense_ledger(min_spaces=4)
    actual = run_gate(too_many_spaces, "dense_surge_window_space_spread")
    expected = expected_scorecard(too_many_spaces)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5

    too_many_houses = surge_dense_ledger(min_houses=3)
    actual = run_gate(too_many_houses, "dense_surge_window_house_spread")
    expected = expected_scorecard(too_many_houses)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5


def test_surge_window_pressure_matrix_is_compatible_with_other_frontier_rules():
    """Verify generated surge-window drills compose with handoff, leveling, heat, and diversity rules."""
    observed = set()
    full_count = 0
    for idx, ledger in enumerate(surge_window_variants()):
        actual = run_gate(ledger, f"dense_surge_matrix_{idx:02d}")
        expected = expected_scorecard(ledger)
        assert actual == expected
        observed.add(tuple(expected["summary"].values()))
        if expected["summary"]["scored_count"] == 5:
            full_count += 1
    assert len(observed) >= 4
    assert 0 < full_count < len(surge_window_variants())


def test_relay_path_uses_member_order_edges_not_round_order():
    """Verify relay paths follow the explicit member order after filtering scored members."""
    default_order = relay_dense_ledger()
    actual = run_gate(default_order, "dense_relay_member_order")
    expected = expected_scorecard(default_order)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5

    alternate_order = relay_dense_ledger(member_order=["r1", "r2", "r6", "r4"])
    actual = run_gate(alternate_order, "dense_relay_alternate_order")
    expected = expected_scorecard(alternate_order)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5

    missing_edge = relay_dense_ledger(second_edge=False)
    actual = run_gate(missing_edge, "dense_relay_missing_pair_edge")
    expected = expected_scorecard(missing_edge)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5


def test_relay_path_subject_span_and_distinct_piece_rules_are_final_state_checks():
    """Verify relay same-subject labels, round span waiver, and piece spread apply to selected pieces."""
    no_subject_labels = relay_dense_ledger(subject_labels=False)
    actual = run_gate(no_subject_labels, "dense_relay_no_subject_labels")
    expected = expected_scorecard(no_subject_labels)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5

    span_blocked = relay_dense_ledger(span=3)
    actual = run_gate(span_blocked, "dense_relay_span_blocked")
    expected = expected_scorecard(span_blocked)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5

    span_waived = relay_dense_ledger(span=3, wide=True)
    actual = run_gate(span_waived, "dense_relay_span_waived")
    expected = expected_scorecard(span_waived)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5

    piece_spread = relay_dense_ledger(distinct=5)
    actual = run_gate(piece_spread, "dense_relay_piece_spread")
    expected = expected_scorecard(piece_spread)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5


def test_relay_path_pressure_matrix_adds_ordered_global_frontier_pressure():
    """Verify generated relay drills vary ordered edge labels, span waivers, and selected-piece spread."""
    observed = set()
    full_count = 0
    partial_count = 0
    for idx, ledger in enumerate(relay_path_variants()):
        actual = run_gate(ledger, f"dense_relay_matrix_{idx:03d}")
        expected = expected_scorecard(ledger)
        assert actual == expected
        observed.add(tuple(expected["summary"].values()))
        if expected["summary"]["scored_count"] == 5:
            full_count += 1
        if expected["summary"]["scored_count"] == 4:
            partial_count += 1
    assert len(observed) >= 3
    assert full_count > 0
    assert partial_count > 0


def test_relay_path_pair_checks_remain_local_with_multiple_paths():
    """Verify separate relay paths do not share edge labels, span waivers, or same-subject labels."""
    ledger = relay_dense_ledger(wide=True)
    ledger["relay_paths"].append(
        {
            "name": "ember",
            "members": ["r4", "r2", "r6", "r1"],
            "min_score": 4,
            "max_round_span": 2,
            "min_distinct_pieces": 3,
            "edge_label_prefix": "relay:ember",
        }
    )
    ledger["pieces"][0]["labels"].extend(
        [
            "relay-wide:ember",
            "relay:ember:r4:r2",
            "relay:ember:r2:r6",
            "relay:ember:r6:r1",
            "relay-subject:ember:ada",
        ]
    )
    ledger["pieces"][3]["labels"].extend(
        [
            "relay-wide:ember",
            "relay:ember:r4:r2",
            "relay:ember:r2:r6",
            "relay:ember:r6:r1",
        ]
    )
    ledger["pieces"][5]["labels"].extend(
        [
            "relay-wide:ember",
            "relay:ember:r4:r2",
            "relay:ember:r2:r6",
            "relay:ember:r6:r1",
            "relay-subject:ember:ada",
        ]
    )
    actual = run_gate(ledger, "dense_relay_two_local_paths")
    expected = expected_scorecard(ledger)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5


def test_score_track_override_and_finish_band_change_the_frontier():
    """Verify score tracks use selected-piece deltas and final finish limits in round order."""
    full = track_dense_ledger()
    actual = run_gate(full, "dense_track_full_override")
    expected = expected_scorecard(full)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5

    no_override = track_dense_ledger(override=False)
    actual = run_gate(no_override, "dense_track_no_override")
    expected = expected_scorecard(no_override)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 4

    reset_needed = track_dense_ledger(finish_min=1, finish_max=3)
    actual = run_gate(reset_needed, "dense_track_reset_missing")
    expected = expected_scorecard(reset_needed)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5

    reset_ok = track_dense_ledger(reset=True, finish_min=1, finish_max=3)
    actual = run_gate(reset_ok, "dense_track_reset_ok")
    expected = expected_scorecard(reset_ok)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5


def test_score_track_guard_scope_and_lexicographic_override_label():
    """Verify track guards are per-step only and duplicate delta labels use lexicographic order."""
    duplicate = track_dense_ledger(duplicate_override=True)
    actual = run_gate(duplicate, "dense_track_duplicate_override")
    expected = expected_scorecard(duplicate)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5

    no_guard = track_dense_ledger(spike=True, reset=True, finish_min=1, finish_max=3)
    actual = run_gate(no_guard, "dense_track_spike_no_guard")
    expected = expected_scorecard(no_guard)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5

    guarded = track_dense_ledger(spike=True, guard=True, reset=True, finish_min=1, finish_max=3)
    actual = run_gate(guarded, "dense_track_spike_guarded")
    expected = expected_scorecard(guarded)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5


def test_score_track_pressure_matrix_links_ordered_running_state():
    """Verify generated score-track drills vary override labels, guards, resets, and finish ranges."""
    observed = set()
    scored_counts = set()
    for idx, ledger in enumerate(score_track_variants()):
        actual = run_gate(ledger, f"dense_score_track_matrix_{idx:02d}")
        expected = expected_scorecard(ledger)
        assert actual == expected
        observed.add(tuple(expected["summary"].values()))
        scored_counts.add(expected["summary"]["scored_count"])
    assert len(observed) >= 5
    assert {0, 4, 5}.issubset(scored_counts)


def test_backup_set_links_unselected_playable_piece_pool():
    """Verify scored members need backup pieces that are playable but not selected."""
    full = backup_dense_ledger()
    actual = run_gate(full, "dense_backup_full")
    expected = expected_scorecard(full)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5

    missing_label = backup_dense_ledger(label_b=False)
    actual = run_gate(missing_label, "dense_backup_missing_label")
    expected = expected_scorecard(missing_label)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5

    same_house = backup_dense_ledger(house_diverse=False)
    actual = run_gate(same_house, "dense_backup_same_house")
    expected = expected_scorecard(same_house)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5


def test_backup_set_uses_piece_id_order_for_checked_backup_burden():
    """Verify backup checks use only the first min_backups pieces by piece id."""
    normal = backup_dense_ledger(burden_cap=3)
    actual = run_gate(normal, "dense_backup_burden_normal")
    expected = expected_scorecard(normal)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5

    tight = backup_dense_ledger(burden_cap=2)
    actual = run_gate(tight, "dense_backup_burden_tight")
    expected = expected_scorecard(tight)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5

    early_heavy = backup_dense_ledger(add_early_heavy=True)
    actual = run_gate(early_heavy, "dense_backup_early_heavy")
    expected = expected_scorecard(early_heavy)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5


def test_backup_set_pressure_matrix_checks_nonselected_option_state():
    """Verify generated backup drills vary backup labels, houses, burden caps, and member scopes."""
    observed = set()
    full_count = 0
    fallback_count = 0
    for idx, ledger in enumerate(backup_set_variants()):
        actual = run_gate(ledger, f"dense_backup_matrix_{idx:03d}")
        expected = expected_scorecard(ledger)
        assert actual == expected
        observed.add(tuple(expected["summary"].values()))
        if expected["summary"]["scored_count"] == 5:
            full_count += 1
        if expected["summary"]["scored_count"] == 2:
            fallback_count += 1
    assert len(observed) >= 2
    assert full_count > 0
    assert fallback_count > 0


def test_claim_market_reserves_are_claimed_globally_in_turn_order():
    """Verify claim markets reserve nonselected playable pieces once across scored members."""
    full = claim_market_ledger()
    actual = run_gate(full, "dense_claim_market_full")
    expected = expected_scorecard(full)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5

    same_house = claim_market_ledger(second_house=False)
    actual = run_gate(same_house, "dense_claim_market_same_house")
    expected = expected_scorecard(same_house)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5

    early_heavy = claim_market_ledger(early_heavy=True, claim_burden=5)
    actual = run_gate(early_heavy, "dense_claim_market_early_heavy")
    expected = expected_scorecard(early_heavy)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5


def test_claim_market_pressure_matrix_checks_reserve_order_and_burden():
    """Verify generated claim-market drills vary reserve houses, reserve order, and claim counts."""
    observed = set()
    full_count = 0
    fallback_count = 0
    for idx, ledger in enumerate(claim_market_variants()):
        actual = run_gate(ledger, f"dense_claim_market_matrix_{idx:03d}")
        expected = expected_scorecard(ledger)
        assert actual == expected
        observed.add(tuple(expected["summary"].values()))
        if expected["summary"]["scored_count"] == 5:
            full_count += 1
        if expected["summary"]["scored_count"] < 5:
            fallback_count += 1
    assert len(observed) >= 3
    assert full_count > 0
    assert fallback_count > 0


def test_claim_market_ignores_selected_claim_labeled_pieces_when_reserving():
    """Verify claim markets reserve only nonselected pieces from the regular pieces array."""
    ledger = claim_market_ledger()
    claim_label = ledger["claim_markets"][0]["claim_label"]
    for piece_id in ("a1", "a2"):
        for piece in ledger["pieces"]:
            if piece["id"] == piece_id and claim_label not in piece["labels"]:
                piece["labels"].append(claim_label)
    ledger["pieces"].append(
        {
            "id": "a00",
            "subject": "ada",
            "club": "ia",
            "style": "tower",
            "start_tick": 10,
            "end_tick": 90,
            "spent_tick": None,
            "spaces": ["vault", "ops"],
            "stances": ["forge", "captain"],
            "level": 4,
            "pair": "k1",
            "remaining": 1,
            "booster": True,
            "labels": ["door", "rune", "crest", claim_label],
            "cooldown": 0,
        }
    )
    ledger["claim_markets"][0]["max_claim_burden"] = 4
    actual = run_gate(ledger, "dense_claim_market_selected_labels_and_early_burden")
    expected = expected_scorecard(ledger)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5


def test_round_ladder_links_alternating_style_motion_and_pair_waivers():
    """Verify round ladders use round order and apply pair waivers only to their adjacent pair."""
    blocked = ladder_ledger(pattern="down-up")
    actual = run_gate(blocked, "dense_ladder_blocked")
    expected = expected_scorecard(blocked)
    assert actual == expected
    assert expected["summary"]["scored_count"] < 5

    waived = ladder_ledger(pattern="down-up", free_pair=True)
    actual = run_gate(waived, "dense_ladder_waived")
    expected = expected_scorecard(waived)
    assert actual == expected
    assert expected["summary"]["scored_count"] >= 4

    wide = ladder_ledger(pattern="down-up", max_gap=2, free_pair=True, wide=True)
    actual = run_gate(wide, "dense_ladder_wide")
    expected = expected_scorecard(wide)
    assert actual == expected
    assert expected["summary"]["scored_count"] >= 4


def test_round_ladder_pressure_matrix_checks_order_gap_and_pattern():
    """Verify generated round-ladder drills vary movement pattern, round span, and waivers."""
    observed = set()
    scored_counts = set()
    for idx, ledger in enumerate(ladder_variants()):
        actual = run_gate(ledger, f"dense_ladder_matrix_{idx:03d}")
        expected = expected_scorecard(ledger)
        assert actual == expected
        observed.add(tuple(expected["summary"].values()))
        scored_counts.add(expected["summary"]["scored_count"])
    assert len(observed) >= 3
    assert len(scored_counts) >= 2


def test_no_subject_piece_miss_is_distinct_from_same_subject_failure_union():
    """Verify turns with no subject piece use the terminal no_subject_piece reason."""
    ledger = copy.deepcopy(variant_base())
    ledger["turns"] = [
        {
            "id": "ghost",
            "subject": "eve",
            "space": "vault",
            "stance": "forge",
            "at": 50,
            "level": 1,
            "pair": "k",
            "booster_required": False,
            "priority": 1,
            "heat": 1,
            "badge": [],
            "round": 1,
            "links": [],
            "link_label": "",
        }
    ]
    actual = run_gate(ledger, "dense_no_subject_piece")
    expected = expected_scorecard(ledger)
    assert actual == expected
    assert actual["missed"] == [{"turn_id": "ghost", "reasons": ["no_subject_piece"]}]


def test_same_subject_round_gap_links_rapid_label_on_both_selected_pieces():
    """Verify same-subject round spacing is waived only when both selected pieces carry rapid."""
    no_rapid = dense_frontier_ledger()
    no_rapid["limits"]["subject_round_gap"]["ada"] = 10
    no_rapid["pieces"][0]["labels"].remove("rapid")
    no_rapid["pieces"][5]["labels"].remove("rapid")
    actual = run_gate(no_rapid, "dense_subject_gap_no_rapid")
    expected = expected_scorecard(no_rapid)
    assert actual == expected
    assert [item["turn_id"] for item in actual["scored"]] == ["r3", "r4"]

    rapid = dense_frontier_ledger()
    rapid["limits"]["subject_round_gap"]["ada"] = 10
    actual = run_gate(rapid, "dense_subject_gap_rapid")
    expected = expected_scorecard(rapid)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5


def test_space_transition_route_label_on_either_side_unlocks_disallowed_move():
    """Verify route:<from>:<to> on either selected piece can allow a forbidden space transition."""
    no_route = dense_frontier_ledger()
    no_route["limits"]["allowed_transitions"]["vault"] = []
    actual = run_gate(no_route, "dense_transition_no_route")
    expected = expected_scorecard(no_route)
    assert actual == expected
    assert [item["turn_id"] for item in actual["scored"]] == ["r3", "r4"]

    left_route = dense_frontier_ledger()
    left_route["limits"]["allowed_transitions"]["vault"] = []
    left_route["pieces"][0]["labels"].append("route:vault:ops")
    actual = run_gate(left_route, "dense_transition_left_route")
    expected = expected_scorecard(left_route)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5

    right_route = dense_frontier_ledger()
    right_route["limits"]["allowed_transitions"]["vault"] = []
    right_route["pieces"][5]["labels"].append("route:vault:ops")
    actual = run_gate(right_route, "dense_transition_right_route")
    expected = expected_scorecard(right_route)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5


def test_prerequisite_link_label_can_score_turn_with_missing_requirement():
    """Verify links are enforced unless the selected piece contains the turn link_label."""
    blocked = dense_frontier_ledger()
    blocked["turns"][-1]["links"] = ["ghost"]
    blocked["turns"][-1]["link_label"] = "override"
    actual = run_gate(blocked, "dense_links_no_waiver")
    expected = expected_scorecard(blocked)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 4

    waived = dense_frontier_ledger()
    waived["turns"][-1]["links"] = ["ghost"]
    waived["turns"][-1]["link_label"] = "pool:door"
    actual = run_gate(waived, "dense_links_waived")
    expected = expected_scorecard(waived)
    assert actual == expected
    assert expected["summary"]["scored_count"] == 5


def test_default_control_room_scorecard_path_works():
    """Verify omitting --output writes the desk scorecard to /app/out/scorecard.json."""
    ledger = generated_variants()[2]
    input_path = OUT_DIR / "default.input.json"
    default_out = OUT_DIR / "scorecard.json"
    input_path.write_text(json.dumps(ledger, separators=(",", ":")), encoding="utf-8")
    if default_out.exists():
        default_out.unlink()
    result = subprocess.run(
        [str(BIN), "--input", str(input_path)],
        cwd=APP,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert load_json(default_out) == expected_scorecard(ledger)
