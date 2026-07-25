import json
import os
import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

DATA = "/app/data/sensors.csv"
OUT = "/app/outputs"
ATOL = 1e-6
FPR_BOUND = 0.1
SENS_TARGET = 0.95


def load(path=DATA):
    d = pd.read_csv(path)
    return d["CO2"].to_numpy(float), d["Occupancy"].to_numpy(int)


def reference(s, y):
    p = int((y == 1).sum())
    n = int((y == 0).sum())
    thr = np.unique(s)
    order = np.argsort(-s, kind="mergesort")
    ys = y[order]
    ss = s[order]
    cpos = np.cumsum(ys == 1)
    tp = np.zeros(len(thr), int)
    fp = np.zeros(len(thr), int)
    for k, t in enumerate(thr):
        m = int(np.searchsorted(-ss, -t, side="right"))
        if m == 0:
            continue
        tp[k] = int(cpos[m - 1])
        fp[k] = m - int(cpos[m - 1])
    tn = n - fp
    fn = p - tp
    tpr = tp / p
    fpr = fp / n
    od = np.lexsort((tpr, fpr))
    fx = np.concatenate([[0.0], fpr[od]])
    tx = np.concatenate([[0.0], tpr[od]])
    auc = float(np.trapezoid(tx, fx))
    keep = fx <= FPR_BOUND + 1e-12
    xf = fx[keep]
    yt = tx[keep]
    if xf[-1] < FPR_BOUND:
        kk = int(np.where(fx > FPR_BOUND)[0][0])
        yi = tx[kk - 1] + (tx[kk] - tx[kk - 1]) * (FPR_BOUND - fx[kk - 1]) / (
            fx[kk] - fx[kk - 1]
        )
        xf = np.append(xf, FPR_BOUND)
        yt = np.append(yt, yi)
    raw = float(np.trapezoid(yt, xf))
    std = (1 + (raw - FPR_BOUND**2 / 2) / (FPR_BOUND - FPR_BOUND**2 / 2)) / 2
    sel = np.where(tpr >= SENS_TARGET)[0]
    best = sel[np.lexsort((-thr[sel], fpr[sel]))[0]]
    op = {
        "threshold": float(thr[best]),
        "tp": int(tp[best]),
        "fp": int(fp[best]),
        "tn": int(tn[best]),
        "fn": int(fn[best]),
        "tpr": float(tpr[best]),
        "fpr": float(fpr[best]),
        "precision": float(tp[best] / (tp[best] + fp[best])),
        "f1": float(
            2
            * (tp[best] / (tp[best] + fp[best]))
            * tpr[best]
            / ((tp[best] / (tp[best] + fp[best])) + tpr[best])
        ),
    }
    so = np.argsort(thr, kind="mergesort")
    return {
        "n_pos": p,
        "n_neg": n,
        "auc": auc,
        "raw": raw,
        "std": std,
        "op": op,
        "thr": thr[so],
        "tp": tp[so],
        "fp": fp[so],
        "tn": tn[so],
        "fn": fn[so],
        "tpr": tpr[so],
        "fpr": fpr[so],
    }


@pytest.fixture(scope="module")
def ref():
    """Independent reference computed from the raw data via the trapezoid route."""
    s, y = load()
    return reference(s, y)


@pytest.fixture(scope="module")
def roc():
    """Load the candidate operating-point table."""
    return pd.read_csv(os.path.join(OUT, "roc_points.csv"))


@pytest.fixture(scope="module")
def metrics():
    """Load the candidate metrics summary."""
    with open(os.path.join(OUT, "metrics.json")) as fh:
        return json.load(fh)


def test_artifacts_present():
    """Both required output files exist."""
    assert os.path.isfile(os.path.join(OUT, "roc_points.csv"))
    assert os.path.isfile(os.path.join(OUT, "metrics.json"))


def test_class_counts(metrics, ref):
    """Reported positive and negative counts match the data."""
    assert int(metrics["n_pos"]) == ref["n_pos"]
    assert int(metrics["n_neg"]) == ref["n_neg"]


def test_auc_matches(metrics, ref):
    """Reported area under the curve matches the independent trapezoid route."""
    assert abs(float(metrics["auc"]) - ref["auc"]) <= ATOL


def test_partial_auc_raw(metrics, ref):
    """Reported raw partial area matches the reference."""
    assert abs(float(metrics["partial_auc_raw"]) - ref["raw"]) <= ATOL


def test_partial_auc_standardized(metrics, ref):
    """Reported standardised partial area matches the reference."""
    assert abs(float(metrics["partial_auc_standardized"]) - ref["std"]) <= ATOL


def test_partial_auc_is_standardized_not_raw(metrics, ref):
    """Standardised partial area differs from the raw area as required."""
    assert abs(ref["std"] - ref["raw"]) > 1e-3
    assert abs(float(metrics["partial_auc_standardized"]) - ref["raw"]) > 1e-3


def test_reported_bounds(metrics):
    """Reported false-positive bound and sensitivity target are the disclosed values."""
    assert abs(float(metrics["fpr_bound"]) - FPR_BOUND) <= ATOL
    assert abs(float(metrics["sensitivity_target"]) - SENS_TARGET) <= ATOL


def test_roc_row_count(roc, ref):
    """Operating-point table has one row per distinct threshold."""
    assert len(roc) == len(ref["thr"])


def test_roc_sorted_by_threshold(roc):
    """Operating-point rows are ordered by ascending threshold."""
    t = roc["threshold"].to_numpy(float)
    assert (np.diff(t) > 0).all()


@pytest.mark.parametrize("frac", [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0])
def test_roc_confusion_counts(roc, ref, frac):
    """Confusion counts at a sampled threshold match the reference."""
    k = min(int(frac * (len(ref["thr"]) - 1)), len(ref["thr"]) - 1)
    row = roc.iloc[k]
    assert int(row["tp"]) == int(ref["tp"][k])
    assert int(row["fp"]) == int(ref["fp"][k])
    assert int(row["tn"]) == int(ref["tn"][k])
    assert int(row["fn"]) == int(ref["fn"][k])


def test_roc_all_confusion_counts(roc, ref):
    """Every confusion count in the table matches the reference."""
    assert (roc["tp"].to_numpy(int) == ref["tp"]).all()
    assert (roc["fp"].to_numpy(int) == ref["fp"]).all()
    assert (roc["tn"].to_numpy(int) == ref["tn"]).all()
    assert (roc["fn"].to_numpy(int) == ref["fn"]).all()


def test_roc_rates_match(roc, ref):
    """Every true-positive and false-positive rate matches the reference."""
    assert np.max(np.abs(roc["tpr"].to_numpy(float) - ref["tpr"])) <= ATOL
    assert np.max(np.abs(roc["fpr"].to_numpy(float) - ref["fpr"])) <= ATOL


def test_confusion_counts_consistent(roc, ref):
    """Each row's four confusion counts sum to the sample size."""
    tot = (
        roc["tp"].to_numpy(int)
        + roc["fp"].to_numpy(int)
        + roc["tn"].to_numpy(int)
        + roc["fn"].to_numpy(int)
    )
    assert (tot == ref["n_pos"] + ref["n_neg"]).all()


def test_auc_matches_table_trapezoid(roc, metrics, ref):
    """Reported area equals the trapezoid area of the reported operating points."""
    tpr = roc["tpr"].to_numpy(float)
    fpr = roc["fpr"].to_numpy(float)
    od = np.lexsort((tpr, fpr))
    fx = np.concatenate([[0.0], fpr[od]])
    tx = np.concatenate([[0.0], tpr[od]])
    area = float(np.trapezoid(tx, fx))
    assert abs(area - float(metrics["auc"])) <= 1e-4


@pytest.mark.parametrize(
    "field", ["threshold", "tp", "fp", "tn", "fn", "tpr", "fpr", "precision", "f1"]
)
def test_operating_point_fields(metrics, ref, field):
    """Each operating-point field matches the reference."""
    got = metrics["operating_point"][field]
    exp = ref["op"][field]
    if isinstance(exp, int):
        assert int(got) == exp
    else:
        assert abs(float(got) - float(exp)) <= ATOL


def test_operating_point_meets_sensitivity(metrics):
    """Selected operating point meets the sensitivity requirement."""
    assert float(metrics["operating_point"]["tpr"]) >= SENS_TARGET - ATOL


def test_operating_point_confusion_reproduces(metrics, ref):
    """Operating-point confusion reproduces from its threshold on the raw data."""
    s, y = load()
    t = float(metrics["operating_point"]["threshold"])
    pred = s >= t
    assert int((pred & (y == 1)).sum()) == int(metrics["operating_point"]["tp"])
    assert int((pred & (y == 0)).sum()) == int(metrics["operating_point"]["fp"])


def _rerun(df):
    bak = DATA + ".bak"
    ob = OUT + ".bak"
    shutil.copy2(DATA, bak)
    if os.path.isdir(ob):
        shutil.rmtree(ob)
    shutil.copytree(OUT, ob)
    try:
        df.to_csv(DATA, index=False)
        proc = subprocess.run(
            ["bash", "/app/run.sh"],
            capture_output=True,
            text=True,
            timeout=420,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr[-2000:]
        with open(os.path.join(OUT, "metrics.json")) as fh:
            return json.load(fh)
    finally:
        shutil.copy2(bak, DATA)
        os.remove(bak)
        shutil.rmtree(OUT)
        shutil.copytree(ob, OUT)
        shutil.rmtree(ob)


def test_variant_score_negation_metamorphic(ref):
    """Negating the score and flipping the outcome leaves the area unchanged."""
    d = pd.read_csv(DATA)
    d["CO2"] = -d["CO2"].to_numpy()
    d["Occupancy"] = 1 - d["Occupancy"].to_numpy()
    got = _rerun(d)
    assert abs(float(got["auc"]) - ref["auc"]) <= 1e-4


def test_variant_row_subset():
    """Re-running on a row subset reproduces the recomputed reference."""
    d = pd.read_csv(DATA)
    d = d.iloc[: int(len(d) * 0.6)].copy()
    got = _rerun(d)
    s = d["CO2"].to_numpy(float)
    y = d["Occupancy"].to_numpy(int)
    exp = reference(s, y)
    assert abs(float(got["auc"]) - exp["auc"]) <= 1e-4
    assert int(got["operating_point"]["tp"]) == exp["op"]["tp"]
    assert abs(float(got["partial_auc_standardized"]) - exp["std"]) <= 1e-4
