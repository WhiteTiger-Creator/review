"""Behavioral verifier for the Empirical Mode Decomposition (EMD) sifter.

The program under test reads one JSON object ``{"inputs": [<input>, ...]}`` on
standard input and writes ``{"results": [{"imfs": [[...],...], "residual": [...]}, ...]}``
on standard output, one result per input in order. Correctness is the classic
Huang-1998 sifting decomposition as implemented by the reference
``EMD-signal`` (PyEMD) package with its default configuration.

The whole corpus is fed to the program once. Each case is checked
independently: the number of IMFs, each IMF's samples, and the residual, all
to a floating-point tolerance, so a partial implementation still scores on the
cases it handles correctly.
"""
import json
import math
import os
import shutil
import subprocess

import pytest

APP = "/app"
BIN = "/app/dist/main.mjs"
CORPUS = os.path.join(os.path.dirname(__file__), "corpus.json")
RUN_TIMEOUT_SEC = 300
ATOL = 1e-6
RTOL = 1e-6


def _load():
    with open(CORPUS, encoding="utf-8") as f:
        return json.load(f)


CASES = _load()


def _build():
    make = shutil.which("make") or "make"
    # Rebuild unconditionally so a stale warm-build artifact cannot mask the source.
    subprocess.run([make, "clean"], cwd=APP, capture_output=True, text=True,
                   timeout=120)
    assert not os.path.exists(BIN), "build artifact present after 'make clean'"
    r = subprocess.run([make, "dist/main.mjs"], cwd=APP, capture_output=True,
                       text=True, timeout=600)
    assert r.returncode == 0, f"build failed (rc={r.returncode}): {r.stdout}\n{r.stderr}"
    assert os.path.exists(BIN), f"build artifact not found at {BIN}"
    return BIN


def _run_all(_binary):
    cmd = shutil.which("siftfit") or "siftfit"
    job = {"inputs": [c["input"] for c in CASES]}
    r = subprocess.run([cmd], input=json.dumps(job),
                       capture_output=True, text=True, timeout=RUN_TIMEOUT_SEC)
    assert r.returncode == 0, f"program exited nonzero: {r.stderr}"
    doc = json.loads(r.stdout.strip())
    return doc["results"]


@pytest.fixture(scope="session")
def results():
    binary = _build()
    return _run_all(binary)


def _close_series(a, b):
    if a is None or b is None:
        return False
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if not math.isclose(x, y, rel_tol=RTOL, abs_tol=ATOL):
            return False
    return True


def test_result_count(results):
    """One result object is produced for every input signal."""
    assert len(results) == len(CASES), (
        f"expected {len(CASES)} results, got {len(results)}")


def test_result_shape(results):
    """Every result carries an imfs list and a residual list of the right length."""
    bad = []
    for i, (c, r) in enumerate(zip(CASES, results)):
        n = len(c["input"]["signal"])
        if not isinstance(r, dict):
            bad.append(i)
            continue
        imfs = r.get("imfs")
        resid = r.get("residual")
        if not isinstance(imfs, list) or not isinstance(resid, list):
            bad.append(i)
            continue
        if len(resid) != n:
            bad.append(i)
            continue
        if any((not isinstance(row, list) or len(row) != n) for row in imfs):
            bad.append(i)
    assert not bad, f"malformed result at indices: {bad[:5]}"


@pytest.mark.parametrize("idx", range(len(CASES)))
def test_case(results, idx):
    """Each signal decomposes into the reference IMFs and residual within tolerance."""
    c = CASES[idx]
    exp_imfs = c["expected"]["imfs"]
    exp_resid = c["expected"]["residual"]
    got = results[idx] if idx < len(results) else None
    assert isinstance(got, dict), f"case[{idx}] missing result"
    got_imfs = got.get("imfs")
    got_resid = got.get("residual")

    assert isinstance(got_imfs, list) and len(got_imfs) == len(exp_imfs), (
        f"case[{idx}] n={len(c['input']['signal'])} max_imf={c['input']['max_imf']}: "
        f"expected {len(exp_imfs)} IMFs, got "
        f"{len(got_imfs) if isinstance(got_imfs, list) else got_imfs}")

    for k in range(len(exp_imfs)):
        assert _close_series(got_imfs[k], exp_imfs[k]), (
            f"case[{idx}] IMF[{k}] mismatch: "
            f"expected[:4]={exp_imfs[k][:4]}, got[:4]={got_imfs[k][:4]}")

    assert _close_series(got_resid, exp_resid), (
        f"case[{idx}] residual mismatch: "
        f"expected[:4]={exp_resid[:4]}, got[:4]={(got_resid or [])[:4]}")
