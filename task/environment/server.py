import os
import hmac
import json
import random
import hashlib
import itertools
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)

MODEL_SECRET = os.environ.get("MODEL_SECRET") or "crop_plan_m0d3l_2026"
LOG_SECRET = os.environ.get("LOG_SECRET") or "crop_plan_l0g_2026"
STATE_PATH = os.environ.get("STATE_PATH") or "/var/lib/crop-planner/game_state.json"

SEEDS = [10, 30, 50, 70, 90]
NUM_PLOTS = 6
NUM_TYPES = 5
EVAL_BUDGET_PER_SEED = 10
GLOBAL_EVAL_CAP = 45
MIN_DISTINCT_EVALS = 4
WIN_PERCENTILE = 0.80
DUPLICATE_EVAL_COST = 2

_state_lock = threading.RLock()
started_seeds = set()
game_states = {}
event_log = []
global_evals_used = 0


def _serialize_state():
    serializable_games = {}
    for seed, state in game_states.items():
        serializable_games[str(seed)] = {
            key: value for key, value in state.items() if key != "params"
        }
    return {
        "started_seeds": sorted(started_seeds),
        "game_states": serializable_games,
        "event_log": event_log,
        "global_evals_used": global_evals_used,
    }


def _load_state():
    global started_seeds, game_states, event_log, global_evals_used
    if not os.path.isfile(STATE_PATH):
        return
    with open(STATE_PATH, encoding="utf-8") as handle:
        data = json.load(handle)
    started_seeds = set(data.get("started_seeds", []))
    game_states = {int(k): v for k, v in data.get("game_states", {}).items()}
    for seed, state in game_states.items():
        state["params"] = generate_params(seed)
    event_log = data.get("event_log", [])
    global_evals_used = data.get("global_evals_used", 0)


def _save_state():
    directory = os.path.dirname(STATE_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    payload = json.dumps(_serialize_state(), sort_keys=True)
    tmp_path = f"{STATE_PATH}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, STATE_PATH)


def log_event(event_type, data):
    entry = {"type": event_type, "data": data}
    raw = json.dumps(entry, sort_keys=True)
    sig = hmac.HMAC(LOG_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:16]
    entry["sig"] = sig
    with _state_lock:
        event_log.append(entry)
        _save_state()


def ring_neighbors(plot_index):
    return [(plot_index - 1) % NUM_PLOTS, (plot_index + 1) % NUM_PLOTS]


def generate_params(seed):
    rng = random.Random(f"{MODEL_SECRET}_{seed}")
    compatibility = [[rng.randint(1, 10) for _ in range(NUM_TYPES)] for _ in range(NUM_PLOTS)]
    all_pairs = [(i, j) for i in range(NUM_PLOTS) for j in range(i + 1, NUM_PLOTS)]
    rng.shuffle(all_pairs)
    rotation_bonus_pairs = all_pairs[:4]
    rotation_bonus_values = [rng.randint(3, 8) for _ in range(4)]
    competition_penalty_pairs = all_pairs[4:7]
    competition_penalty_values = [rng.randint(3, 7) for _ in range(3)]
    synergy_triples = []
    triple_candidates = list(itertools.combinations(range(NUM_PLOTS), 3))
    rng.shuffle(triple_candidates)
    for triple in triple_candidates[:2]:
        synergy_triples.append((triple, rng.randint(4, 9)))
    ring_penalty_pairs = []
    for plot_index in range(NUM_PLOTS):
        neighbor = (plot_index + 1) % NUM_PLOTS
        ring_penalty_pairs.append((plot_index, neighbor, rng.randint(2, 5)))
    anchor_plot = rng.randint(0, NUM_PLOTS - 1)
    anchor_crop = rng.randint(0, NUM_TYPES - 1)
    return {
        "compatibility": compatibility,
        "rotation_bonus_pairs": rotation_bonus_pairs,
        "rotation_bonus_values": rotation_bonus_values,
        "competition_penalty_pairs": competition_penalty_pairs,
        "competition_penalty_values": competition_penalty_values,
        "synergy_triples": synergy_triples,
        "ring_penalty_pairs": ring_penalty_pairs,
        "anchor_plot": anchor_plot,
        "anchor_crop": anchor_crop,
    }


def compute_score(params, assignment):
    score = 0
    for plot_index in range(NUM_PLOTS):
        score += params["compatibility"][plot_index][assignment[plot_index]]
    for idx, (pi, pj) in enumerate(params["rotation_bonus_pairs"]):
        if assignment[pi] != assignment[pj]:
            score += params["rotation_bonus_values"][idx]
    for idx, (pi, pj) in enumerate(params["competition_penalty_pairs"]):
        if assignment[pi] == assignment[pj]:
            score -= params["competition_penalty_values"][idx]
    for triple, bonus in params["synergy_triples"]:
        crops = {assignment[p] for p in triple}
        if len(crops) == 3:
            score += bonus
    for pi, pj, penalty in params["ring_penalty_pairs"]:
        if assignment[pi] == assignment[pj]:
            score -= penalty
    anchor_plot = params["anchor_plot"]
    anchor_crop = params["anchor_crop"]
    if assignment[anchor_plot] == anchor_crop:
        for neighbor in ring_neighbors(anchor_plot):
            if assignment[neighbor] != anchor_crop:
                score += 4
    return score


def compute_percentile(params):
    scores = []
    for combo in itertools.product(range(NUM_TYPES), repeat=NUM_PLOTS):
        if len(set(combo)) == NUM_TYPES:
            scores.append(compute_score(params, list(combo)))
    scores.sort()
    idx = int(len(scores) * WIN_PERCENTILE)
    return scores[idx] if idx < len(scores) else scores[-1]


def validate_assignment(assignment):
    if not isinstance(assignment, list) or len(assignment) != NUM_PLOTS:
        return False
    if not all(isinstance(x, int) and 0 <= x < NUM_TYPES for x in assignment):
        return False
    if len(set(assignment)) < NUM_TYPES:
        return False
    return True


def assignment_key(assignment):
    return json.dumps(assignment, separators=(",", ":"))


_load_state()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "global_evals_remaining": GLOBAL_EVAL_CAP - global_evals_used})


@app.route("/field_notes", methods=["GET"])
def field_notes():
    seed = request.args.get("seed", type=int)
    if seed not in SEEDS:
        return jsonify({"error": f"Invalid seed. Use one of {SEEDS}"}), 400
    with _state_lock:
        if seed not in game_states:
            return jsonify({"error": "Start a game first with /new_game"}), 400
        params = game_states[seed]["params"]
        log_event("field_notes", {"seed": seed})
    anchor_plot = params["anchor_plot"]
    anchor_crop = params["anchor_crop"]
    rotation_pairs = [
        [pi, pj] for pi, pj in params["rotation_bonus_pairs"]
    ]
    competition_pairs = [
        [pi, pj] for pi, pj in params["competition_penalty_pairs"]
    ]
    synergy_triples = [
        [int(plot) for plot in triple]
        for triple, _bonus in params["synergy_triples"]
    ]
    preferred_crop_per_plot = [
        max(range(NUM_TYPES), key=lambda crop, plot=plot: params["compatibility"][plot][crop])
        for plot in range(NUM_PLOTS)
    ]
    return jsonify({
        "seed": seed,
        "note": (
            f"Plot {anchor_plot} responds when crop {anchor_crop} is planted there "
            "and the ring neighbors differ."
        ),
        "anchor_plot": anchor_plot,
        "anchor_crop": anchor_crop,
        "rotation_bonus_pairs": rotation_pairs,
        "competition_penalty_pairs": competition_pairs,
        "synergy_triples": synergy_triples,
        "preferred_crop_per_plot": preferred_crop_per_plot,
    })


@app.route("/new_game", methods=["POST"])
def new_game():
    data = request.get_json(force=True)
    seed = data.get("seed")
    if seed not in SEEDS:
        return jsonify({"error": f"Invalid seed. Use one of {SEEDS}"}), 400
    with _state_lock:
        if seed in started_seeds:
            log_event("new_game_rejected", {"seed": seed, "reason": "already_started"})
            return jsonify({"error": f"Seed {seed} already started"}), 400
        started_seeds.add(seed)
        params = generate_params(seed)
        threshold = compute_percentile(params)
        game_states[seed] = {
            "params": params,
            "evals_used": 0,
            "evaluated_assignments": {},
            "best_score": None,
            "threshold": threshold,
            "finished": False,
        }
        log_event("new_game", {"seed": seed, "threshold": threshold})
    return jsonify({
        "seed": seed,
        "num_plots": NUM_PLOTS,
        "num_types": NUM_TYPES,
        "eval_budget": EVAL_BUDGET_PER_SEED,
        "global_eval_cap": GLOBAL_EVAL_CAP,
        "min_distinct_evals": MIN_DISTINCT_EVALS,
        "message": (
            f"Assign {NUM_PLOTS} plots with types 0-{NUM_TYPES - 1}. "
            f"All {NUM_TYPES} types must appear. Repeated assignments cost "
            f"{DUPLICATE_EVAL_COST} evaluation slots."
        ),
    })


@app.route("/evaluate", methods=["POST"])
def evaluate():
    data = request.get_json(force=True)
    seed = data.get("seed")
    assignment = data.get("assignment")
    with _state_lock:
        global global_evals_used
        if seed not in game_states:
            return jsonify({"error": "Start a game first with /new_game"}), 400
        state = game_states[seed]
        if state["finished"]:
            return jsonify({"error": "Game already finished"}), 400
        if state["evals_used"] >= EVAL_BUDGET_PER_SEED:
            return jsonify({"error": "Per-seed evaluation budget exhausted"}), 400
        if global_evals_used >= GLOBAL_EVAL_CAP:
            return jsonify({"error": "Global evaluation cap exhausted"}), 400
        if not validate_assignment(assignment):
            return jsonify({
                "error": (
                    f"Invalid assignment. Need list of {NUM_PLOTS} ints 0-{NUM_TYPES - 1}, "
                    f"all {NUM_TYPES} types present."
                )
            }), 400
        key = assignment_key(assignment)
        is_repeat = key in state["evaluated_assignments"]
        eval_cost = DUPLICATE_EVAL_COST if is_repeat else 1
        if state["evals_used"] + eval_cost > EVAL_BUDGET_PER_SEED:
            return jsonify({"error": "Not enough per-seed budget for this evaluation"}), 400
        if global_evals_used + eval_cost > GLOBAL_EVAL_CAP:
            return jsonify({"error": "Not enough global budget for this evaluation"}), 400
        state["evals_used"] += eval_cost
        global_evals_used += eval_cost
        true_score = compute_score(state["params"], assignment)
        rng = random.Random(f"{MODEL_SECRET}_{seed}_{state['evals_used']}_{assignment}")
        noise = rng.randint(-1, 1)
        noisy_score = true_score + noise
        state["evaluated_assignments"][key] = noisy_score
        if state["best_score"] is None or noisy_score > state["best_score"]:
            state["best_score"] = noisy_score
        evals_used = state["evals_used"]
        log_event(
            "evaluate",
            {
                "seed": seed,
                "assignment": assignment,
                "noisy_score": noisy_score,
                "eval_num": evals_used,
                "repeat": is_repeat,
                "eval_cost": eval_cost,
            },
        )
    return jsonify({
        "noisy_score": noisy_score,
        "evals_used": evals_used,
        "evals_remaining": EVAL_BUDGET_PER_SEED - evals_used,
        "global_evals_remaining": GLOBAL_EVAL_CAP - global_evals_used,
        "repeat": is_repeat,
        "eval_cost": eval_cost,
    })


@app.route("/finish", methods=["POST"])
def finish():
    data = request.get_json(force=True)
    seed = data.get("seed")
    assignment = data.get("assignment")
    with _state_lock:
        if seed not in game_states:
            return jsonify({"error": "Start a game first with /new_game"}), 400
        state = game_states[seed]
        if state["finished"]:
            return jsonify({"error": "Game already finished"}), 400
        if not validate_assignment(assignment):
            return jsonify({"error": "Invalid assignment"}), 400
        if len(state["evaluated_assignments"]) < MIN_DISTINCT_EVALS:
            return jsonify({
                "error": (
                    f"Need at least {MIN_DISTINCT_EVALS} distinct evaluated assignments "
                    f"before finish"
                )
            }), 400
        key = assignment_key(assignment)
        if key not in state["evaluated_assignments"]:
            return jsonify({"error": "Finish assignment must have been evaluated first"}), 400
        state["finished"] = True
        true_score = compute_score(state["params"], assignment)
        won = true_score >= state["threshold"]
        log_event(
            "finish",
            {
                "seed": seed,
                "assignment": assignment,
                "true_score": true_score,
                "threshold": state["threshold"],
                "won": won,
            },
        )
        threshold = state["threshold"]
    return jsonify({
        "true_score": true_score,
        "threshold": threshold,
        "won": won,
        "message": "You won this seed!" if won else "Below threshold.",
    })


@app.route("/events", methods=["GET"])
def events():
    with _state_lock:
        return jsonify({
            "events": list(event_log),
            "global_evals_used": global_evals_used,
        })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8780, threaded=True)
