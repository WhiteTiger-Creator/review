"""tests for the Lua model contamination audit pipeline."""

import contextlib
import hashlib
import http.server
import json
import math
import pathlib
import re
import shutil
import socket
import sqlite3
import subprocess
import threading
import time

APP = pathlib.Path("/app")
AUDIT_PATH = APP / "output" / "audit.json"
DATABASE_PATH = APP / "output" / "probes.sqlite"
CLEANED_PATH = APP / "output" / "cleaned.jsonl"
CONFIG_PATH = APP / "config" / "audit.json"
PROFILE_PATH = APP / "config" / "model_profiles.json"
OUTPUT_PATHS = (AUDIT_PATH, DATABASE_PATH, CLEANED_PATH)
AXES = {
    "answer_format",
    "benchmark_age",
    "canary_rarity",
    "paraphrase_distance",
    "prompt_framing",
    "sampling_randomness",
}
FEATURES = (
    "completion_likelihood_gap",
    "exact_match_rate",
    "perturbation_sensitivity",
    "order_invariance",
    "metadata_leak",
    "canary_recall",
    "paraphrase_robustness",
    "substring_overlap",
    "semantic_overlap",
)
NORMAL_90 = 1.645
HIDDEN_MODALITIES = ("text", "source_code", "table", "image_caption")
HIDDEN_PENALTIES = [0.004, 0.012, 0.05, 0.15, 0.5, 1.5]
_HEAD_CACHE: dict[tuple, dict] = {}


def _wait_for_port(port: int) -> None:
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        with contextlib.suppress(OSError), socket.create_connection(
            ("127.0.0.1", port),
            timeout=0.1,
        ):
            return
        time.sleep(0.05)
    message = f"local model server on port {port} did not start"
    raise RuntimeError(message)


def _run_audit(config: pathlib.Path = CONFIG_PATH) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(APP / "bin" / "memscope"), "audit", "--config", str(config)],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _load_audit(path: pathlib.Path = AUDIT_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_lines(paths: list[str]) -> list[dict]:
    rows = []
    for raw_path in paths:
        path = pathlib.Path(raw_path)
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    return rows


def _words(text: str) -> list[str]:
    return re.findall(r"[0-9a-z]+", text.lower())


def _longest_run(left: list[str], right: list[str]) -> int:
    best = 0
    for start in range(len(left)):
        for offset in range(len(right)):
            length = 0
            while (
                start + length < len(left)
                and offset + length < len(right)
                and left[start + length] == right[offset + length]
            ):
                length += 1
            best = max(best, length)
    return best


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return numerator / (left_norm * right_norm)


def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    size = len(rhs)
    work = [[*row, rhs[index]] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = column
        for row in range(column + 1, size):
            if abs(work[row][column]) > abs(work[pivot][column]):
                pivot = row
        work[column], work[pivot] = work[pivot], work[column]
        head = work[column][column]
        for row in range(size):
            if row == column:
                continue
            factor = work[row][column] / head
            for index in range(column, size + 1):
                work[row][index] -= factor * work[column][index]
    return [work[row][size] / work[row][row] for row in range(size)]


def _linear(coefficients: list[float], scaled: list[float]) -> float:
    return coefficients[0] + sum(
        coefficients[index + 1] * value for index, value in enumerate(scaled)
    )


def _point_loss(eta: float, label: float) -> float:
    return max(eta, 0.0) - eta * label + math.log1p(math.exp(-abs(eta)))


def _fit(
    design: list[list[float]],
    labels: list[float],
    penalty: float,
    used: list[bool],
) -> list[float]:
    width = len(design[0]) + 1
    coefficients = [0.0] * width
    total = float(sum(used))
    for _ in range(100):
        gradient = [0.0] * width
        hessian = [[0.0] * width for _ in range(width)]
        for index, row in enumerate(design):
            if not used[index]:
                continue
            basis = [1.0, *row]
            mu = 1.0 / (1.0 + math.exp(-_linear(coefficients, row)))
            weight = mu * (1.0 - mu)
            residual = mu - labels[index]
            for left in range(width):
                gradient[left] += residual * basis[left] / total
                for right in range(width):
                    hessian[left][right] += weight * basis[left] * basis[right] / total
        for left in range(1, width):
            gradient[left] += 2 * penalty * coefficients[left]
            hessian[left][left] += 2 * penalty
        step = _solve(hessian, gradient)
        coefficients = [coefficients[index] - step[index] for index in range(width)]
        if max(abs(value) for value in step) < 1e-13:
            break
    return coefficients


def _panel_rows(paths: list[str]) -> list[dict]:
    return [
        {
            "modality": row["modality"],
            "label": float(row["contaminated"]),
            "features": [float(row[name]) for name in FEATURES],
        }
        for row in _load_json_lines(paths)
    ]


def _calibrate(rows: list[dict], penalties: list[float]) -> dict:
    count = len(rows)
    center = [
        sum(row["features"][column] for row in rows) / count for column in range(len(FEATURES))
    ]
    spread = [
        math.sqrt(
            sum((row["features"][column] - center[column]) ** 2 for row in rows) / count,
        )
        for column in range(len(FEATURES))
    ]
    design = [
        [(row["features"][column] - center[column]) / spread[column] for column in range(len(FEATURES))]
        for row in rows
    ]
    labels = [row["label"] for row in rows]
    modalities = sorted({row["modality"] for row in rows})

    curve = []
    for penalty in penalties:
        losses = []
        for modality in modalities:
            used = [row["modality"] != modality for row in rows]
            coefficients = _fit(design, labels, penalty, used)
            held = [index for index in range(count) if not used[index]]
            losses.append(
                sum(_point_loss(_linear(coefficients, design[index]), labels[index]) for index in held)
                / len(held),
            )
        mean = sum(losses) / len(losses)
        variance = sum((value - mean) ** 2 for value in losses) / (len(losses) - 1)
        curve.append((penalty, mean, math.sqrt(variance) / math.sqrt(len(losses))))

    best = curve[0]
    for row in curve[1:]:
        if row[1] < best[1]:
            best = row
    limit = best[1] + best[2]
    chosen = best
    for row in curve:
        if row[1] <= limit and row[0] > chosen[0]:
            chosen = row
    full = _fit(design, labels, chosen[0], [True] * count)
    deleted = []
    for dropped in range(count):
        used = [True] * count
        used[dropped] = False
        deleted.append(_fit(design, labels, chosen[0], used))
    return {
        "penalty": chosen[0],
        "mean_log_loss": chosen[1],
        "intercept": full[0],
        "coefficients": full[1:],
        "center": center,
        "spread": spread,
        "full": full,
        "deleted": deleted,
    }


def _head_for(config: dict) -> dict:
    settings = config["calibration"]
    key = (tuple(settings["panel_paths"]), tuple(settings["penalties"]))
    cached = _HEAD_CACHE.get(key)
    if cached is None:
        cached = _calibrate(_panel_rows(settings["panel_paths"]), settings["penalties"])
        _HEAD_CACHE[key] = cached
    return cached


def _predict(head: dict, evidence: dict) -> tuple[float, float, float]:
    scaled = [
        (float(evidence[name]) - head["center"][column]) / head["spread"][column]
        for column, name in enumerate(FEATURES)
    ]
    eta = _linear(head["full"], scaled)
    deleted = [_linear(coefficients, scaled) for coefficients in head["deleted"]]
    count = len(deleted)
    mean = sum(deleted) / count
    error = math.sqrt((count - 1) / count * sum((value - mean) ** 2 for value in deleted))
    return (
        1.0 / (1.0 + math.exp(-eta)),
        1.0 / (1.0 + math.exp(-(eta - NORMAL_90 * error))),
        1.0 / (1.0 + math.exp(-(eta + NORMAL_90 * error))),
    )


def _normalized_study_value(value: object) -> str:
    if isinstance(value, int | float):
        return f"{float(value):.12g}"
    return str(value)


def _logical_database_dump(path: pathlib.Path) -> dict[str, list[tuple]]:
    with sqlite3.connect(path) as connection:
        return {
            "items": connection.execute("SELECT * FROM items ORDER BY id").fetchall(),
            "probes": connection.execute(
                "SELECT * FROM probes ORDER BY probe_index",
            ).fetchall(),
            "study": connection.execute(
                "SELECT * FROM study ORDER BY axis, value",
            ).fetchall(),
        }


@contextlib.contextmanager
def _server_for(handler: type[http.server.BaseHTTPRequestHandler]):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


class _HiddenProbeHandler(http.server.BaseHTTPRequestHandler):
    profiles: dict[str, dict]

    def do_POST(self) -> None:
        length = int(self.headers["Content-Length"])
        request = json.loads(self.rfile.read(length))
        profile = self.profiles[request["item_id"]]
        risk = profile["risk"]
        kind = request.get("probe_kind", "original")
        distance = float(request.get("paraphrase_distance", 0))
        temperature = float(request.get("temperature", 0))
        if kind == "perturbed":
            probability = 0.18 if risk > 0.5 else 0.40
        elif kind == "paraphrase":
            probability = (0.91 if risk > 0.5 else 0.42) - 0.32 * distance
        else:
            probability = 0.98 if risk > 0.5 else 0.43
        probability -= 0.18 * temperature
        signature = "|".join(
            [
                request["item_id"],
                kind,
                str(request.get("seed", 0)),
                str(distance),
                str(temperature),
                str(request.get("answer_format", "free")),
            ],
        )
        unit = int(hashlib.sha256(signature.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        correct = unit < probability
        logprob = (-0.18 if risk > 0.5 else -2.25) - (
            distance * 1.1 if kind == "paraphrase" and risk > 0.5 else 0
        )
        metadata = {}
        if request.get("framing") == "metadata" and risk > 0.5:
            metadata = {"benchmark_id": request["item_id"], "split": "hidden"}
        canary = ""
        if kind == "canary" and risk > 0.5 and request.get("canary_rarity", 0) >= 7:
            canary = request["canary"]
        payload = json.dumps(
            {
                "text": profile["answer"] if correct else profile["distractor"],
                "logprob": logprob,
                "metadata_echo": metadata,
                "returned_canary": canary,
            },
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_: object) -> None:
        return


class _MalformedProbeHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        payload = b'{"text":7,"logprob":"not numeric"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_: object) -> None:
        return


def _hidden_panel() -> list[dict]:
    """an adjudicated panel the audit has never seen, drawn from a small generator."""
    rows: list[dict] = []
    state = 20260728
    scale = 1 << 31

    def unit() -> float:
        nonlocal state
        state = (state * 1103515245 + 12345) % scale
        return state / scale

    for index, modality in enumerate(HIDDEN_MODALITIES):
        for _ in range(12):
            risk = unit()
            label = 1 if risk > 0.5 else 0
            if unit() < 0.06:
                label = 1 - label
            offset = 0.02 * index - 0.03
            rows.append(
                {
                    "id": f"unseen_{len(rows) + 1:03d}",
                    "modality": modality,
                    "contaminated": label,
                    "completion_likelihood_gap": round(0.05 + 0.36 * risk + 0.05 * unit(), 4),
                    "exact_match_rate": round(min(1.0, max(0.0, 0.2 + 0.7 * risk + offset)), 4),
                    "perturbation_sensitivity": round(
                        min(1.0, max(0.0, 0.1 + 0.6 * risk - 0.2 * unit())), 4,
                    ),
                    "order_invariance": round(min(1.0, max(0.0, 0.35 + 0.5 * risk + 0.1 * unit())), 4),
                    "metadata_leak": 1.0 if risk > 0.45 else 0.0,
                    "canary_recall": 1.0 if risk > 0.6 else 0.0,
                    "paraphrase_robustness": round(
                        min(1.0, max(0.0, 0.25 + 0.55 * risk - 0.15 * unit())), 4,
                    ),
                    "substring_overlap": round(min(1.0, max(0.02, 0.06 + 0.8 * risk * unit())), 4),
                    "semantic_overlap": round(
                        min(0.9999, max(0.2, 0.34 + 0.55 * risk + 0.06 * unit())), 4,
                    ),
                },
            )
    return rows


def _write_hidden_case(root: pathlib.Path, port: int) -> tuple[pathlib.Path, dict[str, float]]:
    modalities = ["text", "source_code", "table", "image_caption"]
    profiles = {}
    benchmarks = []
    corpus = []
    embeddings = []
    for index in range(8):
        item_id = f"hidden_{index + 1}"
        contaminated = index < 4
        risk = 0.91 if contaminated else 0.09
        answer = f"answer {index + 1}"
        profiles[item_id] = {
            "risk": risk,
            "answer": answer,
            "distractor": f"distractor {index + 1}",
        }
        embedding = [1.0, 0.0, 0.0, 0.0] if contaminated else [0.0, 1.0, 0.0, 0.0]
        prompt = (
            f"Archived benchmark prompt number {index + 1}"
            if contaminated
            else f"Novel evaluation question number {index + 1}"
        )
        benchmarks.append(
            {
                "id": item_id,
                "modality": modalities[index % len(modalities)],
                "prompt": prompt,
                "answer": answer,
                "options": [answer, f"distractor {index + 1}"],
                "metadata": {"source": "hidden", "split": "heldout"},
                "canary": f"rare token {index + 101}",
                "age_months": 48 if contaminated else 4,
                "embedding": embedding,
                "paraphrases": [
                    {
                        "text": f"Rephrased hidden prompt {index + 1}",
                        "distance": 0.25,
                        "embedding": embedding,
                    },
                    {
                        "text": f"Semantically altered hidden prompt {index + 1}",
                        "distance": 0.65,
                        "embedding": embedding,
                    },
                ],
            },
        )
        if contaminated:
            corpus.append(
                {
                    "id": f"corpus_{index}",
                    "text": prompt,
                    "embedding": embedding,
                },
            )
            embeddings.append({"id": f"embed_{index}", "embedding": embedding})
    corpus.append(
        {
            "id": "unrelated",
            "text": "A distant corpus passage about mineral crystal symmetry",
            "embedding": [0.0, 0.0, 1.0, 0.0],
        },
    )
    embeddings.append({"id": "unrelated", "embedding": [0.0, 0.0, 1.0, 0.0]})

    root.mkdir(parents=True, exist_ok=True)
    benchmark_path = root / "benchmarks.jsonl"
    corpus_path = root / "corpus.jsonl"
    embedding_path = root / "embeddings.jsonl"
    benchmark_path.write_text("\n".join(json.dumps(row) for row in benchmarks) + "\n", encoding="utf-8")
    corpus_path.write_text("\n".join(json.dumps(row) for row in corpus) + "\n", encoding="utf-8")
    embedding_path.write_text("\n".join(json.dumps(row) for row in embeddings) + "\n", encoding="utf-8")
    panel_path = root / "panel.jsonl"
    panel_path.write_text(
        "\n".join(json.dumps(row) for row in _hidden_panel()) + "\n",
        encoding="utf-8",
    )
    config = {
        "benchmark_paths": [str(benchmark_path)],
        "corpus_paths": [str(corpus_path)],
        "embedding_paths": [str(embedding_path)],
        "endpoint": f"http://127.0.0.1:{port}/v1/probe",
        "output": {
            "audit": str(AUDIT_PATH),
            "database": str(DATABASE_PATH),
            "cleaned": str(CLEANED_PATH),
        },
        "seeds": [3, 5, 7, 11, 13],
        "study": {
            "paraphrase_distance": [0.15, 0.45, 0.75],
            "canary_rarity": [2, 7, 13],
            "prompt_framing": ["plain", "metadata"],
            "answer_format": ["free", "choice"],
            "sampling_randomness": [0.0, 0.4, 0.8],
            "benchmark_age": [6, 24, 60],
        },
        "calibration": {
            "panel_paths": [str(panel_path)],
            "penalties": HIDDEN_PENALTIES,
        },
        "cleaning": {
            "risk_limit": 0.65,
            "minimum_retention": 0.5,
            "minimum_per_modality": 1,
        },
    }
    config_path = root / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path, {key: value["risk"] for key, value in profiles.items()}


def setup_module() -> None:
    """generate all primary artifacts from a live local model API."""
    for path in OUTPUT_PATHS:
        path.unlink(missing_ok=True)
    process = subprocess.Popen(
        ["lua", str(APP / "mock_model" / "server.lua"), str(PROFILE_PATH), "18080"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_for_port(18080)
    result = _run_audit()
    process.terminate()
    process.wait(timeout=5)
    assert result.returncode == 0, result.stderr
    assert all(path.exists() for path in OUTPUT_PATHS)


def test_lua_pipeline_authors_all_required_artifacts() -> None:
    """the Lua entrypoint recreates every documented final artifact."""
    first_line = (APP / "bin" / "memscope").read_text(encoding="utf-8").splitlines()[0]
    assert "lua" in first_line.lower()
    assert (APP / "src" / "cli.lua").is_file()
    assert (APP / "src" / "pipeline.lua").is_file()
    forbidden_suffixes = {".js", ".php", ".pl", ".py", ".rb", ".sh", ".ts"}
    forbidden_sources = [
        path
        for path in APP.rglob("*")
        if path.is_file() and path.suffix.lower() in forbidden_suffixes
    ]
    assert not forbidden_sources
    for source in (APP / "src").glob("*.lua"):
        for line in source.read_text(encoding="utf-8").splitlines():
            if "os.execute" in line or "io.popen" in line:
                assert not any(
                    interpreter in line.lower()
                    for interpreter in ("node", "perl", "php", "python", "ruby")
                )
    audit = _load_audit()
    assert set(audit) == {"calibration", "cleaning", "items", "parameter_study", "summary"}
    assert set(audit["summary"]) == {"item_count", "probe_count"}
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert audit["summary"]["item_count"] == len(_load_json_lines(config["benchmark_paths"]))
    assert len(CLEANED_PATH.read_text(encoding="utf-8").splitlines()) > 0


def test_sqlite_contains_live_api_probe_evidence() -> None:
    """every evidence family and study request is persisted in SQLite."""
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    expected_items = len(_load_json_lines(config["benchmark_paths"]))
    with sqlite3.connect(DATABASE_PATH) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'",
            )
        }
        assert {"items", "probes", "study"} <= table_names
        assert connection.execute("SELECT COUNT(*) FROM items").fetchone()[0] == expected_items
        kinds = {
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT kind FROM probes WHERE axis=''",
            )
        }
        assert {"canary", "metadata", "order", "original", "paraphrase", "perturbed"} <= kinds
        axes = {
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT axis FROM probes WHERE axis<>''",
            )
        }
        assert axes == AXES
        probe_count = connection.execute("SELECT COUNT(*) FROM probes").fetchone()[0]
        assert probe_count == _load_audit()["summary"]["probe_count"]


def test_overlap_indexes_cover_substrings_and_cosine_similarity() -> None:
    """substring clones and embedding cosine maxima are measured correctly."""
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    benchmarks = _load_json_lines(config["benchmark_paths"])
    corpus = _load_json_lines(config["corpus_paths"])
    corpus_embeddings = _load_json_lines(config["embedding_paths"])
    reported = {row["id"]: row for row in _load_audit()["items"]}
    corpus_words = [_words(row["text"]) for row in corpus]
    for item in benchmarks:
        expected_semantic = max(
            _cosine(item["embedding"], row["embedding"])
            for row in corpus_embeddings
        )
        assert math.isclose(
            reported[item["id"]]["semantic_overlap"],
            expected_semantic,
            rel_tol=1e-9,
            abs_tol=1e-12,
        )
        prompt_words = _words(item["prompt"])
        expected_substring = max(
            _longest_run(prompt_words, passage) for passage in corpus_words
        ) / len(prompt_words)
        assert math.isclose(
            reported[item["id"]]["substring_overlap"],
            expected_substring,
            rel_tol=1e-9,
            abs_tol=1e-12,
        )


def test_per_item_evidence_is_recomputed_from_persisted_probes() -> None:
    """likelihood, matching, perturbation, order, metadata, canary, and paraphrase evidence agree with probes."""
    audit_items = {row["id"]: row for row in _load_audit()["items"]}
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        probes = connection.execute(
            "SELECT * FROM probes WHERE axis='' ORDER BY probe_index",
        ).fetchall()
    by_item: dict[str, list[sqlite3.Row]] = {}
    for row in probes:
        by_item.setdefault(row["item_id"], []).append(row)
    for item_id, rows in by_item.items():
        item = audit_items[item_id]

        def selected(
            kind: str,
            field: str,
            records: list[sqlite3.Row] = rows,
        ) -> list[float]:
            return [float(row[field]) for row in records if row["kind"] == kind]

        original_correct = selected("original", "correct")
        paraphrase_correct = selected("paraphrase", "correct")
        original_logprob = selected("original", "logprob")
        paraphrase_logprob = selected("paraphrase", "logprob")
        exact_rate = sum(original_correct) / len(original_correct)
        paraphrase_rate = sum(paraphrase_correct) / len(paraphrase_correct)
        assert math.isclose(item["exact_match_rate"], exact_rate)
        assert math.isclose(item["paraphrase_robustness"], paraphrase_rate)
        expected_gap = sum(original_logprob) / len(original_logprob) - sum(
            paraphrase_logprob,
        ) / len(paraphrase_logprob)
        assert math.isclose(item["completion_likelihood_gap"], expected_gap)
        perturbed = selected("perturbed", "correct")
        assert math.isclose(
            item["perturbation_sensitivity"],
            max(0.0, exact_rate - sum(perturbed) / len(perturbed)),
        )
        for kind, field, output_key in (
            ("order", "correct", "order_invariance"),
            ("metadata", "metadata_leak", "metadata_leak"),
            ("canary", "canary_recall", "canary_recall"),
        ):
            values = selected(kind, field)
            assert math.isclose(item[output_key], sum(values) / len(values))


def test_calibration_reports_the_one_standard_error_penalized_fit() -> None:
    """the reported head is the leave one modality out selection over the adjudicated panel."""
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    head = _head_for(config)
    reported = _load_audit()["calibration"]
    assert set(reported) == {"coefficients", "intercept", "mean_log_loss", "penalty"}
    assert math.isclose(reported["penalty"], head["penalty"], rel_tol=1e-9)
    assert math.isclose(reported["mean_log_loss"], head["mean_log_loss"], abs_tol=1e-6)
    assert math.isclose(reported["intercept"], head["intercept"], abs_tol=1e-6)
    assert len(reported["coefficients"]) == len(FEATURES)
    for value, expected in zip(reported["coefficients"], head["coefficients"], strict=True):
        assert math.isclose(value, expected, abs_tol=1e-6)


def test_scores_and_jackknife_intervals_follow_from_the_calibrated_head() -> None:
    """each score and interval is the panel fit applied to the item evidence."""
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    head = _head_for(config)
    for item in _load_audit()["items"]:
        score, lower, upper = _predict(head, item)
        assert math.isclose(item["score"], score, abs_tol=1e-6)
        assert math.isclose(item["lower"], lower, abs_tol=5e-5)
        assert math.isclose(item["upper"], upper, abs_tol=5e-5)


def test_parameter_studies_match_their_persisted_measurements() -> None:
    """all six parameter axes report the mean signal recorded by their probes."""
    audit = _load_audit()
    study = {
        (row["axis"], _normalized_study_value(row["value"])): row["mean_signal"]
        for row in audit["parameter_study"]
    }
    assert {axis for axis, _ in study} == AXES
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT * FROM probes WHERE axis<>'' ORDER BY probe_index",
        ).fetchall()
    grouped: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        if row["axis"] in {"answer_format", "prompt_framing"}:
            key = (row["axis"], row["value"])
        else:
            key = (row["axis"], _normalized_study_value(float(row["value"])))
        if row["axis"] in {"paraphrase_distance", "benchmark_age"}:
            signal = float(row["logprob"])
        elif row["axis"] == "canary_rarity":
            signal = float(row["canary_recall"])
        elif row["axis"] == "prompt_framing":
            signal = float(row["metadata_leak"])
        else:
            signal = float(row["correct"])
        grouped.setdefault(key, []).append(signal)
    assert set(grouped) == set(study)
    for key, values in grouped.items():
        assert math.isclose(study[key], sum(values) / len(values), abs_tol=1e-10)


def test_cleaning_is_the_largest_feasible_modality_preserving_subset() -> None:
    """cleaning maximizes retention under risk, retention, and modality floors."""
    audit = _load_audit()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))["cleaning"]
    items = audit["items"]
    modalities = {item["modality"] for item in items}
    feasible: list[tuple[int, float, tuple[str, ...]]] = []
    for mask in range(1 << len(items)):
        chosen = [item for index, item in enumerate(items) if mask & (1 << index)]
        if len(chosen) < math.ceil(len(items) * config["minimum_retention"]):
            continue
        counts = {
            modality: sum(item["modality"] == modality for item in chosen)
            for modality in modalities
        }
        if min(counts.values()) < config["minimum_per_modality"]:
            continue
        mean_upper = sum(item["upper"] for item in chosen) / len(chosen)
        if mean_upper <= config["risk_limit"] + 1e-12:
            feasible.append(
                (
                    len(chosen),
                    mean_upper,
                    tuple(sorted(item["id"] for item in chosen)),
                ),
            )
    assert feasible
    optimum = min(feasible, key=lambda row: (-row[0], row[1], row[2]))
    retained = tuple(audit["cleaning"]["retained_ids"])
    assert retained == optimum[2]
    assert math.isclose(audit["cleaning"]["mean_upper_risk"], optimum[1])
    retained_set = set(retained)
    expected_removed = sorted(
        item["id"] for item in items if item["id"] not in retained_set
    )
    assert audit["cleaning"]["removed_ids"] == expected_removed
    assert math.isclose(
        audit["cleaning"]["retained_fraction"],
        len(retained) / len(items),
    )
    for item in items:
        expected_decision = "keep" if item["id"] in retained_set else "remove"
        assert item["decision"] == expected_decision
    cleaned_ids = {
        json.loads(line)["id"]
        for line in CLEANED_PATH.read_text(encoding="utf-8").splitlines()
        if line
    }
    assert cleaned_ids == set(retained)


def test_repeated_runs_reproduce_json_and_jsonl_bytes() -> None:
    """repeated live audits preserve byte identical JSON and JSONL outputs."""
    before_audit = AUDIT_PATH.read_bytes()
    before_cleaned = CLEANED_PATH.read_bytes()
    before_database = _logical_database_dump(DATABASE_PATH)
    process = subprocess.Popen(
        ["lua", str(APP / "mock_model" / "server.lua"), str(PROFILE_PATH), "18080"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_for_port(18080)
    result = _run_audit()
    process.terminate()
    process.wait(timeout=5)
    assert result.returncode == 0, result.stderr
    assert AUDIT_PATH.read_bytes() == before_audit
    assert CLEANED_PATH.read_bytes() == before_cleaned
    assert _logical_database_dump(DATABASE_PATH) == before_database


def test_unseen_model_service_and_records_defeat_fixture_hardcoding() -> None:
    """an unseen API, benchmark and panel still produce the calibrated head they imply."""
    root = pathlib.Path("/tmp/memscope-hidden")
    shutil.rmtree(root, ignore_errors=True)
    profiles = {
        f"hidden_{index + 1}": {
            "risk": 0.91 if index < 4 else 0.09,
            "answer": f"answer {index + 1}",
            "distractor": f"distractor {index + 1}",
        }
        for index in range(8)
    }
    _HiddenProbeHandler.profiles = profiles
    with _server_for(_HiddenProbeHandler) as port:
        config_path, _ = _write_hidden_case(root, port)
        result = _run_audit(config_path)
    assert result.returncode == 0, result.stderr
    audit = _load_audit()
    assert {item["modality"] for item in audit["items"]} == {
        "image_caption",
        "source_code",
        "table",
        "text",
    }
    head = _head_for(json.loads(config_path.read_text(encoding="utf-8")))
    assert math.isclose(audit["calibration"]["penalty"], head["penalty"], rel_tol=1e-9)
    assert math.isclose(audit["calibration"]["intercept"], head["intercept"], abs_tol=1e-6)
    for item in audit["items"]:
        score, lower, upper = _predict(head, item)
        assert math.isclose(item["score"], score, abs_tol=1e-6)
        assert math.isclose(item["lower"], lower, abs_tol=5e-5)
        assert math.isclose(item["upper"], upper, abs_tol=5e-5)
    assert all(path.is_file() for path in OUTPUT_PATHS)

    process = subprocess.Popen(
        ["lua", str(APP / "mock_model" / "server.lua"), str(PROFILE_PATH), "18080"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _wait_for_port(18080)
    restore_result = _run_audit()
    process.terminate()
    process.wait(timeout=5)
    assert restore_result.returncode == 0, restore_result.stderr


def test_invalid_inputs_fail_without_replacing_completed_outputs() -> None:
    """malformed configuration and API payloads return nonzero while preserving outputs."""
    snapshots = {path: path.read_bytes() for path in OUTPUT_PATHS}
    invalid_config = pathlib.Path("/tmp/memscope-invalid.json")
    invalid_config.write_text('{"endpoint":7}', encoding="utf-8")
    invalid_result = _run_audit(invalid_config)
    assert invalid_result.returncode != 0
    assert {path: path.read_bytes() for path in OUTPUT_PATHS} == snapshots

    root = pathlib.Path("/tmp/memscope-malformed-api")
    shutil.rmtree(root, ignore_errors=True)
    with _server_for(_MalformedProbeHandler) as port:
        valid_config, _ = _write_hidden_case(root, port)
        config = json.loads(valid_config.read_text(encoding="utf-8"))
        config["output"] = {
            "audit": str(AUDIT_PATH),
            "database": str(DATABASE_PATH),
            "cleaned": str(CLEANED_PATH),
        }
        valid_config.write_text(json.dumps(config), encoding="utf-8")
        malformed_result = _run_audit(valid_config)
    assert malformed_result.returncode != 0
    assert {path: path.read_bytes() for path in OUTPUT_PATHS} == snapshots
