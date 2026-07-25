import contextlib
import json
import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import reference

APP = "/app"
WORK = "/tmp/elast_work"
EVAL = "/tmp/elast_eval"
JAR = os.path.join(WORK, "engine.jar")
KOTLINC = "/opt/kotlinc/bin/kotlinc"
JAVA = "/opt/java/openjdk/bin/java"

SEGMENTS = ["grocery", "apparel", "electronics", "home"]
PANEL_NAMES = ["committed", "a", "b", "c"]
PANELS = {}
TRUTH = {}
SEALED = {"tests": False, "interp": 0}

ZERO_EPS = 1e-9
PROJECTED_EPS = 2e-6
SEPARATION = 1e-3


def _tol(ref):
    return max(2e-6, 1e-5 * abs(ref))


def _build():
    src = os.path.join(APP, "src")
    files = sorted(
        os.path.join(r, n)
        for r, _, ns in os.walk(src)
        for n in ns
        if n.endswith(".kt")
    )
    assert files, "no kotlin sources under /app/src"
    cmd = [KOTLINC, *files, "-include-runtime", "-d", JAR]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900, check=False)
    assert r.returncode == 0, f"pipeline failed to build:\n{r.stderr[-4000:]}"
    assert os.path.isfile(JAR), "engine jar was not produced"
    os.chmod(JAR, 0o644)


def _seal():
    for path in ("/tests", os.path.dirname(os.path.abspath(__file__))):
        with contextlib.suppress(OSError):
            os.chmod(path, 0o700)
            SEALED["tests"] = True
    here = os.path.dirname(os.path.abspath(__file__))
    with contextlib.suppress(OSError):
        os.remove(os.path.join(here, "reference.py"))
    for d in ("/usr/bin", "/usr/local/bin", "/bin", "/usr/sbin"):
        if not os.path.isdir(d):
            continue
        for n in os.listdir(d):
            if not n.startswith(("python", "perl", "ruby")):
                continue
            p = os.path.join(d, n)
            if os.path.islink(p) and not os.path.exists(p):
                continue
            with contextlib.suppress(OSError):
                os.chmod(p, 0o750)
                SEALED["interp"] += 1


@pytest.fixture(scope="session", autouse=True)
def prepared():
    for d in (WORK, EVAL):
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d)
        os.chmod(d, 0o777)
    _build()
    hd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "heldout")
    PANELS["committed"] = os.path.join(APP, "data", "panel.csv")
    for name in ("a", "b", "c"):
        dst = os.path.join(EVAL, f"panel_{name}.csv")
        shutil.copy(os.path.join(hd, f"panel_{name}.csv"), dst)
        os.chmod(dst, 0o644)
        PANELS[name] = dst
    for name, path in PANELS.items():
        TRUTH[name] = reference.run(path)
    _seal()
    return TRUTH


def as_nobody(cmd, timeout=600):
    env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp"}
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, check=False,
        user="nobody", group="nogroup", extra_groups=[], cwd="/tmp", env=env,
    )


def output_for(name):
    out = os.path.join(WORK, f"out_{name}.json")
    if os.path.isfile(out):
        os.remove(out)
    r = as_nobody([JAVA, "-jar", JAR, "--panel", PANELS[name], "--out", out])
    assert r.returncode == 0, (
        f"pipeline exit {r.returncode} on {name}\n"
        f"stdout:{r.stdout[-1500:]}\nstderr:{r.stderr[-1500:]}"
    )
    assert os.path.isfile(out), f"no artifact written for {name}"
    with open(out) as f:
        return json.load(f)


def cv_by_value(obj):
    return {round(float(k), 12): v for k, v in obj["cv_mean_error"].items()}


@pytest.mark.parametrize("name", PANEL_NAMES)
def test_coefficients_match(name):
    """Every fitted coefficient on the standardized design matches ELAST-X v2."""
    got = output_for(name)["coefficients"]
    ref = TRUTH[name]["coefficients"]
    for k, v in ref.items():
        assert k in got, f"missing coefficient {k}"
        assert abs(got[k] - v) <= _tol(v), (
            f"coef {k} on {name}: got {got[k]!r} want {v!r}"
        )


@pytest.mark.parametrize("name", PANEL_NAMES)
def test_lambda_selected(name):
    """The cross-validated ridge penalty is the one-standard-error choice."""
    got = output_for(name)
    ref = TRUTH[name]["lambda"]
    assert abs(got["lambda"] - ref) <= _tol(ref)


@pytest.mark.parametrize("name", PANEL_NAMES)
def test_cv_curve_match(name):
    """The mean cross-validation error at every grid lambda matches."""
    got = cv_by_value(output_for(name))
    ref = {round(float(k), 12): v for k, v in TRUTH[name]["cv_mean_error"].items()}
    for lam, v in ref.items():
        assert lam in got, f"missing cv lambda {lam!r}"
        assert abs(got[lam] - v) <= _tol(v), (
            f"cv[{lam!r}] on {name}: got {got[lam]!r} want {v!r}"
        )


@pytest.mark.parametrize("name", PANEL_NAMES)
def test_elasticities_match(name):
    """Per-segment arc elasticities match, including any monotonicity projection."""
    got = output_for(name)["elasticities"]
    ref = TRUTH[name]["elasticities"]
    for s in SEGMENTS:
        assert s in got, f"missing elasticity {s}"
        assert abs(got[s] - ref[s]) <= _tol(ref[s]), (
            f"elasticity {s} on {name}: got {got[s]!r} want {ref[s]!r}"
        )


@pytest.mark.parametrize("name", PANEL_NAMES)
def test_holdout_metric_match(name):
    """The weighted holdout MAPE matches ELAST-X v2."""
    got = output_for(name)["holdout_weighted_mape"]
    ref = TRUTH[name]["holdout_weighted_mape"]
    assert abs(got - ref) <= _tol(ref)


def test_monotonicity_projection_is_data_driven():
    """A positive raw slope is projected to zero and other segments keep their sign."""
    assert abs(TRUTH["committed"]["elasticities"]["home"]) <= ZERO_EPS
    assert TRUTH["c"]["elasticities"]["home"] < -SEPARATION
    assert abs(output_for("committed")["elasticities"]["home"]) <= PROJECTED_EPS
    assert output_for("c")["elasticities"]["home"] < -SEPARATION


def test_output_is_not_hardcoded():
    """Held-out panels have different truth, so echoing the visible answer fails."""
    a = TRUTH["committed"]["coefficients"]
    b = TRUTH["a"]["coefficients"]
    assert any(abs(a[k] - b[k]) > SEPARATION for k in a), "held-out truth must differ"
    got_a = output_for("a")["holdout_weighted_mape"]
    ref_a = TRUTH["a"]["holdout_weighted_mape"]
    assert abs(got_a - ref_a) <= _tol(ref_a)
    visible = TRUTH["committed"]["holdout_weighted_mape"]
    assert abs(got_a - visible) > SEPARATION


def test_tests_directory_is_sealed():
    """The graded panels and reference are unreadable to the pipeline process."""
    assert SEALED["tests"], "tests directory was not sealed"
    assert SEALED["interp"] > 0, "no interpreters were sealed"
    here = os.path.dirname(os.path.abspath(__file__))
    r = as_nobody(["/bin/cat", os.path.join(here, "heldout", "panel_a.csv")])
    assert r.returncode != 0, "held-out panel is readable by the pipeline process"
