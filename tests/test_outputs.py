import csv
import json
import math
import subprocess
import tempfile
from pathlib import Path

import mpmath as mp
import numpy as np
import pytest
from numpy.polynomial.hermite_e import hermegauss

mp.mp.dps = 40

APP = Path("/app")
TESTS = Path(__file__).resolve().parent
AGENT = APP / "solve.R"
PUBLIC = APP / "data"
HIDDEN_A = TESTS / "fixtures" / "hidden_a"
HIDDEN_B = TESTS / "fixtures" / "hidden_b"
HIDDEN_SCALED = TESTS / "fixtures" / "hidden_scaled"

REL_TOL = 1e-8
ABS_TOL = 1e-10
META_TOL = 1e-7
SCALE_C = 3.0
GH_ORDER = 80
PSD_SLACK = 1e-10
MIN_CASES = 60
MODE_STEP = 1e-4
MODE_VERTEX_TOL = 1e-2

_NODES, _WEIGHTS = hermegauss(GH_ORDER)
_WEIGHTS = _WEIGHTS / math.sqrt(2.0 * math.pi)

CASES = []


def _read(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def _qnorm(p):
    return float(mp.sqrt(2) * mp.erfinv(2 * mp.mpf(str(p)) - 1))


def _kernel(a, b, sv, ell):
    return sv * np.exp(-0.5 * ((a[:, None] - b[None, :]) / ell) ** 2)


def _warp(name, y, lam):
    if name == "identity":
        return y.copy(), np.ones_like(y)
    if name == "log":
        return np.log(y), 1.0 / y
    return (y**lam - 1.0) / lam, y ** (lam - 1.0)


def _ginv(name, u, lam):
    if name == "identity":
        return u
    if name == "log":
        return np.exp(u)
    base = lam * u + 1.0
    out = np.full(np.shape(base), np.nan, dtype=float)
    ok = base > 0.0
    out[ok] = base[ok] ** (1.0 / lam)
    return out


def _mode(name, mu, var, lam):
    """The mode of the predictive law of radius, or None where none exists."""
    if name == "identity":
        return [float(v) for v in mu]
    if name == "log":
        return [float(v) for v in np.exp(mu - var)]
    if lam < 1.0:
        return None
    base = 1.0 + lam * mu
    root = (base + np.sqrt(base**2 + 4.0 * lam * var * (lam - 1.0))) / 2.0
    return [float(v) for v in root ** (1.0 / lam)]


def _log_density(name, r, m, sd, lam):
    """Log density of radius r under the back-transformed predictive law.

    Up to an additive constant, and independent of the closed form in _mode.
    """
    if name != "identity" and r <= 0.0:
        return -math.inf
    if name == "identity":
        g, ljac = r, 0.0
    elif name == "log":
        g, ljac = math.log(r), -math.log(r)
    else:
        g, ljac = (r**lam - 1.0) / lam, (lam - 1.0) * math.log(r)
    return -((g - m) ** 2) / (2.0 * sd * sd) + ljac


def _nullify(arr):
    return [
        None if not math.isfinite(float(v)) else float(v) for v in np.atleast_1d(arr)
    ]


def _gh_mean(m, v):
    return float(np.sum(_WEIGHTS * np.exp(m + math.sqrt(v) * _NODES)))


def _gh_cov(mu, sig, i, j):
    sii, sjj, sij = sig[i, i], sig[j, j], sig[i, j]
    cvar = sjj - sij * sij / sii
    t = mu[i] + math.sqrt(sii) * _NODES
    inner = np.exp(mu[j] + (sij / sii) * (t - mu[i]) + cvar / 2.0)
    joint = float(np.sum(_WEIGHTS * np.exp(t) * inner))
    return joint - math.exp(mu[i] + sii / 2.0) * math.exp(mu[j] + sjj / 2.0)


def _solve_block(wname, train, xq, par):
    x, y, sg = train
    sv, ell, jit, lam, zlo, zhi = par
    n = len(x)
    z, gp = _warp(wname, y, lam)
    s = sg * gp
    centre = z.mean()
    zt = z - centre
    amat = _kernel(x, x, sv, ell) + np.diag(s**2) + jit * np.eye(n)
    evals, evecs = np.linalg.eigh(amat)
    proj = evecs.T @ zt
    evidence = (
        -0.5 * float(np.sum(proj**2 / evals))
        - 0.5 * float(np.sum(np.log(evals)))
        - 0.5 * n * math.log(2.0 * math.pi)
        + float(np.sum(np.log(gp)))
    )
    kq = _kernel(x, xq, sv, ell)
    mu = centre + kq.T @ (evecs @ (proj / evals))
    sig = _kernel(xq, xq, sv, ell) - kq.T @ (evecs @ ((evecs.T @ kq) / evals[:, None]))
    dg = np.diag(sig).copy()
    block = {
        "warp": wname,
        "evidence": evidence,
        "median": _nullify(_ginv(wname, mu, lam)),
        "mode": _mode(wname, mu, dg, lam),
        "mu_warped": list(mu),
        "sd_warped": list(np.sqrt(dg)),
        "lam": lam,
        "quantile_low": _nullify(_ginv(wname, mu + np.sqrt(dg) * zlo, lam)),
        "quantile_high": _nullify(_ginv(wname, mu + np.sqrt(dg) * zhi, lam)),
        "n_train": n,
    }
    if wname == "boxcox":
        block["mean"] = None
        block["covariance"] = None
    elif wname == "identity":
        block["mean"] = list(mu)
        block["covariance"] = sig.tolist()
    else:
        block["mean"] = [_gh_mean(mu[k], dg[k]) for k in range(len(mu))]
        block["covariance"] = [
            [_gh_cov(mu, sig, i, j) for j in range(len(mu))] for i in range(len(mu))
        ]
    return block


def reference(data_dir):
    planets = _read(data_dir / "planets.csv")
    qtab = _read(data_dir / "queries.csv")
    out = []
    for cf in _read(data_dir / "configurations.csv"):
        rows = [r for r in planets if r["facility"] == cf["facility"]][
            : int(cf["n_train"])
        ]
        x = np.array([float(r["log_mass_earth"]) for r in rows])
        y = np.array([float(r["radius_earth"]) for r in rows])
        sg = np.array([float(r["radius_sigma_earth"]) for r in rows])
        qrows = sorted(
            (r for r in qtab if r["config_id"] == cf["config_id"]),
            key=lambda r: int(r["query_index"]),
        )
        xq = np.array([float(r["log_mass_earth"]) for r in qrows])
        par = (
            float(cf["signal_variance"]),
            float(cf["lengthscale"]),
            float(cf["jitter"]),
            float(cf["boxcox_lambda"]),
            _qnorm(cf["quantile_low"]),
            _qnorm(cf["quantile_high"]),
        )
        warps = cf["warp_catalogue"].split(";")
        blocks = [_solve_block(w, (x, y, sg), xq, par) for w in warps]
        evs = [b["evidence"] for b in blocks]
        top = max(evs)
        tol = float(cf["tie_tolerance"])
        selected = warps[min(i for i, e in enumerate(evs) if e >= top - tol)]
        out.append(
            {"config_id": cf["config_id"], "selected_warp": selected, "warps": blocks}
        )
    return out


def run_agent(data_dir):
    assert AGENT.is_file(), f"agent program missing at {AGENT}"
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "answer.json"
        proc = subprocess.run(
            ["Rscript", str(AGENT), str(data_dir), str(dest)],
            check=False,
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert proc.returncode == 0, (
            f"agent failed on {data_dir}: {proc.stderr[-2000:]}"
        )
        assert dest.is_file(), f"agent wrote no output for {data_dir}"
        with open(dest) as fh:
            return json.load(fh)


def close(got, want):
    if isinstance(got, bool) or not isinstance(got, (int, float)):
        return False
    if not math.isfinite(got):
        return False
    return abs(got - want) <= max(REL_TOL * abs(want), ABS_TOL)


def _check_quantile_arrays(gw, rw, tag):
    for key in ("median", "quantile_low", "quantile_high"):
        arr = gw.get(key)
        assert isinstance(arr, list) and len(arr) == len(rw[key]), f"{tag}: bad {key}"
        for k, want in enumerate(rw[key]):
            if want is None:
                assert arr[k] is None, (
                    f"{tag}: {key}[{k}] must be null, the inverse warp is undefined there"
                )
            else:
                assert close(arr[k], want), (
                    f"{tag}: {key}[{k}] {arr[k]} expected {want}"
                )
                if rw["warp"] != "identity":
                    assert arr[k] > 0.0, f"{tag}: {key}[{k}] not positive"
            CASES.append(1)
    lo, mid, hi = gw["quantile_low"], gw["median"], gw["quantile_high"]
    for k in range(len(mid)):
        if lo[k] is not None and mid[k] is not None and hi[k] is not None:
            assert lo[k] < mid[k] < hi[k], f"{tag}: quantile ordering violated at {k}"


def _check_mean(gw, rw, tag):
    gm = gw.get("mean")
    assert isinstance(gm, list) and len(gm) == len(rw["mean"]), f"{tag}: bad mean"
    for k, want in enumerate(rw["mean"]):
        assert close(gm[k], want), f"{tag}: mean[{k}] {gm[k]} expected {want}"
        CASES.append(1)
    if rw["warp"] == "log":
        for k, mval in enumerate(gm):
            assert mval > gw["median"][k], f"{tag}: mean must exceed median at {k}"
            CASES.append(1)


def _check_covariance(gw, rw, tag):
    ref_cov = rw["covariance"]
    gcov = gw.get("covariance")
    m = len(ref_cov)
    assert isinstance(gcov, list) and len(gcov) == m, f"{tag}: bad covariance"
    for i in range(m):
        assert isinstance(gcov[i], list) and len(gcov[i]) == m, (
            f"{tag}: bad covariance row"
        )
        for j in range(m):
            want = ref_cov[i][j]
            got = gcov[i][j]
            scale = math.sqrt(abs(ref_cov[i][i] * ref_cov[j][j]))
            assert isinstance(got, (int, float)) and math.isfinite(got), (
                f"{tag}: covariance[{i}][{j}] not finite"
            )
            assert abs(got - want) <= max(
                REL_TOL * abs(want), REL_TOL * scale, ABS_TOL
            ), f"{tag}: covariance[{i}][{j}] {got} expected {want}"
            CASES.append(1)
    arr = np.array(gcov, dtype=float)
    peak = max(abs(arr).max(), 1.0)
    assert np.allclose(arr, arr.T, rtol=0, atol=1e-9 * peak), (
        f"{tag}: covariance not symmetric"
    )
    evals = np.linalg.eigvalsh((arr + arr.T) / 2.0)
    assert evals.min() > -PSD_SLACK * max(abs(evals).max(), 1.0), (
        f"{tag}: covariance not positive semidefinite"
    )
    CASES.append(1)


def _check_mode(gw, rw, tag):
    ref = rw["mode"]
    got = gw.get("mode", "missing")
    if ref is None:
        assert got is None, (
            f"{tag}: mode must be null, the density of radius attains no "
            f"maximum under this warp"
        )
        CASES.append(1)
        return
    assert isinstance(got, list) and len(got) == len(ref), f"{tag}: bad mode"
    for k, want in enumerate(ref):
        assert close(got[k], want), f"{tag}: mode[{k}] {got[k]} expected {want}"
        CASES.append(1)

    # Independent confirmation that the reported point maximises the radius
    # scale density, using a direct evaluation of that density rather than the
    # closed form the reference used to produce it.
    for k, spot in enumerate(got):
        m = rw["mu_warped"][k]
        sd = rw["sd_warped"][k]
        step = MODE_STEP * max(abs(spot), 1.0)
        here = _log_density(rw["warp"], spot, m, sd, rw["lam"])
        up = _log_density(rw["warp"], spot + step, m, sd, rw["lam"])
        down = _log_density(rw["warp"], spot - step, m, sd, rw["lam"])
        assert here > up and here > down, (
            f"{tag}: mode[{k}] is not a local maximum of the density"
        )
        curve = up - 2.0 * here + down
        assert curve < 0.0, f"{tag}: mode[{k}] sits where the density is convex"
        vertex = step * (down - up) / (2.0 * curve)
        assert abs(vertex) <= MODE_VERTEX_TOL * step, (
            f"{tag}: mode[{k}] is not stationary; the density peaks {vertex} away"
        )
        CASES.append(1)


def _check_warp_block(gw, rw, tag):
    assert gw.get("warp") == rw["warp"], f"{tag}: warp name or ordering mismatch"
    assert close(gw.get("evidence"), rw["evidence"]), (
        f"{tag}: evidence {gw.get('evidence')} expected {rw['evidence']}"
    )
    CASES.append(1)
    _check_mode(gw, rw, tag)
    _check_quantile_arrays(gw, rw, tag)
    if rw["mean"] is None:
        assert gw.get("mean", "missing") is None, (
            f"{tag}: mean must be null, the expectation does not exist under this warp"
        )
        assert gw.get("covariance", "missing") is None, (
            f"{tag}: covariance must be null"
        )
        CASES.extend([1, 1])
        return
    _check_mean(gw, rw, tag)
    _check_covariance(gw, rw, tag)


def compare(answer, ref):
    assert isinstance(answer, dict), "answer is not a JSON object"
    got_cfgs = answer.get("configurations")
    assert isinstance(got_cfgs, list), "missing configurations array"
    assert len(got_cfgs) == len(ref), "configuration count mismatch"
    for gc, rc in zip(got_cfgs, ref, strict=True):
        assert gc.get("config_id") == rc["config_id"], "config_id or ordering mismatch"
        assert gc.get("selected_warp") == rc["selected_warp"], (
            f"{rc['config_id']}: selected_warp {gc.get('selected_warp')} "
            f"expected {rc['selected_warp']}"
        )
        CASES.append(1)
        gws = gc.get("warps")
        assert isinstance(gws, list) and len(gws) == len(rc["warps"]), (
            "warp block count mismatch"
        )
        for gw, rw in zip(gws, rc["warps"], strict=True):
            _check_warp_block(gw, rw, f"{rc['config_id']}/{rw['warp']}")


@pytest.mark.parametrize(
    "data_dir", [PUBLIC, HIDDEN_A, HIDDEN_B], ids=["public", "hidden_a", "hidden_b"]
)
def test_contract(data_dir):
    """Every reported quantity matches an independent recomputation of the contract."""
    compare(run_agent(data_dir), reference(data_dir))


def test_unit_change_metamorphic():
    """Rescaling radius and its uncertainty shifts log-warp evidence by exactly minus n log c."""
    base = run_agent(HIDDEN_A)
    scaled = run_agent(HIDDEN_SCALED)
    ref = reference(HIDDEN_A)
    shift = math.log(SCALE_C)
    checked = 0
    for bc, sc, rc in zip(
        base["configurations"], scaled["configurations"], ref, strict=True
    ):
        bmap = {w["warp"]: w for w in bc["warps"]}
        smap = {w["warp"]: w for w in sc["warps"]}
        n = next(w["n_train"] for w in rc["warps"] if w["warp"] == "log")
        want = -n * shift
        got = smap["log"]["evidence"] - bmap["log"]["evidence"]
        assert abs(got - want) <= META_TOL * max(abs(want), 1.0), (
            f"{rc['config_id']}: log-warp evidence shift {got} expected {want}"
        )
        checked += 1
        for k, bmed in enumerate(bmap["log"]["median"]):
            assert close(smap["log"]["median"][k], SCALE_C * bmed), (
                f"{rc['config_id']}: median[{k}] did not scale with the unit change"
            )
            checked += 1
        for k, bmode in enumerate(bmap["log"]["mode"]):
            assert close(smap["log"]["mode"][k], SCALE_C * bmode), (
                f"{rc['config_id']}: mode[{k}] did not scale with the unit change"
            )
            checked += 1
        for i, row in enumerate(bmap["log"]["covariance"]):
            for j, bval in enumerate(row):
                assert close(
                    smap["log"]["covariance"][i][j], SCALE_C * SCALE_C * bval
                ), (
                    f"{rc['config_id']}: covariance[{i}][{j}] did not scale with c squared"
                )
                checked += 1
    CASES.extend([1] * checked)
    assert checked > 0, "metamorphic relation executed no cases"


@pytest.mark.parametrize(
    "data_dir", [PUBLIC, HIDDEN_A, HIDDEN_B], ids=["public", "hidden_a", "hidden_b"]
)
def test_absent_mode_matches_an_unbounded_density(data_dir):
    """Where the reference reports no mode, the density really does grow without bound.

    Confirms the null is the correct answer rather than merely the expected one.
    """
    absent = 0
    for cfg in reference(data_dir):
        for warp in cfg["warps"]:
            if warp["mode"] is not None:
                continue
            absent += 1
            lam = warp["lam"]
            assert lam < 1.0, (
                f"{cfg['config_id']}/{warp['warp']}: mode reported absent but the "
                f"density is bounded at the lower endpoint"
            )
            # Deep enough that the warped value has settled at its endpoint limit,
            # so each further decade multiplies the density by a fixed factor.
            per_decade = (1.0 - lam) * math.log(10.0)
            for k in range(len(warp["mu_warped"])):
                m = warp["mu_warped"][k]
                sd = warp["sd_warped"][k]
                near = _log_density(warp["warp"], 1e-60, m, sd, lam)
                deeper = _log_density(warp["warp"], 1e-61, m, sd, lam)
                gain = deeper - near
                assert gain > 0.0 and abs(gain - per_decade) <= 1e-6 * per_decade, (
                    f"{cfg['config_id']}/{warp['warp']}: density at query {k} grows "
                    f"by {gain} per decade toward zero radius, not {per_decade}, so "
                    f"it does not diverge and a mode should exist"
                )
                CASES.append(1)
    assert absent > 0, "no absent-mode case was exercised"


def test_case_floor():
    """The graded run executes at least the required number of semantic cases."""
    total = len(CASES)
    print(f"executed semantic cases: {total}")
    assert total >= MIN_CASES, f"executed {total} semantic cases, floor is {MIN_CASES}"
