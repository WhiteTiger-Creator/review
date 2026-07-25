"""Verifier for lyapunov-exponents-matrix-cocycle.

The graded checks are unchanged; they are only reorganised so that each graded
problem is its own pytest case. The staging step (tests/test.sh) generates the
problems, builds and runs the program, and exports the artifact paths; this module
reads them and grades one problem per parametrized case across four families:
per-problem exponent accuracy, the determinant anchor, the metamorphic relations,
and the product-forming trap. The reward remains binary all-pass.
"""

import json
import math
import os

import pytest

ABS_TOL = 1e-8
BASELINE_MIN = 1e-5


def eye(n):
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def matmul(A, B):
    n = len(A)
    m = len(B[0])
    p = len(B)
    C = [[0.0] * m for _ in range(n)]
    for i in range(n):
        Ai = A[i]
        Ci = C[i]
        for t in range(p):
            a = Ai[t]
            Bt = B[t]
            for j in range(m):
                Ci[j] += a * Bt[j]
    return C


def fro_norm(A):
    return math.sqrt(sum(x * x for row in A for x in row))


def det(M):
    n = len(M)
    A = [row[:] for row in M]
    sign = 1.0
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(A[r][c]))
        if A[p][c] == 0.0:
            return 0.0
        if p != c:
            A[c], A[p] = A[p], A[c]
            sign = -sign
        for r in range(c + 1, n):
            f = A[r][c] / A[c][c]
            for cc in range(c, n):
                A[r][cc] -= f * A[c][cc]
    d = sign
    for i in range(n):
        d *= A[i][i]
    return d


def gram_schmidt_qr(A):
    n = len(A)
    cols = [[A[i][j] for i in range(n)] for j in range(n)]
    Q = [[0.0] * n for _ in range(n)]
    R = [[0.0] * n for _ in range(n)]
    for j in range(n):
        v = list(cols[j])
        for i in range(j):
            qi = [Q[r][i] for r in range(n)]
            dot = sum(qi[r] * cols[j][r] for r in range(n))
            R[i][j] = dot
            for r in range(n):
                v[r] -= dot * qi[r]
        nrm = math.sqrt(sum(x * x for x in v))
        R[j][j] = nrm
        for r in range(n):
            Q[r][j] = v[r] / nrm if nrm > 0 else 0.0
    return Q, R


def sym_eigvals(S):
    n = len(S)
    A = [row[:] for row in S]
    for _ in range(100):
        off = 0.0
        p, q = 0, 1
        for i in range(n):
            for j in range(i + 1, n):
                if abs(A[i][j]) > off:
                    off = abs(A[i][j])
                    p, q = i, j
        if off < 1e-300:
            break
        app, aqq, apq = A[p][p], A[q][q], A[p][q]
        if apq == 0.0:
            break
        tau = (aqq - app) / (2.0 * apq)
        t = (1.0 if tau >= 0 else -1.0) / (abs(tau) + math.sqrt(1.0 + tau * tau))
        c = 1.0 / math.sqrt(1.0 + t * t)
        s = t * c
        for k in range(n):
            akp = A[k][p]
            akq = A[k][q]
            A[k][p] = c * akp - s * akq
            A[k][q] = s * akp + c * akq
        for k in range(n):
            apk = A[p][k]
            aqk = A[q][k]
            A[p][k] = c * apk - s * aqk
            A[q][k] = s * apk + c * aqk
    return sorted((A[i][i] for i in range(n)), reverse=True)


def singular_values(P):
    n = len(P)
    Pt = [[P[j][i] for j in range(n)] for i in range(n)]
    G = matmul(Pt, P)
    ev = sym_eigvals(G)
    return [math.sqrt(x) if x > 0 else 0.0 for x in ev]


def parse_output(path):
    table = {}
    with open(path) as fh:
        for line in fh:
            parts = line.split()
            if not parts:
                continue
            try:
                table[parts[0]] = [float(v) for v in parts[1:]]
            except ValueError:
                table[parts[0]] = None
    return table


def read_problem(path):
    with open(path) as fh:
        toks = fh.read().split()
    n = int(toks[0])
    k = int(toks[1])
    vals = [float(t) for t in toks[2:]]
    A = []
    off = 0
    for _ in range(k):
        A.append([vals[off + i * n : off + (i + 1) * n] for i in range(n)])
        off += n * n
    return n, k, A


def _logs(vals, k):
    return sorted((math.log(v) / k if v > 0 else -1e300 for v in vals), reverse=True)


def baseline_form_svd(n, k, A):
    P = eye(n)
    for M in A:
        P = matmul(M, P)
    return _logs(singular_values(P), k)


def baseline_form_rescale_svd(n, k, A):
    P = eye(n)
    logscale = 0.0
    for M in A:
        P = matmul(M, P)
        nrm = fro_norm(P)
        if nrm > 0:
            P = [[x / nrm for x in row] for row in P]
            logscale += math.log(nrm)
    sv = singular_values(P)
    return sorted(
        ((math.log(v) + logscale) / k if v > 0 else -1e300 for v in sv), reverse=True
    )


def baseline_qr_diagonal(n, k, A):
    Q = eye(n)
    acc = [0.0] * n
    for M in A:
        B = matmul(M, Q)
        Qn, R = gram_schmidt_qr(B)
        for j in range(n):
            sgn = 1.0 if R[j][j] >= 0 else -1.0
            for i in range(n):
                Qn[i][j] *= sgn
            for c in range(n):
                R[j][c] *= sgn
        Q = Qn
        for j in range(n):
            acc[j] += math.log(abs(R[j][j])) if R[j][j] != 0 else -1e300
    return sorted((a / k for a in acc), reverse=True)


WORK = "/tmp/lyaptask"
OUT = os.environ.get("LYAP_OUT", os.path.join(WORK, "out.txt"))
REF = os.environ.get("LYAP_REF", os.path.join(WORK, "ref.json"))
IN_DIR = os.environ.get("LYAP_IN", os.path.join(WORK, "in"))

with open(REF) as _fh:
    _DATA = json.load(_fh)
ORDER = _DATA["order"]
REF_BY_NAME = _DATA["ref"]
GOT = parse_output(OUT)

META_NAMES = [name for name in ORDER if REF_BY_NAME[name]["meta"] is not None]
PLAIN_NAMES = [name for name in ORDER if REF_BY_NAME[name]["meta"] is None]

TRAP_ROUTES = {
    "form": baseline_form_svd,
    "rescale": baseline_form_rescale_svd,
    "qr_diagonal": baseline_qr_diagonal,
}


@pytest.mark.parametrize("name", ORDER)
def test_exponents_match_reference(name):
    """Every finite-horizon exponent for this problem matches the reference in order."""
    rec = REF_BY_NAME[name]
    n = rec["n"]
    truth = rec["lam"]
    u = GOT.get(name)
    assert u is not None and len(u) == n, f"{name} missing or wrong length"
    assert all(math.isfinite(v) for v in u), f"{name} non-finite"
    for i in range(n):
        assert abs(u[i] - truth[i]) <= ABS_TOL, (
            f"{name}[{i}] off by {abs(u[i] - truth[i]):.2e}"
        )


@pytest.mark.parametrize("name", ORDER)
def test_determinant_anchor(name):
    """The sum of exponents equals the mean log|det| anchor within n*ABS_TOL."""
    n = REF_BY_NAME[name]["n"]
    u = GOT.get(name)
    assert u is not None and len(u) == n, f"{name} missing or wrong length"
    _pn, pk, A = read_problem(os.path.join(IN_DIR, name))
    anchor = sum(math.log(abs(det(M))) for M in A) / pk
    dev = abs(sum(u) - anchor)
    assert dev <= n * ABS_TOL, f"{name} determinant anchor off by {dev:.2e}"


@pytest.mark.parametrize("name", META_NAMES)
def test_metamorphic_relation(name):
    """The scaling or negation relation to the base problem holds within 2*ABS_TOL."""
    kind, base_idx, c = REF_BY_NAME[name]["meta"]
    base_name = ORDER[base_idx]
    n = REF_BY_NAME[name]["n"]
    u = GOT.get(name)
    b = GOT.get(base_name)
    assert u and b and len(u) == n and len(b) == n, f"metamorphic {name} unusable"
    shift = 0.0 if kind == "negate" else math.log(abs(c))
    for i in range(n):
        assert abs(u[i] - (b[i] + shift)) <= 2 * ABS_TOL, (
            f"metamorphic {name} ({kind}) relation broken at {i}"
        )


@pytest.mark.parametrize("name", PLAIN_NAMES)
def test_trap_routes_fail(name):
    """Each naive product-forming route misses this problem by more than BASELINE_MIN."""
    n, k, A = read_problem(os.path.join(IN_DIR, name))
    truth = REF_BY_NAME[name]["lam"]
    for label, fn in TRAP_ROUTES.items():
        est = fn(n, k, A)
        e = max(abs(est[i] - truth[i]) for i in range(n))
        assert (not math.isfinite(e)) or e > BASELINE_MIN, (
            f"{name} solvable by the {label} route (err={e:.2e})"
        )
