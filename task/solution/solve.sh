#!/bin/bash
if [ -z "${BASH_VERSION:-}" ]; then
  exec /bin/bash "$0" "$@"
fi
set -euo pipefail

cd /app
mkdir -p /app/output

start_crop_server() {
  if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8780/health', timeout=2).read()" 2>/dev/null; then
    return 0
  fi
  if [ "$(id -u)" -eq 0 ]; then
    /usr/local/bin/ensure-crop-server.sh
    return $?
  fi
  if sudo -n /usr/local/bin/ensure-crop-server.sh 2>/dev/null; then
    return 0
  fi
  /usr/local/bin/ensure-crop-server.sh
}

if ! start_crop_server; then
  echo "crop scoring server failed to start on http://127.0.0.1:8780" >&2
  exit 1
fi

python3 - <<'PY'
import itertools
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "http://127.0.0.1:8780"
SEEDS = [10, 30, 50, 70, 90]
NUM_PLOTS = 6
NUM_TYPES = 5
MIN_DISTINCT_EVALS = 4
EVAL_PER_SEED = 9
REQUEST_TIMEOUT = 60


def request_json(path, payload=None, method=None):
    url = f"{BASE_URL}{path}"
    if payload is not None:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method=method or "POST",
        )
    else:
        req = urllib.request.Request(url, method=method or "GET")
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def wait_for_health():
    err = None
    for _ in range(60):
        try:
            request_json("/health")
            return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            err = exc
            time.sleep(1)
    raise RuntimeError(f"crop server health check failed: {err}")


def ring_neighbors(plot_index):
    return [(plot_index - 1) % NUM_PLOTS, (plot_index + 1) % NUM_PLOTS]


def all_valid_assignments():
    for combo in itertools.product(range(NUM_TYPES), repeat=NUM_PLOTS):
        if len(set(combo)) == NUM_TYPES:
            yield list(combo)


def proxy_score(notes, assignment):
    anchor_plot = notes["anchor_plot"]
    anchor_crop = notes["anchor_crop"]
    preferred = notes["preferred_crop_per_plot"]
    rotation_pairs = [tuple(pair) for pair in notes["rotation_bonus_pairs"]]
    competition_pairs = [tuple(pair) for pair in notes["competition_penalty_pairs"]]
    synergy_triples = [tuple(triple) for triple in notes["synergy_triples"]]

    score = 0
    score += sum(6 for plot, crop in enumerate(assignment) if crop == preferred[plot])
    if assignment[anchor_plot] == anchor_crop:
        for neighbor in ring_neighbors(anchor_plot):
            if assignment[neighbor] != anchor_crop:
                score += 4
    score += sum(5 for pi, pj in rotation_pairs if assignment[pi] != assignment[pj])
    score -= sum(5 for pi, pj in competition_pairs if assignment[pi] == assignment[pj])
    score += sum(
        6
        for triple in synergy_triples
        if len({assignment[plot] for plot in triple}) == 3
    )
    for plot_index in range(NUM_PLOTS):
        for neighbor in ring_neighbors(plot_index):
            if plot_index < neighbor and assignment[plot_index] == assignment[neighbor]:
                score -= 3
    return score


def top_candidates(notes, limit):
    ranked = sorted(
        ((proxy_score(notes, assignment), assignment) for assignment in all_valid_assignments()),
        key=lambda item: item[0],
        reverse=True,
    )
    chosen = []
    seen = set()
    for _, assignment in ranked:
        key = tuple(assignment)
        if key in seen:
            continue
        seen.add(key)
        chosen.append(assignment)
        if len(chosen) >= limit:
            break
    return chosen


def run_seed(seed):
    request_json("/new_game", {"seed": seed})
    notes = request_json(f"/field_notes?{urllib.parse.urlencode({'seed': seed})}")
    candidates = top_candidates(notes, max(MIN_DISTINCT_EVALS, EVAL_PER_SEED))

    best_assignment = None
    best_noisy = None
    for assignment in candidates:
        result = request_json("/evaluate", {"seed": seed, "assignment": assignment})
        noisy = result["noisy_score"]
        if best_noisy is None or noisy >= best_noisy:
            best_noisy = noisy
            best_assignment = assignment

    finish = request_json("/finish", {"seed": seed, "assignment": best_assignment})
    return {
        "seed": seed,
        "won": finish.get("won", False),
        "true_score": finish.get("true_score"),
        "threshold": finish.get("threshold"),
        "assignment": best_assignment,
    }


wait_for_health()
outcomes = [run_seed(seed) for seed in SEEDS]

wins = sum(1 for row in outcomes if row["won"])
strong = sum(
    1
    for row in outcomes
    if row["won"] and (row["true_score"] - row["threshold"]) >= 2
)
if wins < 3 or strong < 2:
    raise SystemExit(
        f"oracle did not meet win targets: wins={wins}/5 strong={strong}/5"
    )

audit_path = "/app/output/audit.json"
result_path = "/app/output/result.txt"

with open(audit_path, "w", encoding="utf-8") as handle:
    json.dump(outcomes, handle, indent=2)

with open(result_path, "w", encoding="utf-8") as handle:
    for row in outcomes:
        handle.write(
            f"Seed {row['seed']}: assignment={row['assignment']} "
            f"score={row['true_score']} threshold={row['threshold']} "
            f"won={row['won']}\n"
        )
    handle.write(f"Total wins: {wins}/5\n")

for path in (audit_path, result_path):
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise SystemExit(f"missing or empty required output: {path}")
PY

test -s /app/output/audit.json
test -s /app/output/result.txt
