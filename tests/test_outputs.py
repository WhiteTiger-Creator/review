"""Verifier for TrustLoom TL-ALS-CONF-1 (nested folds / local R* / sign canon)."""

from __future__ import annotations

import csv
import json
import math
import subprocess
from pathlib import Path

ROOT = Path("/opt/trustloom")
BIN = ROOT / "bin" / "trustloom"
INTERACTIONS = Path("/app/data/interactions.csv")
QUERIES = Path("/app/data/queries.csv")
HOLDOUT = Path("/app/data/holdout.csv")
OUT = Path("/var/lib/trustloom")
MODEL = OUT / "model.json"
SCORES = OUT / "scores.json"
METRICS = OUT / "metrics.json"
DIAG = OUT / "diagnostics.json"
FOLDS = OUT / "folds.json"
BUILD_PATH = Path("/app/remediation/build-path.txt")

F, LAMBDA, ALPHA, ITERS, INIT_SCALE, K = 4, 0.15, 25.0, 8, 0.02, 3
FADE, MID, FK, GAMMA, JITTER = 0.994, 4, 4, 5.0, 1e-8
FNV_OFFSET, FNV_PRIME = 14695981039346656037, 1099511628211
ABS_TOL, MET_TOL = 1e-9, 1e-12


def _fnv1a64(data: bytes) -> int:
    h = FNV_OFFSET
    for b in data:
        h ^= b
        h = (h * FNV_PRIME) & 0xFFFFFFFFFFFFFFFF
    return h


def _unit_hash(kind: str, id_: int, f: int) -> float:
    h = _fnv1a64(f"{kind}|{id_}|{f}".encode("ascii"))
    return ((h % 1000003) / 1000003.0) * 2.0 - 1.0


def _load_pairs(path: Path):
    with open(path) as fh:
        rows = list(csv.DictReader(fh))
    totals_u, totals_i = {}, {}
    raw = []
    for row in rows:
        u, i, c = int(row["user_id"]), int(row["item_id"]), int(row["count"])
        totals_u[u] = totals_u.get(u, 0) + c
        totals_i[i] = totals_i.get(i, 0) + c
        raw.append((u, i, c))
    keep_u = {u for u, t in totals_u.items() if t >= 2}
    keep_i = {i for i, t in totals_i.items() if t >= 2}
    pairs = {}
    for u, i, c in raw:
        if u in keep_u and i in keep_i:
            pairs[(u, i)] = pairs.get((u, i), 0) + c
    return pairs


def _remass(pairs):
    totals_u, totals_i = {}, {}
    for (u, i), c in pairs.items():
        totals_u[u] = totals_u.get(u, 0) + c
        totals_i[i] = totals_i.get(i, 0) + c
    keep_u = {u for u, t in totals_u.items() if t >= 2}
    keep_i = {i for i, t in totals_i.items() if t >= 2}
    return {(u, i): c for (u, i), c in pairs.items() if u in keep_u and i in keep_i}


def _catalog(pairs):
    users = sorted({u for u, _ in pairs})
    items = sorted({i for _, i in pairs})
    u_index = {u: idx for idx, u in enumerate(users)}
    i_index = {i: idx for idx, i in enumerate(items)}
    user_obs = {ui: [] for ui in range(len(users))}
    item_obs = {ii: [] for ii in range(len(items))}
    for (u, i), r in pairs.items():
        user_obs[u_index[u]].append((i_index[i], r))
        item_obs[i_index[i]].append((u_index[u], r))
    r_star = max(pairs.values()) if pairs else 1
    return users, items, user_obs, item_obs, u_index, i_index, r_star, len(pairs)


def _eye(n):
    return [[1.0 if a == b else 0.0 for b in range(n)] for a in range(n)]


def _add(a, b):
    n = len(a)
    return [[a[i][j] + b[i][j] for j in range(n)] for i in range(n)]


def _scale(a, s):
    n = len(a)
    return [[a[i][j] * s for j in range(n)] for i in range(n)]


def _outer(v):
    n = len(v)
    return [[v[i] * v[j] for j in range(n)] for i in range(n)]


def _gram(M):
    f = len(M[0])
    g = [[0.0] * f for _ in range(f)]
    for row in M:
        for a in range(f):
            for b in range(f):
                g[a][b] += row[a] * row[b]
    return g


def _chol_solve(A, b):
    n = len(b)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                L[i][j] = math.sqrt(max(A[i][i] - s, 0.0))
            else:
                L[i][j] = (A[i][j] - s) / L[j][j]
    y = [0.0] * n
    for i in range(n):
        y[i] = (b[i] - sum(L[i][k] * y[k] for k in range(i))) / L[i][i]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (y[i] - sum(L[k][i] * x[k] for k in range(i + 1, n))) / L[i][i]
    return x


def _normalize(M):
    out = []
    for row in M:
        nrm = math.sqrt(sum(v * v for v in row))
        out.append(list(row) if nrm == 0 else [v / nrm for v in row])
    return out


def _sign_canon(M):
    out = []
    for row in M:
        if row and row[0] < 0:
            out.append([-v for v in row])
        else:
            out.append(list(row))
    return out


def _polarity_align(X, Y):
    s = sum(row[0] for row in X if row)
    if s >= 0:
        return X, Y
    return [[-v for v in row] for row in X], [[-v for v in row] for row in Y]


def _add_jitter(A, lt):
    j = JITTER * lt
    n = len(A)
    out = [row[:] for row in A]
    for f in range(n):
        out[f][f] += j
    return out


def _fade(M):
    return [[v * FADE for v in row] for row in M]


def _local_max(obs):
    return max((r for _, r in obs), default=1)


def _conf(r, r_local):
    return 1.0 + ALPHA * math.log1p(r) / math.log1p(r_local)


def _fit(users, items, user_obs, item_obs):
    u_n, i_n = len(users), len(items)
    X = [[INIT_SCALE * _unit_hash("user", users[u], f) for f in range(F)] for u in range(u_n)]
    Y = [[INIT_SCALE * _unit_hash("item", items[i], f) for f in range(F)] for i in range(i_n)]
    schedule = []
    for t in range(1, ITERS + 1):
        lt = LAMBDA if t <= MID else 2 * LAMBDA
        schedule.append(lt)
        do_fade = lt == LAMBDA
        xtx = _gram(X)
        new_y = []
        for i in range(i_n):
            n_i = len(item_obs[i])
            r_i = _local_max(item_obs[i])
            A = _add(xtx, _scale(_eye(F), lt * n_i))
            b = [0.0] * F
            for ui, r in item_obs[i]:
                c = _conf(r, r_i)
                A = _add(A, _scale(_outer(X[ui]), c - 1.0))
                for f in range(F):
                    b[f] += c * X[ui][f]
            new_y.append(_chol_solve(_add_jitter(A, lt), b))
        Y = _fade(new_y) if do_fade else new_y
        yty = _gram(Y)
        new_x = []
        for u in range(u_n):
            n_u = len(user_obs[u])
            r_u = _local_max(user_obs[u])
            A = _add(yty, _scale(_eye(F), lt * n_u))
            b = [0.0] * F
            for ii, r in user_obs[u]:
                c = _conf(r, r_u)
                A = _add(A, _scale(_outer(Y[ii]), c - 1.0))
                for f in range(F):
                    b[f] += c * Y[ii][f]
            new_x.append(_chol_solve(_add_jitter(A, lt), b))
        X = _fade(new_x) if do_fade else new_x
    xn, yn = _normalize(X), _normalize(Y)
    xn, yn = _polarity_align(xn, yn)
    return _sign_canon(xn), _sign_canon(yn), schedule


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _score(X, Y, user_obs, item_obs, u_index, i_index, uid, iid):
    if uid not in u_index or iid not in i_index:
        return 0.0
    ui, ii = u_index[uid], i_index[iid]
    raw = _dot(X[ui], Y[ii])
    n_u = len(user_obs[ui])
    n_i = len(item_obs[ii])
    return raw * math.sqrt((n_u + n_i) / (n_u + n_i + GAMMA))


def _ap_macro(X, Y, user_obs, item_obs, users, items, u_index, i_index, relevant_by_user):
    aps = []
    for u in sorted(relevant_by_user):
        if u not in u_index:
            continue
        R = {i for i in relevant_by_user[u] if i in i_index}
        if not R:
            continue
        scored = [(iid, _score(X, Y, user_obs, item_obs, u_index, i_index, u, iid)) for iid in items]
        scored.sort(key=lambda t: (-t[1], t[0]))
        top = [iid for iid, _ in scored[:K]]
        hit_count = 0
        ap_sum = 0.0
        for rank, iid in enumerate(top, start=1):
            if iid in R:
                hit_count += 1
                ap_sum += hit_count / rank
        denom = min(K, len(R))
        aps.append(ap_sum / denom if hit_count else 0.0)
    if not aps:
        return 0.0, 0
    return sum(aps) / len(aps), len(aps)


def _holdout_metrics(X, Y, user_obs, item_obs, users, items, u_index, i_index, holdout_path: Path):
    by_user = {}
    with open(holdout_path) as fh:
        for row in csv.DictReader(fh):
            u, i, lab = int(row["user_id"]), int(row["item_id"]), int(row["label"])
            by_user.setdefault(u, []).append((i, lab))
    precs, aps, ndcgs = [], [], []
    for u in sorted(by_user):
        if u not in u_index:
            continue
        R = {i for i, lab in by_user[u] if lab == 1 and i in i_index}
        if not R:
            continue
        scored = [(iid, _score(X, Y, user_obs, item_obs, u_index, i_index, u, iid)) for iid in items]
        scored.sort(key=lambda t: (-t[1], t[0]))
        top = [iid for iid, _ in scored[:K]]
        hits = sum(1 for iid in top if iid in R)
        precs.append(hits / K)
        hit_count = 0
        ap_sum = 0.0
        dcg = 0.0
        for rank, iid in enumerate(top, start=1):
            if iid in R:
                hit_count += 1
                ap_sum += hit_count / rank
                dcg += 1.0 / math.log2(rank + 1)
        denom = min(K, len(R))
        aps.append(ap_sum / denom if hit_count else 0.0)
        ideal = min(K, len(R))
        idcg = sum(1.0 / math.log2(r + 1) for r in range(1, ideal + 1))
        ndcgs.append(dcg / idcg if idcg else 0.0)
    n = len(precs)
    if not n:
        return 0.0, 0.0, 0.0, 0
    return sum(precs) / n, sum(aps) / n, sum(ndcgs) / n, n


def _folds(global_pairs):
    _users, _items, _uo, _io, u_index, i_index, _rs, _np = _catalog(global_pairs)
    out = []
    for f in range(FK):
        train, hold = {}, {}
        for (u, i), c in global_pairs.items():
            bucket = (2 * u_index[u] + 3 * i_index[i]) % FK
            (hold if bucket == f else train)[(u, i)] = c
        train = _remass(train)
        tu, ti, uo, io, uix, iix, _rs2, npairs = _catalog(train)
        X, Y, _sched = _fit(tu, ti, uo, io)
        rel = {}
        for (u, i) in hold:
            if u in uix and i in iix:
                rel.setdefault(u, set()).add(i)
        m, e = _ap_macro(X, Y, uo, io, tu, ti, uix, iix, rel)
        out.append(
            {
                "fold_index": f,
                "n_train_users": len(tu),
                "n_train_items": len(ti),
                "n_train_pairs": npairs,
                "eligible_users": e,
                "map_at_k": m,
            }
        )
    return out


def _expected():
    pairs = _load_pairs(INTERACTIONS)
    users, items, user_obs, item_obs, u_index, i_index, r_star, n_pairs = _catalog(pairs)
    X, Y, schedule = _fit(users, items, user_obs, item_obs)
    with open(QUERIES) as fh:
        queries = [(int(r["user_id"]), int(r["item_id"])) for r in csv.DictReader(fh)]
    scores = [_score(X, Y, user_obs, item_obs, u_index, i_index, u, i) for u, i in queries]
    p, m, n, e = _holdout_metrics(X, Y, user_obs, item_obs, users, items, u_index, i_index, HOLDOUT)
    mean_abs = sum(abs(_dot(X[u], Y[i])) for u in range(len(users)) for i in range(len(items)))
    mean_abs /= max(len(users) * len(items), 1)
    return users, items, X, Y, queries, scores, p, m, n, e, r_star, n_pairs, schedule, mean_abs, _folds(pairs)


def _no_active_labals(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or stripped == "":
            continue
        assert "labals" not in stripped, f"{path} still forces labals: {stripped}"


def _rebuild():
    result = subprocess.run(["make", "clean", "all"], cwd=str(ROOT), capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"make failed:\n{result.stdout}{result.stderr}"
    assert BIN.exists()


def _run_fit(interactions=INTERACTIONS, queries=QUERIES, holdout=HOLDOUT, out=OUT):
    if out.exists():
        for child in out.iterdir():
            if child.is_file():
                child.unlink()
    out.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [str(BIN), "--interactions", str(interactions), "--queries", str(queries), "--holdout", str(holdout), "--out", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_close(a, b, tol, label):
    assert abs(float(a) - float(b)) <= tol, f"{label}: got {a}, expected {b}"


def _helpers_disabled() -> None:
    makefile = (ROOT / "Makefile").read_text() if (ROOT / "Makefile").exists() else ""
    for name in ("tl-coerce.sh", "tl-handbook-sync.sh"):
        path = ROOT / "scripts" / name
        if not path.exists():
            continue
        for line in makefile.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped == "":
                continue
            assert name not in stripped, (
                f"active Makefile line still invokes {name}: {stripped}"
            )


def test_packaging_and_rebuild():
    _no_active_labals(ROOT / "staging.mk")
    _no_active_labals(ROOT / ".cutover.mk")
    _helpers_disabled()
    assert BUILD_PATH.read_bytes() == b"default:!labals\n"
    _rebuild()
    assert BIN.read_bytes()[:4] == b"\x7fELF"
    result = _run_fit()
    assert result.returncode == 0, result.stderr
    assert MODEL.exists() and SCORES.exists() and METRICS.exists() and DIAG.exists() and FOLDS.exists()


def test_model_schema_and_factors():
    _rebuild()
    _run_fit()
    users, items, X, Y = _expected()[:4]
    doc = json.loads(MODEL.read_text())
    assert doc["algorithm"] == "tl-als-conf-1"
    assert [u["id"] for u in doc["users"]] == users
    assert [i["id"] for i in doc["items"]] == items
    for idx, u in enumerate(doc["users"]):
        for f in range(F):
            _assert_close(u["factors"][f], X[idx][f], ABS_TOL, f"user {u['id']} f{f}")
        assert u["factors"][0] >= 0.0 or all(abs(v) < ABS_TOL for v in u["factors"])
        nrm = math.sqrt(sum(v * v for v in u["factors"]))
        _assert_close(nrm, 1.0, ABS_TOL, f"user {u['id']} norm")
    for idx, it in enumerate(doc["items"]):
        for f in range(F):
            _assert_close(it["factors"][f], Y[idx][f], ABS_TOL, f"item {it['id']} f{f}")
        assert it["factors"][0] >= 0.0 or all(abs(v) < ABS_TOL for v in it["factors"])


def test_scores_match_expected():
    _rebuild()
    _run_fit()
    exp = _expected()
    queries, scores = exp[4], exp[5]
    doc = json.loads(SCORES.read_text())
    for got, (uid, iid), want in zip(doc["scores"], queries, scores):
        assert got["user_id"] == uid and got["item_id"] == iid
        _assert_close(got["score"], want, ABS_TOL, f"score {uid},{iid}")


def test_metrics_match_expected():
    _rebuild()
    _run_fit()
    exp = _expected()
    p, m, n, e = exp[6], exp[7], exp[8], exp[9]
    doc = json.loads(METRICS.read_text())
    assert doc["k"] == K
    assert doc["eligible_users"] == e
    _assert_close(doc["precision_at_k"], p, MET_TOL, "precision")
    _assert_close(doc["map_at_k"], m, MET_TOL, "map")
    _assert_close(doc["ndcg_at_k"], n, MET_TOL, "ndcg")


def test_diagnostics_match_expected():
    _rebuild()
    _run_fit()
    exp = _expected()
    users, items = exp[0], exp[1]
    r_star, n_pairs, schedule, mean_abs = exp[10], exp[11], exp[12], exp[13]
    doc = json.loads(DIAG.read_text())
    assert doc["r_star"] == r_star
    assert doc["n_users"] == len(users)
    assert doc["n_items"] == len(items)
    assert doc["n_pairs"] == n_pairs
    _assert_close(doc["fade"], FADE, ABS_TOL, "fade")
    assert doc["lambda_schedule"] == schedule
    _assert_close(doc["mean_abs_score"], mean_abs, ABS_TOL, "mean_abs_score")


def test_folds_match_expected():
    _rebuild()
    _run_fit()
    fold_exp = _expected()[14]
    doc = json.loads(FOLDS.read_text())
    assert doc["k"] == FK
    assert len(doc["folds"]) == FK
    for got, want in zip(doc["folds"], fold_exp):
        assert got["fold_index"] == want["fold_index"]
        assert got["n_train_users"] == want["n_train_users"]
        assert got["n_train_items"] == want["n_train_items"]
        assert got["n_train_pairs"] == want["n_train_pairs"]
        assert got["eligible_users"] == want["eligible_users"]
        _assert_close(got["map_at_k"], want["map_at_k"], MET_TOL, f"fold {want['fold_index']} map")


def test_catalog_excludes_low_mass_ids():
    _rebuild()
    _run_fit()
    doc = json.loads(MODEL.read_text())
    user_ids = {u["id"] for u in doc["users"]}
    item_ids = {i["id"] for i in doc["items"]}
    assert 99 not in user_ids and 999 not in item_ids and 70 not in user_ids


def test_cold_start_scores_are_zero():
    _rebuild()
    _run_fit()
    by_pair = {(s["user_id"], s["item_id"]): s["score"] for s in json.loads(SCORES.read_text())["scores"]}
    _assert_close(by_pair[(99, 100)], 0.0, ABS_TOL, "user 99 cold")
    _assert_close(by_pair[(10, 999)], 0.0, ABS_TOL, "item 999 cold")
    _assert_close(by_pair[(70, 200)], 0.0, ABS_TOL, "user 70 cold")


def test_agent_tree_has_no_verifier_assets():
    assert not (ROOT / "tests").exists()
    for path in ROOT.rglob("*"):
        if path.is_file():
            assert "test_outputs" not in path.name


def test_alternate_interactions_recompute():
    _rebuild()
    alt = Path("/tmp/alt_interactions.csv")
    alt.write_text(
        "user_id,item_id,count\n"
        "1,10,3\n1,20,2\n2,10,4\n2,20,1\n2,30,3\n3,20,2\n3,30,5\n3,10,1\n"
        "4,10,2\n4,30,2\n1,30,1\n"
    )
    alt_q = Path("/tmp/alt_queries.csv")
    alt_q.write_text("user_id,item_id\n1,10\n2,30\n3,20\n9,10\n")
    alt_h = Path("/tmp/alt_holdout.csv")
    alt_h.write_text("user_id,item_id,label\n1,10,1\n1,30,0\n2,20,1\n2,30,1\n3,10,0\n3,30,1\n4,10,1\n")
    alt_out = Path("/tmp/alt_out")
    assert _run_fit(alt, alt_q, alt_h, alt_out).returncode == 0

    pairs = _load_pairs(alt)
    users, items, user_obs, item_obs, u_index, i_index, _r_star, _n_pairs = _catalog(pairs)
    X, Y, _schedule = _fit(users, items, user_obs, item_obs)
    queries = [(1, 10), (2, 30), (3, 20), (9, 10)]
    exp_scores = [_score(X, Y, user_obs, item_obs, u_index, i_index, u, i) for u, i in queries]
    p, m, _n, e = _holdout_metrics(X, Y, user_obs, item_obs, users, items, u_index, i_index, alt_h)
    fold_exp = _folds(pairs)

    got_scores = json.loads((alt_out / "scores.json").read_text())["scores"]
    for got, exp, (uid, iid) in zip(got_scores, exp_scores, queries):
        _assert_close(got["score"], exp, ABS_TOL, f"alt score {uid},{iid}")
    met = json.loads((alt_out / "metrics.json").read_text())
    _assert_close(met["precision_at_k"], p, MET_TOL, "alt precision")
    _assert_close(met["map_at_k"], m, MET_TOL, "alt map")
    assert met["eligible_users"] == e
    folds_doc = json.loads((alt_out / "folds.json").read_text())
    for got, exp in zip(folds_doc["folds"], fold_exp):
        assert got["n_train_pairs"] == exp["n_train_pairs"]
        _assert_close(got["map_at_k"], exp["map_at_k"], MET_TOL, "alt fold map")

    _run_fit()
    bundled = json.loads(SCORES.read_text())["scores"]
    assert got_scores[0]["score"] != bundled[0]["score"] or got_scores[1]["score"] != bundled[1]["score"]
