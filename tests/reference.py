import csv
import math

SEGMENTS = ["grocery", "apparel", "electronics", "home"]
OFFSET = 8.0
RECENCY = 0.97
LAMBDA_GRID = [0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0]
WINSOR = {
    "log_price": (2.5, 97.5),
    "log_competitor_price": (2.5, 97.5),
    "log_traffic": (5.0, 100.0),
}
CONT = ["log_price", "log_competitor_price", "log_traffic", "week_trend"]
KFOLDS = 5
EMBARGO = 3
HOLDOUT_START = 48
N_WEEKS = 60
ARC_STEP = 0.10
MAPE_FLOOR = 5.0
WEIGHT_FLOOR = 1e-6

COVARS = ["log_competitor_price", "promo", "holiday", "log_traffic", "week_trend"]


def _row(r):
    return {
        "product_id": int(r["product_id"]),
        "segment": r["segment"],
        "week": int(r["week"]),
        "price": float(r["price"]),
        "units": float(r["units"]),
        "competitor_price": float(r["competitor_price"]),
        "promo": float(r["promo"]),
        "holiday": float(r["holiday"]),
        "traffic": float(r["traffic"]),
    }


def read_panel(path):
    with open(path) as f:
        return [_row(r) for r in csv.DictReader(f)]


def feats(rows):
    return {
        "log_price": [math.log(r["price"]) for r in rows],
        "log_competitor_price": [math.log(r["competitor_price"]) for r in rows],
        "log_traffic": [math.log(r["traffic"]) for r in rows],
        "week_trend": [r["week"] / N_WEEKS for r in rows],
        "promo": [r["promo"] for r in rows],
        "holiday": [r["holiday"] for r in rows],
        "units": [r["units"] for r in rows],
        "segment": [r["segment"] for r in rows],
        "week": [r["week"] for r in rows],
        "price": [r["price"] for r in rows],
    }


def wpercentile(x, w, q):
    idx = sorted(range(len(x)), key=lambda i: x[i])
    xs = [x[i] for i in idx]
    ws = [w[i] for i in idx]
    tot = sum(ws)
    c = 0.0
    cum = []
    for wi in ws:
        cum.append((c + wi / 2.0) / tot)
        c += wi
    t = q / 100.0
    if t <= cum[0]:
        return xs[0]
    if t >= cum[-1]:
        return xs[-1]
    for i in range(1, len(cum)):
        if t <= cum[i]:
            span = cum[i] - cum[i - 1]
            f = (t - cum[i - 1]) / span if span != 0 else 0.0
            return xs[i - 1] + f * (xs[i] - xs[i - 1])
    return xs[-1]


def solve(a, b):
    n = len(b)
    m = [[*row, b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        piv = m[c][c]
        for r in range(n):
            if r == c:
                continue
            fr = m[r][c] / piv
            for k in range(c, n + 1):
                m[r][k] -= fr * m[c][k]
    return [m[i][n] / m[i][i] for i in range(n)]


def wmean_wstd(x, w):
    sw = sum(w)
    m = sum(wi * xi for wi, xi in zip(w, x, strict=True)) / sw
    v = sum(wi * (xi - m) ** 2 for wi, xi in zip(w, x, strict=True)) / sw
    return m, math.sqrt(v) if v > 0 else 1.0


class Prep:
    pass


def prepare(rows):
    f = feats(rows)
    n = len(rows)
    wmax = max(f["week"])
    w = []
    for i in range(n):
        rec = RECENCY ** (wmax - f["week"][i])
        vol = math.log1p(f["units"][i])
        w.append(max(WEIGHT_FLOOR, rec * vol))
    sw = sum(w)
    w = [wi * n / sw for wi in w]
    lim = {}
    cont = {}
    for c in ["log_price", "log_competitor_price", "log_traffic"]:
        lo = wpercentile(f[c], w, WINSOR[c][0])
        hi = wpercentile(f[c], w, WINSOR[c][1])
        lim[c] = (lo, hi)
        cont[c] = [min(max(v, lo), hi) for v in f[c]]
    cont["week_trend"] = list(f["week_trend"])
    mom = {}
    std = {}
    for c in CONT:
        m, s = wmean_wstd(cont[c], w)
        mom[c] = (m, s)
        std[c] = [(v - m) / s for v in cont[c]]
    p = Prep()
    p.f = f
    p.w = w
    p.lim = lim
    p.mom = mom
    p.std = std
    p.n = n
    return p


def design(p):
    f = p.f
    std = p.std
    cols = []
    names = []
    for s in SEGMENTS:
        cols.append([1.0 if seg == s else 0.0 for seg in f["segment"]])
        names.append("int_" + s)
    for s in SEGMENTS:
        pairs = zip(f["segment"], std["log_price"], strict=True)
        cols.append([(1.0 if seg == s else 0.0) * z for seg, z in pairs])
        names.append("slope_" + s)
    for c in COVARS:
        cols.append(list(std[c]) if c in CONT else list(f[c]))
        names.append(c)
    x = [[cols[j][i] for j in range(len(cols))] for i in range(p.n)]
    return x, names


def ridge_beta(x, y, w, lam, drop=()):
    p = len(x[0])
    a = [[0.0] * p for _ in range(p)]
    b = [0.0] * p
    for i in range(len(x)):
        wi = w[i]
        xi = x[i]
        for aa in range(p):
            xa = 0.0 if aa in drop else xi[aa]
            b[aa] += wi * xa * y[i]
            for c in range(aa, p):
                xc = 0.0 if c in drop else xi[c]
                a[aa][c] += wi * xa * xc
    for aa in range(p):
        for c in range(aa):
            a[aa][c] = a[c][aa]
    for aa in range(p):
        a[aa][aa] += lam
        if aa in drop:
            for c in range(p):
                a[aa][c] = 0.0
                a[c][aa] = 0.0
            a[aa][aa] = 1.0
            b[aa] = 0.0
    return solve(a, b)


def build_folds(week, n):
    uw = sorted(set(week))
    q, rem = divmod(len(uw), KFOLDS)
    blocks = []
    start = 0
    for i in range(KFOLDS):
        size = q + (1 if i < rem else 0)
        blocks.append(uw[start:start + size])
        start += size
    folds = []
    for block in blocks:
        val_w = set(block)
        lo = min(block)
        hi = max(block)
        emb = set()
        for e in range(1, EMBARGO + 1):
            emb.add(lo - e)
            emb.add(hi + e)
        tr = [j for j in range(n) if week[j] not in val_w and week[j] not in emb]
        val = [j for j in range(n) if week[j] in val_w]
        folds.append((tr, val))
    return folds


def cv_curve(x, y, w, week, lam_list):
    folds = build_folds(week, len(y))
    means = []
    ses = []
    for lam in lam_list:
        errs = []
        for tr, val in folds:
            xtr = [x[i] for i in tr]
            ytr = [y[i] for i in tr]
            wtr = [w[i] for i in tr]
            beta = ridge_beta(xtr, ytr, wtr, lam)
            num = 0.0
            den = 0.0
            for i in val:
                pred = sum(beta[j] * x[i][j] for j in range(len(beta)))
                num += w[i] * (pred - y[i]) ** 2
                den += w[i]
            errs.append(num / den)
        m = sum(errs) / KFOLDS
        var = sum((e - m) ** 2 for e in errs) / (KFOLDS - 1)
        means.append(m)
        ses.append(math.sqrt(var) / math.sqrt(KFOLDS))
    return means, ses


def select_lambda(means, ses, lam_list):
    j = min(range(len(means)), key=lambda i: means[i])
    thr = means[j] + ses[j]
    cand = [i for i in range(len(lam_list)) if means[i] <= thr]
    return max(cand)


def median(v):
    n = len(v)
    m = n // 2
    return v[m] if n % 2 else (v[m - 1] + v[m]) / 2.0


def q_at(price, intercept, slope, scale):
    mlp, slp, lo_lp, hi_lp = scale
    z = (min(max(math.log(price), lo_lp), hi_lp) - mlp) / slp
    return math.exp(intercept + slope * z) - OFFSET


def elasticity(train, beta, idx, scale, seg):
    seg_prices = sorted(r["price"] for r in train if r["segment"] == seg)
    pref = median(seg_prices)
    sl = beta[idx["slope_" + seg]]
    it = beta[idx["int_" + seg]]
    p1 = pref
    p2 = pref * (1 + ARC_STEP)
    q1 = q_at(p1, it, sl, scale)
    q2 = q_at(p2, it, sl, scale)
    return ((q2 - q1) / ((q1 + q2) / 2)) / ((p2 - p1) / ((p1 + p2) / 2))


def run(path):
    rows = read_panel(path)
    train = [r for r in rows if r["week"] < HOLDOUT_START]
    hold = [r for r in rows if r["week"] >= HOLDOUT_START]
    p = prepare(train)
    x, names = design(p)
    y = [math.log(u + OFFSET) for u in p.f["units"]]
    means, ses = cv_curve(x, y, p.w, p.f["week"], LAMBDA_GRID)
    lam = LAMBDA_GRID[select_lambda(means, ses, LAMBDA_GRID)]
    beta = ridge_beta(x, y, p.w, lam)
    idx = {nm: i for i, nm in enumerate(names)}
    drop = [idx["slope_" + s] for s in SEGMENTS if beta[idx["slope_" + s]] > 0]
    if drop:
        beta = ridge_beta(x, y, p.w, lam, drop=tuple(drop))
    out = {
        "lambda": lam,
        "coefficients": {},
        "cv_mean_error": {},
        "elasticities": {},
        "holdout_weighted_mape": 0.0,
    }
    for c in COVARS:
        out["coefficients"][c] = beta[idx[c]]
    for s in SEGMENTS:
        out["coefficients"]["intercept_" + s] = beta[idx["int_" + s]]
        out["coefficients"]["price_slope_" + s] = beta[idx["slope_" + s]]
    for i, lam_i in enumerate(LAMBDA_GRID):
        out["cv_mean_error"][fmt(lam_i)] = means[i]
    mlp, slp = p.mom["log_price"]
    lo_lp, hi_lp = p.lim["log_price"]
    scale = (mlp, slp, lo_lp, hi_lp)
    for s in SEGMENTS:
        out["elasticities"][s] = elasticity(train, beta, idx, scale, s)
    out["holdout_weighted_mape"] = holdout_mape(hold, p, beta, idx)
    return out


def holdout_mape(hold, p, beta, idx):
    fh = feats(hold)
    num = 0.0
    den = 0.0
    for i in range(len(hold)):
        vec = {}
        for c in ["log_price", "log_competitor_price", "log_traffic"]:
            lo, hi = p.lim[c]
            v = min(max(fh[c][i], lo), hi)
            m, s = p.mom[c]
            vec[c] = (v - m) / s
        m, s = p.mom["week_trend"]
        vec["week_trend"] = (fh["week_trend"][i] - m) / s
        seg = fh["segment"][i]
        pred = beta[idx["int_" + seg]] + beta[idx["slope_" + seg]] * vec["log_price"]
        for c in COVARS:
            xv = vec[c] if c in CONT else fh[c][i]
            pred += beta[idx[c]] * xv
        pu = math.exp(pred) - OFFSET
        actual = fh["units"][i]
        ape = abs(pu - actual) / max(actual, MAPE_FLOOR)
        num += actual * ape
        den += actual
    return num / den if den > 0 else 0.0


def fmt(x):
    return repr(float(x))


if __name__ == "__main__":
    import json
    import sys
    print(json.dumps(run(sys.argv[1]), indent=2))
