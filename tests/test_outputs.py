"""Verification tests for January support-ticket escalation model reproduction (v2 postmortem)."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import jsonschema
import numpy as np
from reference_metrics import (
    _find_optimal_temperature,
    _fit_logistic,
    _load_rows,
    _logits,
    reference_report,
    within_tolerance,
)

OUTPUT = Path("/app/artifacts/reproduction.json")
SCHEMA = Path("/tests/verifier-tools/reproduction.schema.json")
FIXTURE = Path("/app/fixtures/scoring-requests/sample.json")


def test_reproduction_file_exists():
    """Compile TypeScript and run the reproduction script to generate the output artifact."""
    if OUTPUT.exists():
        OUTPUT.unlink()

    res_tsc = subprocess.run(
        ["npx", "tsc"],
        cwd="/app",
        capture_output=True,
        text=True,
        check=False
    )

    res_rep = subprocess.run(
        ["npm", "run", "reproduce"],
        cwd="/app",
        capture_output=True,
        text=True,
        check=False
    )
    assert res_rep.returncode == 0, f"npm run reproduce failed: {res_rep.stderr}\ntsc: {res_tsc.stderr}"
    assert OUTPUT.exists(), f"missing output at {OUTPUT}"


def test_reproduction_matches_schema():
    """Verify reproduction.json satisfies the published JSON Schema contract."""
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema)


def test_class_balanced_weights_correct():
    """Verify class-balanced weights are computed as n_total / (n_classes * n_c)."""
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    expected = reference_report()
    cw = payload["class_weights"]
    ecw = expected["class_weights"]
    assert within_tolerance(cw["0"], ecw["0"], 0.01), (
        f"Class 0 weight mismatch: got {cw['0']}, expected {ecw['0']}"
    )
    assert within_tolerance(cw["1"], ecw["1"], 0.01), (
        f"Class 1 weight mismatch: got {cw['1']}, expected {ecw['1']}"
    )
    # Verify weights are inverse-frequency (not uniform)
    assert cw["0"] != cw["1"], "Class weights should differ for imbalanced data"
    assert cw["0"] > 0 and cw["1"] > 0, "Class weights must be positive"


def test_temperature_scaling_correct():
    """Verify temperature is optimized on validation set via NLL minimization."""
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    expected = reference_report()
    assert within_tolerance(payload["temperature"], expected["temperature"], 0.05), (
        f"Temperature mismatch: got {payload['temperature']}, expected {expected['temperature']}"
    )
    # Temperature must not be 1.0 (default/unscaled) — the grid search should find a better value
    assert payload["temperature"] != 1.0, "Temperature should not be the default 1.0"
    assert payload["temperature"] > 0, "Temperature must be positive"


def test_ece_computation_correct():
    """Verify Expected Calibration Error is computed correctly with 10 bins."""
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    expected = reference_report()
    assert "ece" in payload, "ECE field missing from reproduction report"
    assert 0.0 <= payload["ece"] <= 1.0, f"ECE {payload['ece']} is out of range [0, 1]"
    assert within_tolerance(payload["ece"], expected["ece"], 0.02), (
        f"ECE mismatch: got {payload['ece']}, expected {expected['ece']}"
    )

    # Verify ECE can be recomputed from the calibration bins
    bins = payload["calibration_bins"]
    n = payload["holdout_n"]
    recomputed_ece = sum(
        (b["count"] / n) * abs(b["predicted_mean"] - b["observed_rate"])
        for b in bins
        if b["count"] > 0
    )
    assert within_tolerance(payload["ece"], recomputed_ece, 0.001), (
        f"ECE {payload['ece']} does not match recomputed value {recomputed_ece} from bins"
    )


def test_threshold_optimization_correct():
    """Verify threshold is optimized for macro-F1, not a fixed percentile."""
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    expected = reference_report()
    assert "optimal_threshold" in payload, "optimal_threshold field missing"
    assert 0.01 <= payload["optimal_threshold"] <= 0.99, (
        f"Threshold {payload['optimal_threshold']} outside search range [0.01, 0.99]"
    )
    assert within_tolerance(payload["optimal_threshold"], expected["optimal_threshold"], 0.03), (
        f"Threshold mismatch: got {payload['optimal_threshold']}, expected {expected['optimal_threshold']}"
    )


def test_macro_f1_correct():
    """Verify macro-F1 is the average of per-class F1 scores."""
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    expected = reference_report()

    # Check macro_f1 matches reference
    assert within_tolerance(payload["macro_f1"], expected["macro_f1"], 0.05), (
        f"macro_f1 mismatch: got {payload['macro_f1']}, expected {expected['macro_f1']}"
    )

    # Verify macro_f1 equals average of per-class F1 scores
    per_class = payload["per_class"]
    computed_macro = (per_class["0"]["f1"] + per_class["1"]["f1"]) / 2
    assert within_tolerance(payload["macro_f1"], computed_macro, 0.001), (
        f"macro_f1 {payload['macro_f1']} != avg of per-class F1 {computed_macro}"
    )


def test_weighted_f1_correct():
    """Verify weighted-F1 uses class support as weights."""
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    expected = reference_report()
    assert within_tolerance(payload["weighted_f1"], expected["weighted_f1"], 0.05), (
        f"weighted_f1 mismatch: got {payload['weighted_f1']}, expected {expected['weighted_f1']}"
    )

    # Verify weighted_f1 uses support weights
    pc = payload["per_class"]
    total = pc["0"]["support"] + pc["1"]["support"]
    computed_weighted = (pc["0"]["f1"] * pc["0"]["support"] + pc["1"]["f1"] * pc["1"]["support"]) / total
    assert within_tolerance(payload["weighted_f1"], computed_weighted, 0.001), (
        f"weighted_f1 {payload['weighted_f1']} != support-weighted avg {computed_weighted}"
    )


def test_micro_f1_correct():
    """Verify micro-F1 is computed from global TP/FP/FN counts."""
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    expected = reference_report()
    assert within_tolerance(payload["micro_f1"], expected["micro_f1"], 0.05), (
        f"micro_f1 mismatch: got {payload['micro_f1']}, expected {expected['micro_f1']}"
    )


def test_confusion_matrix_correct():
    """Verify the confusion matrix sums to holdout_n and matches reference."""
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    expected = reference_report()
    cm = payload["confusion_matrix"]

    # Confusion matrix must sum to holdout_n
    total = cm["tp"] + cm["fp"] + cm["fn"] + cm["tn"]
    assert total == payload["holdout_n"], (
        f"Confusion matrix sum {total} != holdout_n {payload['holdout_n']}"
    )

    # Match reference values
    ecm = expected["confusion_matrix"]
    for key in ("tp", "fp", "fn", "tn"):
        assert cm[key] == ecm[key], (
            f"Confusion matrix {key} mismatch: got {cm[key]}, expected {ecm[key]}"
        )


def test_per_class_metrics_correct():
    """Verify per-class precision, recall, F1, and support match reference."""
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    expected = reference_report()

    for cls in ("0", "1"):
        for metric in ("precision", "recall", "f1"):
            actual = payload["per_class"][cls][metric]
            exp = expected["per_class"][cls][metric]
            assert within_tolerance(actual, exp, 0.05), (
                f"per_class[{cls}].{metric} mismatch: got {actual}, expected {exp}"
            )
        assert payload["per_class"][cls]["support"] == expected["per_class"][cls]["support"], (
            f"per_class[{cls}].support mismatch: got {payload['per_class'][cls]['support']}, "
            f"expected {expected['per_class'][cls]['support']}"
        )


def test_calibration_bins_shape_and_tolerance():
    """Verify calibration_bins structure, sums, and bin range boundary invariants."""
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    expected = reference_report()
    bins = payload["calibration_bins"]
    assert len(bins) == 10

    total_count = sum(b["count"] for b in bins)
    assert total_count == payload["holdout_n"], (
        f"Bin counts sum ({total_count}) != holdout_n ({payload['holdout_n']})"
    )

    for i, b in enumerate(bins):
        assert abs(b["bin_lo"] - (i / 10.0)) < 1e-5, f"bin {i} lo bound mismatch"
        assert abs(b["bin_hi"] - ((i + 1) / 10.0)) < 1e-5, f"bin {i} hi bound mismatch"
        assert b["count"] >= 0
        if b["count"] > 0:
            assert b["bin_lo"] <= b["predicted_mean"] <= b["bin_hi"], (
                f"predicted_mean {b['predicted_mean']} not in range [{b['bin_lo']}, {b['bin_hi']}]"
            )
            assert 0.0 <= b["observed_rate"] <= 1.0
        else:
            assert b["predicted_mean"] == 0.0
            assert b["observed_rate"] == 0.0

    for actual_bin, expected_bin in zip(bins, expected["calibration_bins"], strict=True):
        assert actual_bin["count"] == expected_bin["count"], (
            f"Bin count mismatch: got {actual_bin['count']}, expected {expected_bin['count']}"
        )


def test_holdout_count_matches_filtered_cohort():
    """Verify holdout_n reflects excluded channels and the January holdout date window."""
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    expected = reference_report()["holdout_n"]
    assert payload["holdout_n"] == expected


def test_brier_score_uses_temperature_scaled_proba():
    """Verify brier_score is computed with temperature-scaled probabilities."""
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    expected = reference_report()
    assert within_tolerance(payload["brier_score"], expected["brier_score"], 0.05), (
        f"brier_score mismatch: got {payload['brier_score']}, expected {expected['brier_score']}"
    )


def test_deterministic_outputs_across_runs():
    """Verify running the pipeline twice produces identical output."""
    payload1 = json.loads(OUTPUT.read_text(encoding="utf-8"))

    # Re-run the pipeline
    res = subprocess.run(
        ["node", "/app/dist/reproduce.js"],
        cwd="/app",
        capture_output=True,
        text=True,
        check=False
    )
    assert res.returncode == 0, f"Second reproduce run failed: {res.stderr}"
    payload2 = json.loads(OUTPUT.read_text(encoding="utf-8"))

    # All fields must be identical
    assert payload1 == payload2, "Non-deterministic output: two runs produced different results"


def test_scoring_request_prediction():
    """Verify the scoring pipeline correctly outputs the predicted probability for a sample request."""
    res = subprocess.run(
        ["npm", "run", "score", "--", "/app/fixtures/scoring-requests/sample.json"],
        cwd="/app",
        capture_output=True,
        text=True,
        check=False
    )
    assert res.returncode == 0, f"score script failed: {res.stderr}"

    data = None
    try:
        data = json.loads(res.stdout.strip())
    except json.JSONDecodeError:
        pass

    if data is None or "probability" not in data:
        match = re.search(r"\{[^{}]*\"probability\"[^{}]*\}", res.stdout, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

    if data is None or "probability" not in data:
        for line in res.stdout.strip().split("\n"):
            line_str = line.strip()
            if "probability" in line_str:
                m = re.search(r"\{.*\}", line_str)
                if m:
                    try:
                        data = json.loads(m.group(0))
                        break
                    except json.JSONDecodeError:
                        pass

    assert data is not None and "probability" in data, f"Could not parse JSON from score stdout: {res.stdout}"

    probability = data["probability"]
    assert 0.0 <= probability <= 1.0

    # Dynamically compute expected probability from the Python reference model
    train, holdout = _load_rows()
    w = _fit_logistic(train)
    holdout_logits = _logits(w, holdout)
    holdout_labels = np.array([r["escalated"] for r in holdout], dtype=np.float64)
    temperature = _find_optimal_temperature(holdout_logits, holdout_labels)

    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    features = np.array([
        1.0,
        payload["features"]["log_resolved_hours"],
        payload["features"]["priority_score"],
        payload["features"]["channel_web"],
        payload["features"]["api_latency_ms"] / 100.0
    ], dtype=np.float32)

    z = float(np.dot(features, w))
    expected_prob = 1.0 / (1.0 + np.exp(-z / temperature))

    assert abs(probability - expected_prob) <= 0.05, (
        f"Scoring prediction mismatch: got {probability}, expected {expected_prob}"
    )


def test_reproduction_generalizes_on_mutated_data():
    """Verify that the reproduction pipeline generalizes to a mutated database and is not hardcoded."""
    sql_path = Path("/app/data/featurestore.sql")
    backup_path = Path("/app/data/featurestore.sql.bak")
    output_path = Path("/app/artifacts/reproduction.json")

    shutil.copy2(sql_path, backup_path)

    try:
        text = sql_path.read_text(encoding="utf-8")

        ticket_re = re.compile(
            r"\('(T-\d+)',\s*'([^']+)',\s*'([^']+)',\s*'([^']+)',\s*([\d.]+),\s*(\d+),\s*'([^']+)'\)"
        )
        replay_re = re.compile(
            r"(\('T-\d+',\s*')(\{.*?\})('::jsonb)"
        )

        casing_map = {"low": "LOW", "medium": "Medium", "high": "HIGH ", "urgent": "Urgent"}

        def repl_ticket(match):
            ticket_id, created_at, channel, priority, resolved_hours, escalated, cohort = match.groups()
            rh = float(resolved_hours) * 1.05
            p = casing_map.get(priority, priority)
            return f"('{ticket_id}', '{created_at}', '{channel}', '{p}', {rh:.3f}, {escalated}, '{cohort}')"

        def repl_replay(match):
            prefix, body_str, suffix = match.groups()
            body = json.loads(body_str)
            if "features" in body and "api_latency_ms" in body["features"]:
                body["features"]["api_latency_ms"] *= 1.02
            new_body = json.dumps(body).replace("'", "''")
            return f"{prefix}{new_body}{suffix}"

        mutated_text = ticket_re.sub(repl_ticket, text)
        mutated_text = replay_re.sub(repl_replay, mutated_text)

        edge_case_sql = (
            "\nINSERT INTO tickets (ticket_id, created_at, channel, priority, resolved_hours, escalated, cohort) "
            "VALUES ('T-999999', '2025-01-15T00:00:00', 'web', 'medium', 10.0, 1, 'holdout_jan');\n"
            "INSERT INTO api_replay (ticket_id, request_body, response_score, replayed_at) "
            "VALUES ('T-999999', '{\"features\": {\"api_latency_ms\": 150.0}}'::jsonb, 0.5, '2025-01-15T01:00:00');\n"
        )
        sql_path.write_text(mutated_text + edge_case_sql, encoding="utf-8")

        if output_path.exists():
            output_path.unlink()

        res = subprocess.run(
            ["node", "/app/dist/reproduce.js"],
            cwd="/app",
            capture_output=True,
            text=True,
            check=False
        )
        assert res.returncode == 0, f"Reproduction pipeline failed on mutated database: {res.stderr}"
        assert output_path.exists(), "Reproduction pipeline did not write reproduction.json"

        payload = json.loads(output_path.read_text(encoding="utf-8"))

        # Verify key structural properties hold on mutated data
        assert payload["temperature"] > 0, "Temperature must be positive on mutated data"
        assert 0.01 <= payload["optimal_threshold"] <= 0.99, "Threshold out of range on mutated data"
        assert payload["class_weights"]["0"] > 0 and payload["class_weights"]["1"] > 0, (
            "Class weights must be positive on mutated data"
        )
        cm = payload["confusion_matrix"]
        assert cm["tp"] + cm["fp"] + cm["fn"] + cm["tn"] == payload["holdout_n"], (
            "Confusion matrix doesn't sum to holdout_n on mutated data"
        )

    finally:
        if backup_path.exists():
            shutil.move(str(backup_path), str(sql_path))

        if output_path.exists():
            output_path.unlink()
        subprocess.run(["node", "/app/dist/reproduce.js"], cwd="/app", capture_output=True, check=False)
