import csv
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

CLASSES = ["A", "F", "E", "I", "X", "H"]
BUNDLES = [
    "main",
    "relabel",
    "roworder",
    "fresh",
    "sparse_anchors",
    "fresh_sparse_anchors",
]
HIDDEN = Path("/tests/hidden")
OUTPUT_ROOT = Path("/tmp/avila_outputs")
MODEL = Path("/app/model.R")
EXPECTED_COLUMNS = [
    "observation_id",
    "predicted_class",
    "prob_A",
    "prob_F",
    "prob_E",
    "prob_I",
    "prob_X",
    "prob_H",
]
MIN_BALANCED_ACCURACY = 0.60
MAX_LOG_LOSS = 1.35
_CACHE = {}
_STAGED = {}
CANDIDATE_FILES = [
    "features.csv",
    "anchors.csv",
    "annotations.csv",
    "vocabularies.csv",
    "classes.csv",
]


def _read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _bundle_dir(name):
    if name == "main":
        return Path("/app/data")
    if name not in _STAGED:
        staged = Path(tempfile.mkdtemp(prefix=f"avila-{name}-"))
        for filename in CANDIDATE_FILES:
            destination = staged / filename
            shutil.copyfile(HIDDEN / name / filename, destination)
            destination.chmod(0o644)
        staged.chmod(0o755)
        _STAGED[name] = staged
    return _STAGED[name]


def _run_bundle(name):
    if name in _CACHE:
        return _CACHE[name]
    output = OUTPUT_ROOT / f"{name}.csv"
    env = dict(os.environ)
    env["WL_DATA_DIR"] = str(_bundle_dir(name))
    env["WL_OUTPUT_PATH"] = str(output)
    process = subprocess.run(
        [
            "/usr/bin/setpriv",
            "--reuid=65534",
            "--regid=65534",
            "--clear-groups",
            "--no-new-privs",
            "Rscript",
            str(MODEL),
        ],
        cwd="/app",
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert process.returncode == 0, process.stderr[-3000:]
    assert output.is_file()
    rows = _read_csv(output)
    targets = {
        row["observation_id"]: row["canonical_class"]
        for row in _read_csv(HIDDEN / name / "targets.csv")
    }
    _CACHE[name] = (rows, targets)
    return _CACHE[name]


def _validated_predictions(name):
    rows, targets = _run_bundle(name)
    assert len(rows) == len(targets)
    assert rows
    assert list(rows[0]) == EXPECTED_COLUMNS
    observed = {}
    for row in rows:
        obs_id = row["observation_id"]
        assert obs_id in targets
        assert obs_id not in observed
        probabilities = [float(row[f"prob_{label}"]) for label in CLASSES]
        assert all(math.isfinite(value) and value >= 0 for value in probabilities)
        assert abs(sum(probabilities) - 1.0) <= 1e-6
        best = max(range(len(CLASSES)), key=lambda index: probabilities[index])
        assert row["predicted_class"] == CLASSES[best]
        observed[obs_id] = (row["predicted_class"], probabilities)
    assert set(observed) == set(targets)
    return observed, targets


def _balanced_accuracy(targets, predictions):
    recalls = []
    for label in CLASSES:
        ids = [obs_id for obs_id, truth in targets.items() if truth == label]
        correct = sum(predictions[obs_id][0] == label for obs_id in ids)
        recalls.append(correct / len(ids))
    return sum(recalls) / len(recalls)


def _log_loss(targets, predictions):
    total = 0.0
    for obs_id, truth in targets.items():
        probability = predictions[obs_id][1][CLASSES.index(truth)]
        total -= math.log(max(probability, 1e-15))
    return total / len(targets)


def test_model_program_present():
    """The submitted model program exists at the disclosed path."""
    assert MODEL.is_file()


@pytest.mark.parametrize("name", BUNDLES)
def test_prediction_contract(name):
    """Every bundle produces complete normalized canonical predictions."""
    _validated_predictions(name)


@pytest.mark.parametrize("name", BUNDLES)
def test_held_out_balanced_accuracy(name):
    """Predictions generalize across every withheld copyist class."""
    predictions, targets = _validated_predictions(name)
    score = _balanced_accuracy(targets, predictions)
    assert score >= MIN_BALANCED_ACCURACY


@pytest.mark.parametrize("name", BUNDLES)
def test_held_out_log_loss(name):
    """Reported probabilities remain useful on withheld copyist labels."""
    predictions, targets = _validated_predictions(name)
    score = _log_loss(targets, predictions)
    assert score <= MAX_LOG_LOSS
