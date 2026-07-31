"""Verifier for plane-curve-dual-class-census.

Runs the candidate program /app/plucker on every fixture, on runtime-minted
curves, and on metamorphic transforms, and requires its output to equal, byte
for byte, what the independent Python engine (oracle.py, over census.py) computes
from the same input. The engine determines the projective census by exact
integer and rational arithmetic -- singular locus over the algebraic closure,
tangent-cone typing, and the classical Pluecker relations -- a route that shares
no arithmetic with the floating-point or single-chart shortcuts a solver is
likely to try. Source is never inspected; only observed process output is graded.
"""

import contextlib
import os
import resource
import subprocess
import tempfile
from fractions import Fraction as Fr

import census
import oracle
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
FIXROOT = os.path.join(HERE, "fixtures")
PROG = "/app/plucker"

_MEM_CAP_BYTES = 2 * 1024 * 1024 * 1024
_NOBODY_UID = 65534
_NOBODY_GID = 65534
_MIN_FIXTURES = 60
_MIN_VALID_CASES = 40
_MIN_ERROR_CASES = 15
_MIN_VALID_QUARTICS = 5
_MIN_CASE_KIND_COUNT = 3
_MIN_MINTED_CASES = 8
_MIN_METAMORPHIC_CASES = 3
_MIN_ACNODE_CASES = 3  # double points with a complex-conjugate tangent pair
_MIN_REALMEET_GE2 = 3  # curves meeting z = 0 in two or more distinct real points
_SANDBOX_ENV = {
    "PATH": "/usr/bin:/bin",
    "HOME": "/tmp",
    "TMPDIR": "/tmp",
    "LC_ALL": "C",
}


def _sandbox():
    resource.setrlimit(resource.RLIMIT_AS, (_MEM_CAP_BYTES, _MEM_CAP_BYTES))
    with contextlib.suppress(OSError):
        os.setgroups([])
    os.setgid(_NOBODY_GID)
    os.setuid(_NOBODY_UID)


def _run(data):
    fd, path = tempfile.mkstemp(dir="/tmp", suffix=".in")
    try:
        with os.fdopen(fd, "w", newline="") as f:
            f.write(data)
        os.chmod(path, 0o644)
        res = subprocess.run(
            [PROG, path],
            capture_output=True,
            timeout=120,
            preexec_fn=_sandbox,
            env=_SANDBOX_ENV,
            cwd="/tmp",
            check=False,
        )
    finally:
        os.unlink(path)
    stderr = res.stderr.decode("utf-8", errors="replace")
    assert res.returncode == 0, (
        f"candidate exited nonzero ({res.returncode}): {stderr!r}"
    )
    for sig in (
        "Segmentation fault",
        "stack smashing",
        "double free",
        "corrupted",
        "terminate called",
        "Aborted",
        "core dumped",
        "AddressSanitizer",
    ):
        assert sig not in stderr, f"crash signature {sig!r}: {stderr!r}"
    return res.stdout.decode("utf-8")


def _fixture_names():
    out = []
    for name in sorted(os.listdir(FIXROOT)):
        d = os.path.join(FIXROOT, name)
        if os.path.isdir(d) and os.path.exists(os.path.join(d, "input.txt")):
            out.append(name)
    return out


NAMES = _fixture_names()


def _read(name):
    d = os.path.join(FIXROOT, name)
    with open(os.path.join(d, "input.txt"), newline="") as f:
        data = f.read()
    with open(os.path.join(d, "expected.txt"), newline="") as f:
        expected = f.read()
    return data, expected


@pytest.mark.parametrize("name", NAMES)
def test_fixture(name):
    data, expected = _read(name)
    recomputed = oracle.solve(data)
    assert recomputed == expected, f"golden disagrees with oracle on {name}"
    got = _run(data)
    assert got == expected, (
        f"candidate byte-mismatch on {name}: got {got!r} want {expected!r}"
    )


def test_corpus_size():
    assert len(NAMES) >= _MIN_FIXTURES, (
        f"need >= {_MIN_FIXTURES} fixtures, have {len(NAMES)}"
    )


def _fields(text):
    return dict(
        line.split(" = ") for line in text.strip("\n").split("\n") if " = " in line
    )


def test_case_coverage():
    valid = err = 0
    d4valid = 0
    acnode = realmeet_ge2 = 0
    have = {"node": 0, "cusp": 0, "smooth": 0}
    for name in NAMES:
        _, expected = _read(name)
        if expected == "ERROR\n":
            err += 1
            continue
        valid += 1
        f = _fields(expected)
        if f["degree"] == "4":
            d4valid += 1
        if int(f["doublepoints"]) > 0:
            have["node"] += 1
        if int(f["cusps"]) > 0:
            have["cusp"] += 1
        if int(f["doublepoints"]) == 0 and int(f["cusps"]) == 0:
            have["smooth"] += 1
        # a double point whose branches are complex conjugate (acnode) exists
        # exactly when crunodes falls short of the total double-point count
        if int(f["doublepoints"]) > int(f["crunodes"]):
            acnode += 1
        if int(f["realmeet"]) >= 2:
            realmeet_ge2 += 1
    assert valid >= _MIN_VALID_CASES, f"need >= {_MIN_VALID_CASES} valid, have {valid}"
    assert err >= _MIN_ERROR_CASES, f"need >= {_MIN_ERROR_CASES} ERROR, have {err}"
    assert d4valid >= _MIN_VALID_QUARTICS, (
        f"need >= {_MIN_VALID_QUARTICS} valid quartics, have {d4valid}"
    )
    for k, v in have.items():
        assert v >= _MIN_CASE_KIND_COUNT, (
            f"need >= {_MIN_CASE_KIND_COUNT} {k} curves, have {v}"
        )
    assert acnode >= _MIN_ACNODE_CASES, (
        f"need >= {_MIN_ACNODE_CASES} acnode (crunodes<doublepoints) curves, have {acnode}"
    )
    assert realmeet_ge2 >= _MIN_REALMEET_GE2, (
        f"need >= {_MIN_REALMEET_GE2} curves with realmeet>=2, have {realmeet_ge2}"
    )


# ---------------- input serialization ----------------
def _ser(F, d):
    terms = sorted(F.items(), key=lambda kv: kv[0], reverse=True)
    lines = [f"{d} {len(terms)}"]
    for (i, j, k), c in terms:
        lines.append(f"{i} {j} {k} {int(c)}")
    return "\n".join(lines) + "\n"


def _deg(F):
    return max(sum(k) for k in F)


_FERMAT4 = {(4, 0, 0): Fr(1), (0, 4, 0): Fr(1), (0, 0, 4): Fr(1)}
_NODAL3 = {(0, 2, 1): Fr(1), (3, 0, 0): Fr(-1), (2, 0, 1): Fr(-1)}
_CUSP3 = {(0, 2, 1): Fr(1), (3, 0, 0): Fr(-1)}
_SMOOTH3 = {(3, 0, 0): Fr(1), (0, 3, 0): Fr(1), (0, 0, 3): Fr(1)}


def _minted():
    cases = {}
    mats = [
        [[1, 0, 0], [3, 1, 0], [0, 2, 1]],
        [[1, 0, 2], [0, 1, 0], [0, 0, 1]],
        [[2, 1, 1], [0, 1, 3], [0, 0, 1]],
    ]
    for bn, base in [
        ("smooth3", _SMOOTH3),
        ("nodal3", _NODAL3),
        ("cusp3", _CUSP3),
        ("smooth4", _FERMAT4),
    ]:
        for mi, M in enumerate(mats):
            F = census.linsub(base, M)
            if _deg(F) != _deg(base) or any(
                abs(int(c)) > oracle.COEFBOUND for c in F.values()
            ):
                continue
            if census.census(F) == "ERROR":
                continue
            cases[f"mint_{bn}_{mi}"] = _ser(F, _deg(F))
    # large-coefficient scaling: same curve, huge intermediate arithmetic
    for s in (37, 911):
        cases[f"mint_scale_{s}"] = _ser({k: v * s for k, v in _NODAL3.items()}, 3)
    return cases


MINTED = _minted()


@pytest.mark.parametrize("name", sorted(MINTED))
def test_minted(name):
    data = MINTED[name]
    expected = oracle.solve(data)
    got = _run(data)
    assert got == expected, (
        f"candidate byte-mismatch on {name}: got {got!r} want {expected!r}"
    )


def test_minted_nonempty():
    assert len(MINTED) >= _MIN_MINTED_CASES, (
        f"need >= {_MIN_MINTED_CASES} minted cases, have {len(MINTED)}"
    )


# ---------------- metamorphic: projective invariance ----------------
_GL3 = [[1, 1, 0], [0, 1, 1], [1, 0, 1]]  # det 2, invertible over Q


def _metamorphic():
    cases = []
    for bn, base in [("smooth4", _FERMAT4), ("nodal3", _NODAL3), ("cusp3", _CUSP3)]:
        F = census.linsub(base, _GL3)
        if _deg(F) != _deg(base):
            continue
        if any(abs(int(c)) > oracle.COEFBOUND for c in F.values()):
            continue
        base_out = oracle.solve(_ser(base, _deg(base)))
        cases.append((f"meta_{bn}", _ser(F, _deg(F)), base_out))
    return cases


METAMORPHIC = _metamorphic()


def _projective_lines(text):
    """All output lines except realmeet. The six census invariants are stable
    under a linear change of coordinates; realmeet is anchored to the fixed line
    z = 0 and is not, so it is excluded from the invariance comparison."""
    return "".join(
        ln + "\n"
        for ln in text.strip("\n").split("\n")
        if not ln.startswith("realmeet ")
    )


@pytest.mark.parametrize(
    "case_id,new_input,base_out", METAMORPHIC, ids=[c[0] for c in METAMORPHIC]
)
def test_metamorphic(case_id, new_input, base_out):
    ora = oracle.solve(new_input)
    assert _projective_lines(ora) == _projective_lines(base_out), (
        f"projective invariance broken (oracle) on {case_id}"
    )
    got = _run(new_input)
    assert got == ora, (
        f"candidate breaks invariance on {case_id}: got {got!r} want {ora!r}"
    )


def test_metamorphic_nonempty():
    assert len(METAMORPHIC) >= _MIN_METAMORPHIC_CASES, (
        f"need >= {_MIN_METAMORPHIC_CASES} metamorphic cases, have {len(METAMORPHIC)}"
    )
