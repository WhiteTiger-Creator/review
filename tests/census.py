"""Exact projective plane-curve census engine (verifier oracle)."""

from fractions import Fraction as Fr
from math import comb

from ref import (
    padd,
    pmul,
    pscale,
    rational_roots,
    real_roots_count,
    resultant_y,
    u_deg,
    u_divmod,
    u_gcd,
    u_trim,
)

_NODE_MULTIPLICITY = 2
_CUSP_INTERSECTION_MULT = 3
_VALID_DEGREES = (3, 4)


def degree(F):
    return max(sum(k) for k in F)


def is_homogeneous(F, d):
    return all(sum(k) == d for k in F)


def partial(F, var):
    r = {}
    for k, v in F.items():
        e = k[var]
        if e == 0:
            continue
        nk = list(k)
        nk[var] -= 1
        nk = tuple(nk)
        r[nk] = r.get(nk, Fr(0)) + v * e
    return {k: v for k, v in r.items() if v != 0}


def dehomogenize(F, keep):
    """Set the variable NOT in keep=(a,b) to 1; return bivariate dict over the
    two kept axes in order."""
    fixed = ({0, 1, 2} - set(keep)).pop()
    g = {}
    for k, v in F.items():
        if fixed == 0:
            nk = (k[1], k[2])
        elif fixed == 1:
            nk = (k[0], k[2])
        else:
            nk = (k[0], k[1])
        g[nk] = g.get(nk, Fr(0)) + v
    return {k: v for k, v in g.items() if v != 0}


def bshift(g, a, b):
    """g(u+a, v+b) via binomial expansion, exact."""
    r = {}
    for (i, j), c in g.items():
        for s in range(i + 1):
            for t in range(j + 1):
                coef = c * comb(i, s) * comb(j, t) * (a ** (i - s)) * (b ** (j - t))
                if coef:
                    r[(s, t)] = r.get((s, t), Fr(0)) + coef
    return {k: v for k, v in r.items() if v != 0}


def beval(g, u, v):
    return sum(c * (u**i) * (v**j) for (i, j), c in g.items())


def multiplicity(g0):
    return min(i + j for (i, j) in g0) if g0 else 10**9


def line_int_mult(g0, tangent_dir):
    """Intersection multiplicity at origin of curve g0 with the line through the
    origin in direction (du,dv): smallest t exponent of g0(t*du, t*dv)."""
    du, dv = tangent_dir
    poly = {}
    for (i, j), c in g0.items():
        e = i + j
        poly[e] = poly.get(e, Fr(0)) + c * (du**i) * (dv**j)
    poly = {e: c for e, c in poly.items() if c != 0}
    return min(poly) if poly else 10**9


def classify_sing(g0):
    """Classify the origin of the shifted curve g0. Returns a (kind, crunode)
    pair: kind in 'node' / 'cusp' / 'bad', and crunode True only when kind is
    'node' and the tangent-cone discriminant B^2 - 4AC is strictly positive, i.e.
    the two branch tangents are real and distinct (a crunode as opposed to an
    acnode with a conjugate pair of tangents)."""
    mu = multiplicity(g0)
    if mu != _NODE_MULTIPLICITY:
        return "bad", False  # mult>=3 (or smooth, filtered earlier)
    # degree-2 tangent cone A u^2 + B uv + C v^2
    A = g0.get((2, 0), Fr(0))
    B = g0.get((1, 1), Fr(0))
    C = g0.get((0, 2), Fr(0))
    disc = B * B - 4 * A * C
    if disc != 0:
        return "node", disc > 0  # two distinct tangents: ordinary node
    # double tangent line: A u^2 + B uv + C v^2 = (p u + q v)^2 up to scale
    if A != 0:
        p, q = A, B / 2
    elif C != 0:
        p, q = B / 2, C
    else:
        return "bad", False  # tangent cone identically... shouldn't happen at mult 2
    # tangent direction is (q, -p) (kernel of (p u + q v))
    du, dv = q, -p
    im = line_int_mult(g0, (du, dv))
    if im == _CUSP_INTERSECTION_MULT:
        return "cusp", False  # A2 ordinary cusp
    return "bad", False  # A3 tacnode or higher along the tangent


def singular_points(F, d):
    """Return dict proj-point -> type, over the three affine charts, deduped.
    proj-point normalized so first nonzero coord is 1 (rational points only).
    Also returns the count of NON-RATIONAL singular u-roots seen (for ERROR)."""
    found = {}
    nonrational = 0

    charts = [(1, 2, 0), (0, 2, 1), (0, 1, 2)]  # (axisU, axisV, fixed=1)
    for au, av, fx in charts:
        g = dehomogenize(F, (au, av))
        du_g = _dpartial(g, 0)
        dv_g = _dpartial(g, 1)
        R = resultant_y(du_g, dv_g)  # univariate in u (axis au)
        roots = rational_roots(R)
        if roots is None:
            # gu,gv share a component -> non-isolated singular locus
            return None, -1
        # detect non-rational singular candidates: compare rational-root count to
        # deg of squarefree part is hard; instead, count real solving below and
        # flag via a coarse check later. Here we gather rational singular points.
        for u0 in roots:
            # Gather rational v-candidates from the first fiber poly that is not
            # identically zero (dv_g, then du_g, then g). One partial can vanish
            # identically along u=u0, so we must not skip that case.
            vroots = None
            for src in (dv_g, du_g, g):
                cand = rational_roots(_subst_u(src, u0))
                if cand is not None:
                    vroots = cand
                    break
            if vroots is None:
                continue
            for v0 in vroots:
                if beval(du_g, u0, v0) != 0:
                    continue
                if beval(dv_g, u0, v0) != 0:
                    continue
                if beval(g, u0, v0) != 0:
                    continue
                # build projective point in original coords
                coord = [None, None, None]
                coord[fx] = Fr(1)
                coord[au] = u0
                coord[av] = v0
                pt = _normalize(tuple(coord))
                g0 = bshift(g, u0, v0)
                found[pt] = classify_sing(g0)
    return found, nonrational


def _dpartial(g, var):
    r = {}
    for k, c in g.items():
        e = k[var]
        if e == 0:
            continue
        nk = list(k)
        nk[var] -= 1
        r[tuple(nk)] = r.get(tuple(nk), Fr(0)) + c * e
    return {k: v for k, v in r.items() if v != 0}


def _subst_u(g, u0):
    """g(u0, v) as univariate list in v."""
    out = {}
    for (i, j), c in g.items():
        out[j] = out.get(j, Fr(0)) + c * (u0**i)
    if not out:
        return [Fr(0)]
    m = max(out)
    return [out.get(t, Fr(0)) for t in range(m + 1)]


def _normalize(pt):
    for c in pt:
        if c != 0:
            return tuple(x / c for x in pt)
    return pt


def _urat_remove_rational_roots(poly):
    """Divide out all rational linear factors; return the residual univariate."""
    p = u_trim([Fr(c) for c in poly])
    changed = True
    while changed and u_deg_local(p) > 0:
        changed = False
        rr = rational_roots(p)
        if not rr:
            break
        for r in rr:
            # divide by (x - r)
            q, rem = u_divmod(p, [-r, Fr(1)])
            if u_deg(rem) < 0:
                p = q
                changed = True
                break
    return p


def u_deg_local(p):
    return u_deg(p)


def hidden_singularity(F, d):
    """True if the curve has a singular point that is NOT a rational point,
    detected chart-wise via the triple resultant gcd. Sound (never misses a
    non-rational singularity); may conservatively flag rare irrational
    coincidences, which the disclosed domain excludes."""
    charts = [(1, 2, 0), (0, 2, 1), (0, 1, 2)]
    for au, av, _fx in charts:
        g = dehomogenize(F, (au, av))
        gu = _dpartial(g, 0)
        gv = _dpartial(g, 1)
        r1 = resultant_y(g, gu)
        r2 = resultant_y(g, gv)
        r3 = resultant_y(gu, gv)
        if any(u_deg_local(r) < 0 for r in (r1, r2, r3)):
            return True  # a resultant vanished identically -> non-isolated locus
        T = u_gcd(u_gcd(r1, r2), r3)
        if u_deg_local(T) <= 0:
            continue
        residual = _urat_remove_rational_roots(T)
        if u_deg_local(residual) > 0:
            return True
    return False


def hessian(F):
    """3x3 determinant of second partials -> ternary form of degree 3(d-2)."""
    H = [[partial(partial(F, a), b) for b in range(3)] for a in range(3)]

    # det via cofactor expansion (3x3), exact
    def det3(M):
        t1 = pmul(
            M[0][0], padd(pmul(M[1][1], M[2][2]), pscale(pmul(M[1][2], M[2][1]), -1))
        )
        t2 = pscale(
            pmul(
                M[0][1],
                padd(pmul(M[1][0], M[2][2]), pscale(pmul(M[1][2], M[2][0]), -1)),
            ),
            -1,
        )
        t3 = pmul(
            M[0][2], padd(pmul(M[1][0], M[2][1]), pscale(pmul(M[1][1], M[2][0]), -1))
        )
        return padd(padd(t1, t2), t3)

    return det3(H)


def linsub(F, M):
    """Substitute (x,y,z) := M @ (x,y,z) into ternary form F (exact)."""
    lin = []
    for row in range(3):
        L = {}
        for col, coef in enumerate(M[row]):
            if coef:
                e = [0, 0, 0]
                e[col] = 1
                L[tuple(e)] = Fr(coef)
        lin.append(L)
    out = {}
    for (i, j, k), c in F.items():
        term = {(0, 0, 0): c}
        for _ in range(i):
            term = pmul(term, lin[0])
        for _ in range(j):
            term = pmul(term, lin[1])
        for _ in range(k):
            term = pmul(term, lin[2])
        out = padd(out, term)
    return out


_GENERIC_M = [[2, 1, 1], [1, 3, 1], [1, 1, 4]]  # det 17, generic (no vertical comp)


def shares_component(F, H):
    """True if F and its Hessian H share a positive-dimensional component
    (line component => wrong Pluecker flex count => out of domain)."""
    if not H:
        return True  # Hessian identically zero: highly degenerate
    Fg = linsub(F, _GENERIC_M)
    Hg = linsub(H, _GENERIC_M)
    fg = dehomogenize(Fg, (0, 1))  # set new z=1
    hg = dehomogenize(Hg, (0, 1))
    R = resultant_y(fg, hg)
    return u_deg(R) < 0  # identically zero => common factor in v


def _fails_domain_gate(F, d):
    """True if F is out of the census's disclosed domain: wrong degree, not
    homogeneous, a hidden (non-rational) singularity, or a degenerate Hessian
    that shares a component with F (breaks the Pluecker count)."""
    return (
        d not in _VALID_DEGREES
        or not is_homogeneous(F, d)
        or hidden_singularity(F, d)
        or shares_component(F, hessian(F))
    )


def real_meet_z0(F):
    """Number of DISTINCT real points at which the curve F = 0 meets the line
    z = 0, counted in the real projective line over that line. The finite points
    [x:1:0] are the distinct real roots of phi(x) = F(x, 1, 0); the point
    [1:0:0] lies on the curve exactly when the x**d coefficient F(1,0,0) is zero.
    Defined only for a curve not containing z = 0 as a component (else phi is the
    zero polynomial); such curves are rejected upstream as reducible."""
    phi = {}
    for (i, j, k), c in F.items():
        if k != 0:
            continue
        phi[i] = phi.get(i, Fr(0)) + c
    if not phi:
        return None  # z divides F: line component, handled as ERROR upstream
    m = max(phi)
    coeffs = [phi.get(t, Fr(0)) for t in range(m + 1)]
    finite = real_roots_count(coeffs)
    if finite is None:
        return None
    d = degree(F)
    at_infinity = 1 if F.get((d, 0, 0), Fr(0)) == 0 else 0
    return finite + at_infinity


def census(F):
    if not F:
        return "ERROR"
    d = degree(F)
    if _fails_domain_gate(F, d):
        return "ERROR"  # wrong degree / inhomogeneous / hidden singularity / Hessian component
    sp, _nr = singular_points(F, d)
    if sp is None:
        return "ERROR"  # non-isolated singular locus (non-reduced / common comp)
    if any(kind == "bad" for kind, _cru in sp.values()):
        return "ERROR"
    delta = sum(1 for kind, _cru in sp.values() if kind == "node")
    kappa = sum(1 for kind, _cru in sp.values() if kind == "cusp")
    crunodes = sum(1 for kind, cru in sp.values() if kind == "node" and cru)
    g = (d - 1) * (d - 2) // 2 - delta - kappa
    if g < 0:
        return "ERROR"  # reducible / too many double points for the degree
    realmeet = real_meet_z0(F)
    if realmeet is None:
        return "ERROR"  # z-component, defensive (already excluded by domain gate)
    m = d * (d - 1) - 2 * delta - 3 * kappa
    iota = 3 * d * (d - 2) - 6 * delta - 8 * kappa
    # bitangents by Pluecker dual: d = m(m-1) - 2 tau - 3 iota
    tau2 = m * (m - 1) - 3 * iota - d
    tau = tau2 // 2 if tau2 % 2 == 0 else Fr(tau2, 2)
    return {
        "d": d,
        "delta": delta,
        "kappa": kappa,
        "crunodes": crunodes,
        "realmeet": realmeet,
        "m": m,
        "iota": iota,
        "g": g,
        "tau": tau,
    }
