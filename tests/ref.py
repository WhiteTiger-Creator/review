"""Exact-arithmetic polynomial helpers shared by the census engine.

Rational (Fraction) dense multivariate and univariate operations, univariate
resultants over Q, rational-root recovery, and Sturm-sequence real-root
counting. Used by census.py; kept as a separate module so the engine and its
low-level algebra live apart."""

from fractions import Fraction as Fr
from math import gcd

_MIN_PRIME_CANDIDATE = 2


# ---------- polynomial helpers over Q, dense in given variable count ----------
def padd(a, b):
    r = dict(a)
    for k, v in b.items():
        r[k] = r.get(k, Fr(0)) + v
        if r[k] == 0:
            del r[k]
    return r


def pmul(a, b):
    r = {}
    for ka, va in a.items():
        for kb, vb in b.items():
            k = tuple(x + y for x, y in zip(ka, kb, strict=False))
            r[k] = r.get(k, Fr(0)) + va * vb
    return {k: v for k, v in r.items() if v != 0}


def pscale(a, s):
    s = Fr(s)
    if s == 0:
        return {}
    return {k: v * s for k, v in a.items()}


# ---------- univariate (list of Fraction, index=power) exact ops ----------
def u_trim(p):
    while len(p) > 1 and p[-1] == 0:
        p.pop()
    return p


def u_mul(a, b):
    r = [Fr(0)] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        if x == 0:
            continue
        for j, y in enumerate(b):
            r[i + j] += x * y
    return u_trim(r)


def u_sub(a, b):
    n = max(len(a), len(b))
    r = [Fr(0)] * n
    for i, x in enumerate(a):
        r[i] += x
    for i, x in enumerate(b):
        r[i] -= x
    return u_trim(r)


def u_deg(p):
    p = u_trim(p[:])
    return len(p) - 1 if any(c != 0 for c in p) else -1


def u_divmod(a, b):
    a = u_trim(a[:])
    b = u_trim(b[:])
    db = u_deg(b)
    q = [Fr(0)] * max(1, len(a) - db + 1) if u_deg(a) >= db else [Fr(0)]
    r = a[:]
    while u_deg(r) >= db and u_deg(r) >= 0:
        dr = u_deg(r)
        c = r[dr] / b[db]
        s = dr - db
        q[s] = c
        for i in range(db + 1):
            r[i + s] -= c * b[i]
        r = u_trim(r)
    return u_trim(q), u_trim(r)


def u_gcd(a, b):
    a = u_trim(a[:])
    b = u_trim(b[:])
    while u_deg(b) >= 0:
        _, r = u_divmod(a, b)
        a, b = b, r
    if u_deg(a) < 0:
        return [Fr(0)]
    lead = a[u_deg(a)]
    return u_trim([c / lead for c in a])


def resultant_y(P, Q):
    """Res_y of two bivariate polys P,Q (dicts over (x,y)) as a univariate poly
    in x (list of Fraction). Sylvester determinant with entries polynomials in x."""

    # collect as lists of coefficients in y, each coeff a univariate poly in x
    def as_y(poly):
        dy = max((k[1] for k in poly), default=0)
        cols = [[Fr(0)] for _ in range(dy + 1)]
        for (ix, iy), v in poly.items():
            c = cols[iy]
            if len(c) <= ix:
                c += [Fr(0)] * (ix + 1 - len(c))
            c[ix] += v
        return [u_trim(c) for c in cols]  # index = power of y

    A = as_y(P)
    B = as_y(Q)
    da = len(A) - 1
    db = len(B) - 1
    n = da + db
    if n == 0:
        return [Fr(1)]
    # Sylvester matrix of size n x n, entries are univariate polys in x
    M = [[[Fr(0)] for _ in range(n)] for _ in range(n)]
    for r in range(db):
        for j in range(da + 1):
            M[r][r + j] = A[da - j][:]
    for r in range(da):
        for j in range(db + 1):
            M[db + r][r + j] = B[db - j][:]
    return _poly_matrix_det(M)


def _poly_matrix_det(M):
    """Determinant of a matrix whose entries are univariate polys (lists), via
    fraction-free-ish expansion using exact poly arithmetic (Bareiss on polys)."""
    n = len(M)
    M = [[row[:] for row in r] for r in M]
    sign = 1
    prev = [Fr(1)]
    for k in range(n - 1):
        if u_deg(M[k][k]) < 0:
            sw = next((i for i in range(k + 1, n) if u_deg(M[i][k]) >= 0), None)
            if sw is None:
                return [Fr(0)]
            M[k], M[sw] = M[sw], M[k]
            sign = -sign
        for i in range(k + 1, n):
            for j in range(k + 1, n):
                num = u_sub(u_mul(M[k][k], M[i][j]), u_mul(M[i][k], M[k][j]))
                q, rem = u_divmod(num, prev)
                assert u_deg(rem) < 0, "non-exact Bareiss division"
                M[i][j] = q
            M[i][k] = [Fr(0)]
        prev = M[k][k]
    res = M[n - 1][n - 1]
    return u_trim([c * sign for c in res])


def _is_prime(n):
    if n < _MIN_PRIME_CANDIDATE:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False
    return True


def _pollard(n):
    if n % 2 == 0:
        return 2
    for c in range(1, 40):
        x = y = 2
        dd = 1
        while dd == 1:
            x = (x * x + c) % n
            y = (y * y + c) % n
            y = (y * y + c) % n
            dd = gcd(abs(x - y), n)
        if dd != n:
            return dd
    return n


def _factor(n, acc):
    if n == 1:
        return
    if _is_prime(n):
        acc[n] = acc.get(n, 0) + 1
        return
    f = _pollard(n)
    _factor(f, acc)
    _factor(n // f, acc)


def _divisors(m):
    m = abs(m)
    if m == 0:
        return {0}
    fac = {}
    _factor(m, fac)
    ds = {1}
    for pr, e in fac.items():
        ds = {d * pr**k for d in ds for k in range(e + 1)}
    return ds


def rational_roots(poly_int):
    """All rational roots of a univariate integer/fraction poly (list, idx=power)."""
    p = u_trim([Fr(c) for c in poly_int])
    if u_deg(p) < 0:
        return None  # identically zero
    # clear denominators
    dens = [c.denominator for c in p]
    L = 1
    for dd in dens:
        L = L * dd // gcd(L, dd)
    ip = [int(c * L) for c in p]
    ip = ip[:]
    # strip leading zeros
    while len(ip) > 1 and ip[-1] == 0:
        ip.pop()
    # factor out x=0 roots
    roots = set()
    while len(ip) > 1 and ip[0] == 0:
        roots.add(Fr(0))
        ip = ip[1:]
    if len(ip) == 1:
        return roots
    a0 = abs(ip[0])
    an = abs(ip[-1])

    for pnum in _divisors(a0):
        for qden in _divisors(an):
            for s in (1, -1):
                r = Fr(s * pnum, qden)
                val = Fr(0)
                pw = Fr(1)
                for c in ip:
                    val += c * pw
                    pw *= r
                if val == 0:
                    roots.add(r)
    return roots


# ---------- exact real-root counting over R via Sturm sequences ----------
def u_derivative(p):
    p = u_trim([Fr(c) for c in p])
    if u_deg(p) <= 0:
        return [Fr(0)]
    return u_trim([p[i] * i for i in range(1, len(p))])


def sturm_chain(p):
    """Standard Sturm sequence p0=p, p1=p', p_{i+1} = -rem(p_{i-1}, p_i).
    Returns None for the identically zero polynomial."""
    p0 = u_trim([Fr(c) for c in p])
    if u_deg(p0) < 0:
        return None
    chain = [p0, u_derivative(p0)]
    while u_deg(chain[-1]) >= 0:
        _, rem = u_divmod(chain[-2], chain[-1])
        if u_deg(rem) < 0:
            break
        chain.append(u_trim([-c for c in rem]))
    return chain


def _leading_signs(chain, at_pos_inf):
    """Sign of each chain member as its argument tends to +inf or -inf."""
    signs = []
    for poly in chain:
        d = u_deg(poly)
        if d < 0:
            signs.append(0)
            continue
        lead = poly[d]
        s = 1 if lead > 0 else -1
        if not at_pos_inf and d % 2 == 1:
            s = -s
        signs.append(s)
    return signs


def _sign_variations(signs):
    v = 0
    prev = 0
    for s in signs:
        if s == 0:
            continue
        if prev != 0 and s != prev:
            v += 1
        prev = s
    return v


def real_roots_count(p):
    """Number of DISTINCT real roots of a univariate poly over all of R.
    Returns None for the identically zero polynomial."""
    chain = sturm_chain(p)
    if chain is None:
        return None
    v_neg = _sign_variations(_leading_signs(chain, at_pos_inf=False))
    v_pos = _sign_variations(_leading_signs(chain, at_pos_inf=True))
    return v_neg - v_pos
