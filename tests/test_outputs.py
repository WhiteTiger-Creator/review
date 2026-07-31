"""Verifier for the directional Euler-characteristic transform census together
with the exact critical (sandpile) group of each mesh's 1-skeleton.

The program under test reads a mesh instance and prints, for every mesh and
every direction, the Euler characteristic curve of the height sublevel
filtration, then for every mesh the invariant factors of the critical group of
its 1-skeleton and the number of spanning trees tau, then a nearest-centroid
label for every query mesh. This file recomputes the whole census independently
in exact Python big integers and grades the agent binary against it.

Two independent exact routes pin the critical group: an integer Smith-normal-form
reduction of the reduced Laplacian yields the invariant factors, and a
fraction-free Bareiss determinant of the same matrix yields tau; the product of
the factors must equal the determinant on every mesh. The graded quantity is the
integer TORSION structure, which a rank over a field cannot see and a
floating-point determinant cannot represent once tau passes 2**53; both wrong
readings are measured to diverge on the corpus here. tau and the largest factors
run to hundreds of bits, so every intermediate is arbitrary precision; a
fixed-diagonal-pivot elimination without modular bounding blows the entries up
past any fixed width, while the smallest-pivot reduction stays bounded.
"""

import bisect
import contextlib
import glob
import os
import random
import signal
import subprocess
import tempfile
import time
from math import gcd

import numpy as np
import pytest

APP = "/app"
BIN = os.path.join(APP, "target", "release", "ect")
FIXDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
NAMES = sorted(
    os.path.basename(p)
    for p in glob.glob(os.path.join(FIXDIR, "*"))
    if os.path.isdir(p)
)
BUILD_TIMEOUT = 600
# Per-fixture run cap. The optimal oracle (global smallest-pivot, bound-controlled
# SNF) finishes every graded instance in under ~2 s; a solution that lacks
# intermediate-bound control (e.g. a local gcd-pivoting SNF that reduces modulo
# the determinant) runs tens of seconds per instance on the grid>=16 band and
# fails the instances it is stuck on, cleanly, WITHOUT hanging the whole verifier
# -- each instance is capped, so the suite always completes and reports
# per-instance results instead of timing out globally. 15 s leaves the oracle an
# ~8x margin while the whole large band (measured 24-60 s+) reliably exceeds it.
RUN_TIMEOUT = 15
# The verifier shares one wall clock with the recomputation it also has to
# do, so the time spent running the candidate is capped in total as well as
# per instance.
AGENT_TIME_BUDGET = 480
KILL_GRACE = 10

# Fixed-width reference points, and corpus-shape thresholds (named so the intent
# of each bound is explicit).
I64 = 2**63
I128 = 2**127
FLOAT_EXACT = 2**53
MIN_CORPUS = 50
MIN_TORSION = 50
MIN_TAU_OVER_I64 = 40
MIN_TAU_OVER_I128 = 30
MIN_FLOAT_WRONG = 40
MIN_HEIGHT_OVER_I128 = 50
MIN_MULTI_FACTOR = 30
BLOWUP_BITS = 20000       # naive intermediate entries must exceed this on hard band
BOUND_SLACK = 4           # efficient entries stay within this multiple of bits(tau)
MIN_REFS_PER_INSTANCE = 2
TRI_DISTINCT = 3


# ---------------------------------------------------------------- parsing
def _read_csv(path):
    with open(path) as f:
        rows = [ln.strip().split(",") for ln in f if ln.strip()]
    return rows[1:]


def _load_instance(cdir):
    g = None
    for row in _read_csv(os.path.join(cdir, "params.csv")):
        if row[0] == "G":
            g = int(row[1])
    dirs = [(int(r[1]), int(r[2]), int(r[3]))
            for r in _read_csv(os.path.join(cdir, "directions.csv"))]
    thr = [[] for _ in range(len(dirs))]
    for r in _read_csv(os.path.join(cdir, "thresholds.csv")):
        thr[int(r[0])].append((int(r[1]), int(r[2])))
    thr = [[t for _s, t in sorted(v)] for v in thr]
    meshes = [(r[0], r[1], int(r[2]))
              for r in _read_csv(os.path.join(cdir, "meshes.csv"))]
    meshes.sort(key=lambda r: r[0])
    data = {}
    for mid, _role, _label in meshes:
        vrows = _read_csv(os.path.join(cdir, "vertices", mid + ".csv"))
        vertices = [None] * len(vrows)
        for r in vrows:
            vertices[int(r[0])] = (int(r[1]), int(r[2]), int(r[3]))
        frows = _read_csv(os.path.join(cdir, "faces", mid + ".csv"))
        faces = [(int(r[0]), int(r[1]), int(r[2])) for r in frows]
        data[mid] = (vertices, faces)
    return g, dirs, thr, meshes, data


# ---------------------------------------------------------------- ECT census
def _edges(faces):
    s = set()
    for a, b, c in faces:
        for x, y in ((a, b), (b, c), (a, c)):
            s.add((x, y) if x < y else (y, x))
    return sorted(s)


def _heights(vertices, nu):
    return [vx * nu[0] + vy * nu[1] + vz * nu[2] for (vx, vy, vz) in vertices]


def _ect_steps(vertices, faces, e, nu):
    """Net contribution per entry height, prefix-summed; a height whose
    contributions cancel is not a breakpoint."""
    h = _heights(vertices, nu)
    net = {}
    for x in h:
        net[x] = net.get(x, 0) + 1
    for a, b in e:
        x = max(h[a], h[b])
        net[x] = net.get(x, 0) - 1
    for a, b, c in faces:
        x = max(h[a], h[b], h[c])
        net[x] = net.get(x, 0) + 1
    out = []
    acc = 0
    for t in sorted(net):
        d = net[t]
        if d != 0:
            acc += d
            out.append((t, acc))
    return out


def _ect_steps_count(vertices, faces, e, nu):
    """Independent route: count simplices at or below each candidate height
    outright, then keep heights where the counted value changes."""
    h = _heights(vertices, nu)
    he = [max(h[a], h[b]) for a, b in e]
    hf = [max(h[a], h[b], h[c]) for a, b, c in faces]
    cand = sorted(set(h) | set(he) | set(hf))
    hs, hes, hfs = sorted(h), sorted(he), sorted(hf)
    out = []
    prev = 0
    for t in cand:
        val = (bisect.bisect_right(hs, t)
               - bisect.bisect_right(hes, t)
               + bisect.bisect_right(hfs, t))
        if val != prev:
            out.append((t, val))
            prev = val
    return out


def _value_at(st, ts):
    if not st:
        return [0] * len(ts)
    hs = [s[0] for s in st]
    cs = [s[1] for s in st]
    res = []
    for t in ts:
        i = bisect.bisect_right(hs, t)
        res.append(cs[i - 1] if i > 0 else 0)
    return res


def _classify(qflat, refs):
    labels = sorted({lb for lb, _v in refs})
    k = sum(1 for lb, _v in refs if lb == labels[0])
    best, bestd = None, None
    q = [int(x) for x in qflat]
    for lab in labels:
        s = [0] * len(q)
        for lb, v in refs:
            if lb == lab:
                for i in range(len(q)):
                    s[i] += int(v[i])
        d = sum((k * q[i] - s[i]) ** 2 for i in range(len(q)))
        if bestd is None or d < bestd:
            bestd, best = d, lab
    return best


# ---------------------------------------------------------------- critical group
def _reduced_laplacian(n, e):
    lap = [[0] * n for _ in range(n)]
    for a, b in e:
        lap[a][a] += 1
        lap[b][b] += 1
        lap[a][b] -= 1
        lap[b][a] -= 1
    return [row[:n - 1] for row in lap[:n - 1]]


def _snf_factors(matrix, track=False):
    """Invariant factors by smallest-absolute-value pivoting (bounded)."""
    a = [row[:] for row in matrix]
    rows = len(a)
    cols = len(a[0]) if rows else 0
    maxbits = 0
    for t in range(min(rows, cols)):
        while True:
            piv = None
            pv = None
            for i in range(t, rows):
                for j in range(t, cols):
                    if a[i][j] != 0:
                        av = abs(a[i][j])
                        if pv is None or av < pv:
                            pv = av
                            piv = (i, j)
            if piv is None:
                break
            pi, pj = piv
            if pi != t:
                a[t], a[pi] = a[pi], a[t]
            if pj != t:
                for r in range(rows):
                    a[r][t], a[r][pj] = a[r][pj], a[r][t]
            changed = False
            d = a[t][t]
            for i in range(t + 1, rows):
                if a[i][t] != 0:
                    q = a[i][t] // d
                    if q != 0:
                        for j in range(t, cols):
                            a[i][j] -= q * a[t][j]
                    if a[i][t] != 0:
                        changed = True
            for j in range(t + 1, cols):
                if a[t][j] != 0:
                    q = a[t][j] // d
                    if q != 0:
                        for i in range(t, rows):
                            a[i][j] -= q * a[i][t]
                    if a[t][j] != 0:
                        changed = True
            if track:
                for row in a:
                    for x in row:
                        if x:
                            maxbits = max(maxbits, x.bit_length())
            if changed:
                continue
            d = a[t][t]
            bad = None
            if d != 0:
                for i in range(t + 1, rows):
                    for j in range(t + 1, cols):
                        if a[i][j] % d != 0:
                            bad = i
                            break
                    if bad is not None:
                        break
            if bad is not None:
                for j in range(t, cols):
                    a[t][j] += a[bad][j]
                continue
            break
    facs = [abs(a[i][i]) for i in range(min(rows, cols))]
    return (facs, maxbits) if track else facs


def _bareiss_det(matrix):
    n = len(matrix)
    if n == 0:
        return 1
    a = [row[:] for row in matrix]
    prev = 1
    sign = 1
    for k in range(n - 1):
        if a[k][k] == 0:
            piv = None
            for i in range(k + 1, n):
                if a[i][k] != 0:
                    piv = i
                    break
            if piv is None:
                return 0
            a[k], a[piv] = a[piv], a[k]
            sign = -sign
        for i in range(k + 1, n):
            for j in range(k + 1, n):
                a[i][j] = (a[i][j] * a[k][k] - a[i][k] * a[k][j]) // prev
        prev = a[k][k]
    return sign * a[n - 1][n - 1]


def _naive_snf_maxbits(matrix):
    """Fixed-diagonal pivot with lcm cross-multiply and no modular bounding (the
    trap): clears the pivot column and row by integer cross-multiplication.
    Returns the largest entry bit-length reached over the reduction."""
    a = [row[:] for row in matrix]
    n = len(a)
    cols = len(a[0]) if n else 0
    maxbits = 0
    for t in range(min(n, cols)):
        if a[t][t] == 0:
            sw = next((i for i in range(t + 1, n) if a[i][t] != 0), None)
            if sw is None:
                continue
            a[t], a[sw] = a[sw], a[t]
        for i in range(t + 1, n):
            if a[i][t] != 0:
                g = gcd(a[t][t], a[i][t])
                mp, mq = a[t][t] // g, a[i][t] // g
                for j in range(t, cols):
                    a[i][j] = mp * a[i][j] - mq * a[t][j]
        for j in range(t + 1, cols):
            if a[t][j] != 0:
                g = gcd(a[t][t], a[t][j])
                mp, mq = a[t][t] // g, a[t][j] // g
                for i in range(t, n):
                    a[i][j] = mp * a[i][j] - mq * a[i][t]
        for row in a:
            for x in row:
                if x:
                    maxbits = max(maxbits, x.bit_length())
    return maxbits


def _critical_group(n, e):
    facs = _snf_factors(_reduced_laplacian(n, e))
    tau = 1
    for f in facs:
        tau *= f
    gt1 = [f for f in facs if f > 1]
    return gt1, tau


# ---------------------------------------------------------------- reference
_REF_CACHE = {}
_CG_CACHE = {}


def _cg_meshes(cdir):
    """Per-mesh (mid, n, edges, gt1, tau, reduced_laplacian), cached."""
    if cdir in _CG_CACHE:
        return _CG_CACHE[cdir]
    _g, _dirs, _thr, meshes, data = _load_instance(cdir)
    out = []
    for mid, _role, _label in meshes:
        vertices, faces = data[mid]
        e = _edges(faces)
        n = len(vertices)
        gt1, tau = _critical_group(n, e)
        out.append((mid, n, e, gt1, tau, _reduced_laplacian(n, e)))
    _CG_CACHE[cdir] = out
    return out


def _reference(cdir, steps=_ect_steps):
    ck = (cdir, steps.__name__)
    if ck in _REF_CACHE:
        return _REF_CACHE[ck]
    _g, dirs, thr, meshes, data = _load_instance(cdir)
    ect, vals, flats, refs, queries = [], [], {}, [], []
    cg = {mid: (gt1, tau) for mid, _n, _e, gt1, tau, _l in _cg_meshes(cdir)}
    cg_lines, tau_lines = [], []
    for mid, role, label in meshes:
        vertices, faces = data[mid]
        e = _edges(faces)
        flat = []
        for d in range(len(dirs)):
            st = steps(vertices, faces, e, dirs[d])
            body = " ".join(f"{t} {c}" for t, c in st)
            ect.append(f"ECT {mid} {d} {len(st)}" + (" " + body if st else ""))
            got = _value_at(st, thr[d])
            vals.append(f"VAL {mid} {d} " + " ".join(str(x) for x in got))
            flat += got
        gt1, _tau = cg[mid]
        cg_lines.append(f"CG {mid} {len(gt1)}"
                        + ((" " + " ".join(str(x) for x in gt1)) if gt1 else ""))
        tau_lines.append(f"TAU {mid} {cg[mid][1]}")
        flats[mid] = flat
        if role == "reference":
            refs.append((label, flat))
        else:
            queries.append(mid)
    lines = ect + vals + cg_lines + tau_lines
    for q in queries:
        lines.append(f"LABEL {q} {_classify(flats[q], refs)}")
    _REF_CACHE[ck] = "\n".join(lines)
    return _REF_CACHE[ck]


# ---------------------------------------------------------------- build / run
def _build():
    for p in glob.glob(os.path.join(APP, "src", "*.rs")):
        os.utime(p, None)
    cmd = ["cargo", "build", "--release", "--manifest-path",
           os.path.join(APP, "Cargo.toml")]
    subprocess.run(cmd, check=True, capture_output=True, timeout=BUILD_TIMEOUT,
                   cwd=APP)


_AGENT_SPENT = [0.0]


def _kill_process_group(proc):
    """Kill the candidate and anything it started."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        proc.kill()


def _run(cdir):
    """Run the candidate on one instance, bounded per instance and in total.

    The candidate starts in its own session, so a timeout kills the whole
    process group. A program that hands its work to a helper and lets the helper
    inherit the output pipe would otherwise keep the verifier reading long after
    the program it started was killed.
    """
    remaining = AGENT_TIME_BUDGET - _AGENT_SPENT[0]
    if remaining <= 0:
        return "<timeout>"
    started = time.monotonic()
    proc = subprocess.Popen(
        [BIN, cdir], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        out, _err = proc.communicate(timeout=min(RUN_TIMEOUT, remaining))
    except subprocess.TimeoutExpired:
        _kill_process_group(proc)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.communicate(timeout=KILL_GRACE)
        return "<timeout>"
    finally:
        _AGENT_SPENT[0] += time.monotonic() - started
    return out.decode().strip()


_RUN_CACHE = {}


def _agent(cdir):
    if cdir not in _RUN_CACHE:
        try:
            _RUN_CACHE[cdir] = _run(cdir)
        except subprocess.CalledProcessError as exc:
            _RUN_CACHE[cdir] = f"<error:{exc.returncode}>"
    return _RUN_CACHE[cdir]


@pytest.fixture(scope="session", autouse=True)
def _built():
    _build()
    assert os.path.exists(BIN)


def _fx(name):
    return os.path.join(FIXDIR, name)


# ---------------------------------------------------------------- per instance
@pytest.mark.parametrize("name", NAMES)
def test_agent_matches_reference(name):
    """The program reproduces the independently recomputed census exactly,
    including the critical-group invariant factors and tau."""
    if _agent(_fx(name)) != _reference(_fx(name)):
        pytest.fail(f"census mismatch on {name}", pytrace=False)


@pytest.mark.parametrize("name", NAMES)
def test_reference_methods_agree(name):
    """Smith-normal-form invariant factors multiply to the Matrix-Tree
    determinant on every mesh: two independent exact routes to tau."""
    for mid, _n, _e, gt1, tau, lap in _cg_meshes(_fx(name)):
        prod = 1
        for f in gt1:
            prod *= f
        det = abs(_bareiss_det(lap))
        if prod != tau or det != tau:
            pytest.fail(f"routes disagree on {name} {mid}: "
                        f"snf={prod} bareiss={det} tau={tau}", pytrace=False)


@pytest.mark.parametrize("name", NAMES)
def test_ect_two_routes_agree(name):
    """Accumulating net contributions and counting simplices outright give one
    Euler characteristic census (preserves the transform identity)."""
    if _reference(_fx(name), _ect_steps) != _reference(_fx(name), _ect_steps_count):
        pytest.fail(f"ect routes disagree on {name}", pytrace=False)


# ---------------------------------------------------------------- corpus shape
def test_corpus_is_large_enough():
    assert len(NAMES) >= MIN_CORPUS


def _max_tau(cdir):
    return max(tau for _m, _n, _e, _g, tau, _l in _cg_meshes(cdir))


def test_every_mesh_has_torsion():
    """Every mesh's critical group is a nontrivial finite abelian group, so a
    field-rank reading (which reports no torsion) is wrong everywhere."""
    good = sum(
        1 for n in NAMES
        if all(gt1 for _m, _nn, _e, gt1, _t, _l in _cg_meshes(_fx(n)))
    )
    assert good >= MIN_TORSION


def test_corpus_spans_fixed_width_bands():
    """A reachable gradient: many instances exceed 64-bit tau, and many exceed
    128-bit tau so no fixed-width accumulator can hold the spanning-tree count."""
    over64 = sum(1 for n in NAMES if _max_tau(_fx(n)) > I64)
    over128 = sum(1 for n in NAMES if _max_tau(_fx(n)) > I128)
    assert over64 >= MIN_TAU_OVER_I64
    assert over128 >= MIN_TAU_OVER_I128


def test_many_instances_have_multi_factor_groups():
    """Many critical groups need several invariant factors, so reporting only
    tau (or only the largest factor) is insufficient."""
    multi = sum(
        1 for n in NAMES
        if any(len(gt1) >= 2 for _m, _nn, _e, gt1, _t, _l in _cg_meshes(_fx(n)))
    )
    assert multi >= MIN_MULTI_FACTOR


def _max_height(cdir):
    _g, dirs, _thr, meshes, data = _load_instance(cdir)
    top = 0
    for mid, _role, _label in meshes:
        vertices, _faces = data[mid]
        for nu in dirs:
            top = max([top, *(abs(x) for x in _heights(vertices, nu))])
    return top


def test_heights_exceed_fixed_width():
    """Directional heights exceed 128-bit range, so the filtration ordering also
    demands exact arithmetic (the transform's original bignum-height identity)."""
    wide = sum(1 for n in NAMES if _max_height(_fx(n)) > I128)
    assert wide >= MIN_HEIGHT_OVER_I128


# ---------------------------------------------------------------- wrong readings
def test_field_rank_misses_torsion_on_the_corpus():
    """A rank over a field yields n-1 for a connected graph and no torsion; it
    disagrees with the true invariant factors wherever the group is nontrivial,
    which is every mesh."""
    wrong = 0
    for n in NAMES:
        for _m, _nn, _e, gt1, _t, _l in _cg_meshes(_fx(n)):
            if gt1 != []:      # the field reading reports no torsion factors
                wrong += 1
                break
    assert wrong >= MIN_TORSION


def test_float_determinant_is_wrong_on_the_large_band():
    """A floating-point determinant of the reduced Laplacian cannot represent
    tau once it passes 2**53, so it disagrees with the exact tau on the band
    where tau is large."""
    wrong = 0
    for n in NAMES:
        bad = False
        for _m, _nn, _e, _g, tau, lap in _cg_meshes(_fx(n)):
            if tau <= FLOAT_EXACT:
                continue
            fd = float(np.linalg.det(np.array(lap, dtype=float))) if lap else 1.0
            if round(fd) != tau:
                bad = True
                break
        if bad:
            wrong += 1
    assert wrong >= MIN_FLOAT_WRONG


def _hard_probe():
    """A hard-band fixture+mesh with tau over 128 bits and the largest vertex
    count that still reduces quickly: used to exhibit the naive blow-up against
    the bounded reduction."""
    best = None
    for n in NAMES:
        for _m, nn, _e, _g, tau, lap in _cg_meshes(_fx(n)):
            if tau > I128 and nn <= 170 and (best is None or nn > best[0]):
                best = (nn, tau, lap)
    return best


def test_naive_elimination_blows_up_while_bounded_stays_small():
    """On a hard-band mesh the fixed-pivot lcm elimination drives intermediate
    entries past tens of thousands of bits, while the smallest-pivot reduction
    keeps every entry within a small multiple of bits(tau)."""
    probe = _hard_probe()
    assert probe is not None, "no hard probe mesh found"
    _n, tau, lap = probe
    _facs, eff_bits = _snf_factors(lap, track=True)
    naive_bits = _naive_snf_maxbits(lap)
    assert naive_bits > BLOWUP_BITS, f"naive only reached {naive_bits} bits"
    assert eff_bits <= BOUND_SLACK * tau.bit_length(), (
        f"bounded method not bounded: {eff_bits} vs bits(tau)={tau.bit_length()}")
    assert naive_bits > 20 * eff_bits, (
        f"separation too small: naive={naive_bits} efficient={eff_bits}")


# ---------------------------------------------------------------- determinism
def test_run_is_deterministic():
    """Two runs of the program on the same instance produce identical output."""
    name = NAMES[len(NAMES) // 2]
    assert _run(_fx(name)) == _run(_fx(name))


# ---------------------------------------------------------------- format
@pytest.mark.parametrize("name", [NAMES[0], NAMES[-1]])
def test_output_format(name):
    """Every emitted line has the declared shape and field arity."""
    _g, dirs, _thr, meshes, _data = _load_instance(_fx(name))
    out = _agent(_fx(name)).splitlines()
    tags = {}
    for ln in out:
        tags.setdefault(ln.split()[0], 0)
        tags[ln.split()[0]] += 1
    nmesh = len(meshes)
    nquery = sum(1 for _m, role, _l in meshes if role == "query")
    assert tags.get("ECT", 0) == nmesh * len(dirs)
    assert tags.get("VAL", 0) == nmesh * len(dirs)
    assert tags.get("CG", 0) == nmesh
    assert tags.get("TAU", 0) == nmesh
    assert tags.get("LABEL", 0) == nquery
    for ln in out:
        f = ln.split()
        if f[0] == "CG":
            assert int(f[2]) == len(f) - 3
        elif f[0] == "TAU":
            assert len(f) == 3 and (f[2].lstrip("-").isdigit())


# ---------------------------------------------------------------- hygiene
def _canonical(cdir):
    _g, _dirs, _thr, meshes, data = _load_instance(cdir)
    keys = []
    for mid, _r, _l in meshes:
        vertices, faces = data[mid]
        mins = (min(v[0] for v in vertices), min(v[1] for v in vertices),
                min(v[2] for v in vertices))
        vs = tuple(sorted((x - mins[0], y - mins[1], z - mins[2])
                          for (x, y, z) in vertices))
        fs = tuple(sorted(tuple(sorted(f)) for f in faces))
        keys.append((vs, fs))
    return tuple(sorted(keys))


def test_instances_are_pairwise_distinct():
    seen = {}
    for n in NAMES:
        key = _canonical(_fx(n))
        assert key not in seen, f"{n} repeats {seen.get(key)}"
        seen[key] = n


def _token_multiset(cdir):
    toks = {}
    for root, _dirs, files in os.walk(cdir):
        for fn in sorted(files):
            with open(os.path.join(root, fn)) as f:
                for line in f:
                    for t in line.replace(",", " ").split():
                        toks[t] = toks.get(t, 0) + 1
    return tuple(sorted(toks.items()))


def test_instances_have_distinct_token_multisets():
    seen = {}
    for n in NAMES:
        key = _token_multiset(_fx(n))
        assert key not in seen, f"{n} shares tokens with {seen.get(key)}"
        seen[key] = n


def test_fixtures_carry_no_answer_key():
    allowed = {"params.csv", "directions.csv", "meshes.csv", "thresholds.csv"}
    for n in NAMES:
        for root, _dirs, files in os.walk(_fx(n)):
            for fn in files:
                base = os.path.basename(root)
                ok = fn in allowed or base in ("vertices", "faces")
                assert ok, f"unexpected file in instance: {root}/{fn}"


def test_disclosed_example_is_not_a_graded_instance():
    ex = os.path.join(APP, "example")
    if not os.path.isdir(ex):
        pytest.skip("no disclosed example present")
    graded = {_canonical(_fx(n)) for n in NAMES}
    assert _canonical(ex) not in graded


def test_instances_are_well_formed():
    for n in NAMES:
        g, dirs, thr, meshes, data = _load_instance(_fx(n))
        assert g >= 1
        assert len(dirs) == len(thr)
        assert all(len(t) > 0 for t in thr)
        refs = [m for m in meshes if m[1] == "reference"]
        queries = [m for m in meshes if m[1] == "query"]
        assert queries and len(refs) >= MIN_REFS_PER_INSTANCE
        counts = {}
        for _mid, _role, label in refs:
            counts[label] = counts.get(label, 0) + 1
        assert len(set(counts.values())) == 1
        for mid, _role, _label in meshes:
            vertices, faces = data[mid]
            assert all(0 <= c <= g for v in vertices for c in v)
            for a, b, c in faces:
                assert len({a, b, c}) == TRI_DISTINCT


# ---------------------------------------------------------------- battery
def _rand_grid(rng):
    a = rng.randint(3, 6)
    b = rng.randint(3, 6)
    faces = set()
    for i in range(a - 1):
        for j in range(b - 1):
            v00, v10 = i * b + j, (i + 1) * b + j
            v01, v11 = i * b + j + 1, (i + 1) * b + j + 1
            faces.add(tuple(sorted((v00, v10, v01))))
            faces.add(tuple(sorted((v10, v11, v01))))
    return a * b, sorted(faces)


def test_generated_battery_agrees_across_methods():
    """On OS-seeded random grid meshes, the program matches the recomputation and
    both critical-group routes agree."""
    seed = int.from_bytes(os.urandom(8), "big")
    rng = random.Random(seed)
    g = 9 * 10**18
    checked = 0
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(8):
            n, faces = _rand_grid(rng)
            e = _edges(faces)
            gt1, tau = _critical_group(n, e)
            det = abs(_bareiss_det(_reduced_laplacian(n, e)))
            prod = 1
            for f in gt1:
                prod *= f
            assert prod == det == tau, f"seed={seed} i={i} routes disagree"
            cdir = os.path.join(tmp, f"g{i:03d}")
            os.makedirs(os.path.join(cdir, "vertices"))
            os.makedirs(os.path.join(cdir, "faces"))
            verts = [(rng.randint(0, g), rng.randint(0, g), rng.randint(0, g))
                     for _ in range(n)]
            verts[0] = (g, g, g)
            dirs = [(1, 0, 0), (0, 0, 1), (g, g, g),
                    tuple(rng.randint(10**18, g) for _ in range(3))]
            with open(os.path.join(cdir, "params.csv"), "w") as f:
                f.write(f"field,value\nG,{g}\n")
            with open(os.path.join(cdir, "directions.csv"), "w") as f:
                f.write("dir_id,nx,ny,nz\n")
                f.writelines(f"{d},{nu[0]},{nu[1]},{nu[2]}\n"
                             for d, nu in enumerate(dirs))
            with open(os.path.join(cdir, "thresholds.csv"), "w") as f:
                f.write("dir_id,slot,t\n")
                for d, nu in enumerate(dirs):
                    bps = [t for t, _c in _ect_steps(verts, faces, e, nu)]
                    picks = sorted({bps[0] - 1, bps[-1], bps[len(bps) // 2]})
                    f.writelines(f"{d},{s},{t}\n" for s, t in enumerate(picks))
            with open(os.path.join(cdir, "meshes.csv"), "w") as f:
                f.write("mesh_id,role,label\nm0,reference,0\nm1,query,-1\n")
            for mid in ("m0", "m1"):
                with open(os.path.join(cdir, "vertices", mid + ".csv"), "w") as f:
                    f.write("vid,x,y,z\n")
                    f.writelines(f"{vid},{v[0]},{v[1]},{v[2]}\n"
                                 for vid, v in enumerate(verts))
                with open(os.path.join(cdir, "faces", mid + ".csv"), "w") as f:
                    f.write("v0,v1,v2\n")
                    f.writelines(f"{t[0]},{t[1]},{t[2]}\n" for t in faces)
            if _run(cdir) != _reference(cdir):
                pytest.fail(f"battery mismatch seed={seed} i={i}", pytrace=False)
            checked += 1
    assert checked == 8
