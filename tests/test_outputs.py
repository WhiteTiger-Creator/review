"""Verifier tests for golub-kahan-bidiagonal-svd-relative-accuracy.

Builds the agent's tree with CMake (from a clean `build/` directory, so a
stale binary can never be trusted), then runs the resulting `svd_solve`
binary against every graded case and checks it against an independent route
that never calls the agent's own code:

  (a) self-consistency: `U^H U` and `V^H V` against identity, and
      `U * diag(sigma) * V^H` against the case's own complex `A` (re-parsed
      independently from the case file), both scaled by `A`'s own
      magnitude -- catches any implementation whose reported factors do not
      actually reconstruct the disclosed input, regardless of what it
      claims about its own correctness.
  (b) ground-truth singular values for the "graded embedding" family: these
      cases are constructed at authoring time as `A = Q1 diag(sigma_true)
      Q2^H` for a disclosed real `sigma_true` and random COMPLEX UNITARY
      `Q1, Q2`; `sigma_true` is stored verbatim (never computed by any SVD
      routine) under `tests/reference/*.sigma` and compared against the
      candidate's reported singular values at a per-index tolerance.
  (c) ground-truth singular values for the "clustered bidiagonal" family:
      these cases are exactly upper bidiagonal by construction (all
      off-band entries exactly zero, real diagonal/superdiagonal), so their
      entries are read directly back out of the disclosed `A` and each
      independent 2x2 diagonal block's exact singular values are computed
      via a closed-form stable formula -- no SVD routine, agent or
      otherwise, is used to produce this reference.
  (d) ground-truth singular values for the "rank-deficient" family: a
      connected (not block-decoupled) bidiagonal chain -- real-valued or
      genuinely complex -- with one entry planted at exactly zero, so the
      matrix is exactly rank-deficient. Ground truth is an independent
      50-digit mpmath eigendecomposition of B^H B disclosed at authoring
      time. An exact-zero pivot makes the ordinary trailing-2x2 Wilkinson
      shift singular; a candidate that never special-cases it either fails
      to converge or reports a spurious spectrum, both caught below.
  (e) metamorphic relations (unitary invariance, complex phase/magnitude
      scaling, conjugate transpose) checked by re-running the candidate on
      a second, independently disclosed derived fixture and comparing its
      own two reported singular-value sets to each other -- no stored
      reference needed at all.

Case visibility has two tiers:

  - "public" cases live under `/app/environment/data/case_*.txt`, copied
    into the agent's own image.
  - "hidden" cases live under `tests/hidden_data/`, never copied into the
    agent-visible image (see environment/Dockerfile and
    environment/.dockerignore, which excludes `tests/` entirely) -- written
    to a fresh temp directory and run through the compiled binary only at
    verification time.

All matrix/vector arithmetic in this file is plain Python complex numbers
(no numpy, no scipy, no external SVD or eigensolver of any kind): every
case here is small (n <= 16), so there is no performance reason to take on
a dependency in the verifier image, and doing so would risk the verifier's
own reference silently sharing a bug with a candidate that happens to link
the same library.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
DATA_DIR = ENV / "data"
INCLUDE_DIR = ENV / "include"
BUILD_DIR = ENV / "build"

TESTS_DIR = Path(__file__).resolve().parent
HIDDEN_DATA_DIR = TESTS_DIR / "hidden_data"
REF_DIR = TESTS_DIR / "reference"

EPS = 2.220446049250313e-16

MANIFEST = json.loads((REF_DIR / "manifest.json").read_text())
CASE_NAMES = MANIFEST["manifest"]
META_DERIVED = MANIFEST["meta_derived"]

GRADE_B_TOL_MULT = 100.0
GRADE_B_TOL_FLOOR = 3e-10
GRADE_C_TOL = 1e-6
SELF_CONS_TOL = 1e-9
GRADE_D_TOL = 1e-11
GRADE_F_TOL = 1e-11
META_TOL = 1e-7

SELF_CONS_PUBLIC = [
    n for fam in ["SC", "D_public", "E", "meta_base"] for n in CASE_NAMES[fam]
]
SELF_CONS_HIDDEN = list(CASE_NAMES["D_hidden"])

GRADE_B_PUBLIC = list(CASE_NAMES["B_public"])
GRADE_B_HIDDEN = list(CASE_NAMES["B_hidden"])
GRADE_C_PUBLIC = list(CASE_NAMES["C_public"])
GRADE_C_HIDDEN = list(CASE_NAMES["C_hidden"])
GRADE_F_PUBLIC = list(CASE_NAMES["F_public"])
GRADE_F_HIDDEN = list(CASE_NAMES["F_hidden"])

META_UNITARY = META_DERIVED["unitary"]
META_SCALE = META_DERIVED["scale"]
META_CONJT = META_DERIVED["conj_transpose"]

ALL_META_DERIVED_NAMES = (
    [d for _, d in META_UNITARY]
    + [d for _, d, *_ in META_SCALE]
    + [d for _, d in META_CONJT]
)

ALL_PUBLIC_CASE_NAMES = (
    SELF_CONS_PUBLIC
    + GRADE_B_PUBLIC
    + GRADE_C_PUBLIC
    + GRADE_F_PUBLIC
    + ALL_META_DERIVED_NAMES
    + ["case_toy2x2"]
)
ALL_HIDDEN_CASE_NAMES = (
    SELF_CONS_HIDDEN + GRADE_B_HIDDEN + GRADE_C_HIDDEN + GRADE_F_HIDDEN
)

ALL_GRADED_CASE_NAMES = (
    SELF_CONS_PUBLIC
    + SELF_CONS_HIDDEN
    + GRADE_B_PUBLIC
    + GRADE_B_HIDDEN
    + GRADE_C_PUBLIC
    + GRADE_C_HIDDEN
    + GRADE_F_PUBLIC
    + GRADE_F_HIDDEN
    + [d for _, d in META_UNITARY]
    + [d for _, d, *_ in META_SCALE]
    + [d for _, d in META_CONJT]
)


# ---------------------------------------------------------------------------
# Pure-Python complex linear algebra helpers (no third-party dependency)
# ---------------------------------------------------------------------------


def _matmul(A, B):
    n = len(A)
    k = len(B)
    m = len(B[0]) if k else 0
    C = [[0j] * m for _ in range(n)]
    for i in range(n):
        Ai = A[i]
        Ci = C[i]
        for p in range(k):
            a = Ai[p]
            if a == 0j:
                continue
            Bp = B[p]
            for j in range(m):
                Ci[j] += a * Bp[j]
    return C


def _conj_transpose(A):
    n = len(A)
    m = len(A[0]) if n else 0
    return [[A[i][j].conjugate() for i in range(n)] for j in range(m)]


def _max_abs(A):
    return max((abs(v) for row in A for v in row), default=0.0)


def _max_abs_diff(A, B):
    result = 0.0
    saw_nonfinite = False
    for i in range(len(A)):
        for j in range(len(A[0])):
            d = abs(A[i][j] - B[i][j])
            if not math.isfinite(d):
                saw_nonfinite = True
                continue
            if d > result:
                result = d
    return math.nan if saw_nonfinite else result


def _identity(n):
    return [[1 + 0j if i == j else 0j for j in range(n)] for i in range(n)]


def svd2x2_closed_form(d1, e, d2):
    """Exact singular values of the REAL 2x2 upper-bidiagonal [[d1,e],[0,d2]],
    via a stable closed-form (cancellation-safe) formula -- no iteration."""
    fa, ga, ha = abs(d1), abs(e), abs(d2)
    fhmn, fhmx = min(fa, ha), max(fa, ha)
    if fhmn == 0.0:
        smin = 0.0
        if fhmx == 0.0:
            smax = ga
        else:
            smax = max(fhmx, ga) * math.sqrt(1.0 + (min(fhmx, ga) / max(fhmx, ga)) ** 2)
        return smax, smin
    if ga < fhmx:
        as_ = 1.0 + fhmn / fhmx
        at = (fhmx - fhmn) / fhmx
        au = (ga / fhmx) ** 2
        c = 2.0 / (math.sqrt(as_ * as_ + au) + math.sqrt(at * at + au))
        smin = fhmn * c
        smax = fhmx / c
    else:
        au = fhmx / ga
        if au == 0.0:
            smin = (fhmn * fhmx) / ga
            smax = ga
        else:
            as_ = 1.0 + fhmn / fhmx
            at = (fhmx - fhmn) / fhmx
            c = 1.0 / (math.sqrt(1 + (as_ * au) ** 2) + math.sqrt(1 + (at * au) ** 2))
            smin = (fhmn * c) * au * 2.0
            smax = ga / (c * 2.0)
    return smax, smin


# ---------------------------------------------------------------------------
# Case / output file parsing
# ---------------------------------------------------------------------------


def _case_path(case_name: str) -> Path:
    public_path = DATA_DIR / f"{case_name}.txt"
    if public_path.exists():
        return public_path
    return HIDDEN_DATA_DIR / f"{case_name}.txt"


def parse_case_file(path: Path):
    tokens: list[float] = []
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s:
            continue
        tokens.extend(float(t) for t in s.split())
    m = int(round(tokens[0]))
    n = int(round(tokens[1]))
    A = [[0j] * n for _ in range(m)]
    idx = 2
    for i in range(m):
        for j in range(n):
            re = tokens[idx]
            im = tokens[idx + 1]
            idx += 2
            A[i][j] = complex(re, im)
    assert idx == len(tokens), f"{path.name}: unexpected trailing tokens"
    return m, n, A


def parse_output_file(path: Path) -> dict:
    lines = path.read_text().splitlines()
    pos = 0

    def next_line() -> str:
        nonlocal pos
        assert pos < len(lines), f"{path}: output file ended unexpectedly"
        line = lines[pos]
        pos += 1
        return line

    m_line = next_line()
    assert m_line.startswith("m="), f"{path}: expected 'm=' line, got {m_line!r}"
    m = int(m_line[len("m=") :])

    n_line = next_line()
    assert n_line.startswith("n="), f"{path}: expected 'n=' line, got {n_line!r}"
    n = int(n_line[len("n=") :])

    status_line = next_line()
    assert status_line.startswith("status="), f"{path}: expected 'status=' line"
    status = status_line[len("status=") :]

    message_line = next_line()
    assert message_line.startswith("message="), f"{path}: expected 'message=' line"

    result = {"m": m, "n": n, "status": status}
    if status != "OK":
        return result

    sv_line = next_line()
    assert sv_line.startswith("singular_values="), (
        f"{path}: expected 'singular_values=' line"
    )
    sigma = [float(v) for v in sv_line[len("singular_values=") :].split()]
    assert len(sigma) == n, (
        f"{path}: singular_values has {len(sigma)} entries, expected {n}"
    )

    def read_complex_rows(count: int, width: int):
        rows = []
        for _ in range(count):
            vals = [float(v) for v in next_line().split()]
            assert len(vals) == 2 * width, (
                f"{path}: row has {len(vals)} numbers, expected {2 * width}"
            )
            rows.append([complex(vals[2 * k], vals[2 * k + 1]) for k in range(width)])
        return rows

    assert next_line() == "U", f"{path}: expected 'U' section header"
    U = read_complex_rows(m, n)

    assert next_line() == "V", f"{path}: expected 'V' section header"
    V = read_complex_rows(n, n)

    result.update({"sigma": sigma, "U": U, "V": V})
    return result


# ---------------------------------------------------------------------------
# Build + run fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def built() -> Path:
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    configure = subprocess.run(
        ["cmake", "-S", str(ENV), "-B", str(BUILD_DIR), "-DCMAKE_BUILD_TYPE=Release"],
        cwd=str(ENV),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
    )
    assert configure.returncode == 0, f"cmake configure failed:\n{configure.stdout}"
    build = subprocess.run(
        ["cmake", "--build", str(BUILD_DIR), "-j"],
        cwd=str(ENV),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
    )
    assert build.returncode == 0, f"cmake build failed:\n{build.stdout}"
    binary = BUILD_DIR / "svd_solve"
    assert binary.exists(), "build did not produce build/svd_solve"
    return binary


def run_case(built_binary: Path, case_path: Path, tmp_path: Path):
    out_file = tmp_path / f"{case_path.stem}.out"
    result = subprocess.run(
        [str(built_binary), str(case_path), str(out_file)],
        cwd=str(ENV),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )
    return result, out_file


def _solve(built_binary: Path, case_name: str, tmp_path: Path) -> dict:
    case_path = _case_path(case_name)
    result, out_file = run_case(built_binary, case_path, tmp_path)
    assert result.returncode == 0, (
        f"{case_name}: svd_solve exited {result.returncode}\nstderr:\n{result.stderr}"
    )
    assert out_file.exists(), f"{case_name}: no output file was written"
    return parse_output_file(out_file)


def _validate_well_formed(case_name: str, m: int, n: int, out: dict) -> None:
    assert out["status"] == "OK", f"{case_name}: status={out['status']!r}, expected OK"
    assert out["m"] == m and out["n"] == n, (
        f"{case_name}: output shape ({out['m']},{out['n']}), expected ({m},{n})"
    )
    sigma = out["sigma"]
    assert all(math.isfinite(s) for s in sigma), (
        f"{case_name}: singular_values not finite"
    )
    assert all(s >= 0.0 for s in sigma), (
        f"{case_name}: singular_values must be nonnegative"
    )
    for i in range(len(sigma) - 1):
        assert sigma[i] >= sigma[i + 1], f"{case_name}: singular_values not descending"
    assert all(
        math.isfinite(v.real) and math.isfinite(v.imag) for row in out["U"] for v in row
    ), f"{case_name}: U not finite"
    assert all(
        math.isfinite(v.real) and math.isfinite(v.imag) for row in out["V"] for v in row
    ), f"{case_name}: V not finite"


def _self_consistency(m: int, n: int, A, out: dict):
    U, V, sigma = out["U"], out["V"], out["sigma"]
    Uh = _conj_transpose(U)
    ortho_u = _max_abs_diff(_matmul(Uh, U), _identity(n))
    Vh = _conj_transpose(V)
    ortho_v = _max_abs_diff(_matmul(Vh, V), _identity(n))
    Sigma = [[sigma[i] + 0j if i == j else 0j for j in range(n)] for i in range(n)]
    recon = _matmul(_matmul(U, Sigma), Vh)
    denom = max(_max_abs(A), 1e-300)
    recon_err = _max_abs_diff(A, recon) / denom
    return ortho_u, ortho_v, recon_err


# ---------------------------------------------------------------------------
# Structural / build tests
# ---------------------------------------------------------------------------


def test_binary_builds_successfully(built: Path) -> None:
    assert built.exists() and built.is_file()


def test_toy2x2_smoke_case_is_well_formed_and_exact(
    built: Path, tmp_path: Path
) -> None:
    m, n, A = parse_case_file(DATA_DIR / "case_toy2x2.txt")
    out = _solve(built, "case_toy2x2", tmp_path)
    _validate_well_formed("case_toy2x2", m, n, out)
    ortho_u, ortho_v, recon = _self_consistency(m, n, A, out)
    assert max(ortho_u, ortho_v, recon) <= 1e-9, (
        "case_toy2x2: self-consistency too loose"
    )


def test_interface_contract_unaltered() -> None:
    header_text = (INCLUDE_DIR / "svd_types.hpp").read_text()
    assert "SvdResult compute_svd(const Matrix& A);" in header_text, (
        "compute_svd signature in include/svd_types.hpp was altered"
    )
    assert "using Cplx = std::complex<double>;" in header_text, (
        "include/svd_types.hpp: the complex scalar alias was altered"
    )
    for field in (
        "bool ok",
        "std::vector<double> singular_values",
        "Matrix U",
        "Matrix V",
        "std::string error_message",
    ):
        assert field in header_text, (
            f"include/svd_types.hpp: expected field {field!r} is missing"
        )


def test_all_public_cases_present_under_data_directory() -> None:
    for name in ALL_PUBLIC_CASE_NAMES:
        assert (DATA_DIR / f"{name}.txt").exists(), (
            f"missing expected public data file {name}.txt"
        )


def test_all_hidden_cases_present_and_not_shipped_to_agent() -> None:
    for name in ALL_HIDDEN_CASE_NAMES:
        assert (HIDDEN_DATA_DIR / f"{name}.txt").exists(), (
            f"missing expected hidden case {name}.txt"
        )
        assert not (DATA_DIR / f"{name}.txt").exists(), (
            f"{name}.txt is present under environment/data/; a hidden case must not be agent-visible"
        )


def test_case_count_meets_minimum() -> None:
    assert len(set(ALL_GRADED_CASE_NAMES)) == len(ALL_GRADED_CASE_NAMES), (
        "duplicate case name in the graded suite"
    )
    assert len(ALL_GRADED_CASE_NAMES) >= 60, (
        f"only {len(ALL_GRADED_CASE_NAMES)} graded cases, expected at least 60"
    )


# ---------------------------------------------------------------------------
# Self-consistency families (generic complex, Householder-trap, structured
# sparsity, metamorphic base matrices)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_name", SELF_CONS_PUBLIC)
def test_public_self_consistency(built: Path, tmp_path: Path, case_name: str) -> None:
    m, n, A = parse_case_file(_case_path(case_name))
    out = _solve(built, case_name, tmp_path)
    _validate_well_formed(case_name, m, n, out)
    ortho_u, ortho_v, recon = _self_consistency(m, n, A, out)
    assert max(ortho_u, ortho_v, recon) <= SELF_CONS_TOL, (
        f"{case_name}: ortho_u={ortho_u:.3e} ortho_v={ortho_v:.3e} recon={recon:.3e} "
        f"exceeds {SELF_CONS_TOL:.1e}"
    )


@pytest.mark.parametrize("case_name", SELF_CONS_HIDDEN)
def test_hidden_self_consistency(built: Path, tmp_path: Path, case_name: str) -> None:
    m, n, A = parse_case_file(_case_path(case_name))
    out = _solve(built, case_name, tmp_path)
    _validate_well_formed(case_name, m, n, out)
    ortho_u, ortho_v, recon = _self_consistency(m, n, A, out)
    assert max(ortho_u, ortho_v, recon) <= GRADE_D_TOL, (
        f"{case_name}: ortho_u={ortho_u:.3e} ortho_v={ortho_v:.3e} recon={recon:.3e} "
        f"exceeds {GRADE_D_TOL:.1e}"
    )


# D_public is graded under the tighter Householder-trap tolerance; SC/E/meta_base
# under the general self-consistency tolerance. Re-check D_public specifically.
@pytest.mark.parametrize("case_name", list(CASE_NAMES["D_public"]))
def test_public_householder_trap_case(
    built: Path, tmp_path: Path, case_name: str
) -> None:
    m, n, A = parse_case_file(_case_path(case_name))
    out = _solve(built, case_name, tmp_path)
    _validate_well_formed(case_name, m, n, out)
    ortho_u, ortho_v, recon = _self_consistency(m, n, A, out)
    assert max(ortho_u, ortho_v, recon) <= GRADE_D_TOL, (
        f"{case_name}: ortho_u={ortho_u:.3e} ortho_v={ortho_v:.3e} recon={recon:.3e} "
        f"exceeds {GRADE_D_TOL:.1e}"
    )


# ---------------------------------------------------------------------------
# Graded-spectrum family (complex unitary embedding): ground truth is the
# disclosed sigma_true used at construction time.
# ---------------------------------------------------------------------------


def _grade_b_check(built: Path, tmp_path: Path, case_name: str) -> None:
    m, n, A = parse_case_file(_case_path(case_name))
    sigma_true = [
        float(x) for x in (REF_DIR / f"{case_name}.sigma").read_text().split()
    ]
    assert len(sigma_true) == n
    out = _solve(built, case_name, tmp_path)
    _validate_well_formed(case_name, m, n, out)
    for i in range(n):
        st = sigma_true[i]
        tol = max(GRADE_B_TOL_FLOOR, GRADE_B_TOL_MULT * EPS / max(st, 1e-300))
        err = abs(out["sigma"][i] - st) / max(st, 1e-300)
        assert err <= tol, (
            f"{case_name}: singular value index {i} relative error {err:.3e} exceeds "
            f"tolerance {tol:.3e} (sigma_true={st:.3e})"
        )


@pytest.mark.parametrize("case_name", GRADE_B_PUBLIC)
def test_public_graded_spectrum_relative_accuracy(
    built: Path, tmp_path: Path, case_name: str
) -> None:
    _grade_b_check(built, tmp_path, case_name)


@pytest.mark.parametrize("case_name", GRADE_B_HIDDEN)
def test_hidden_graded_spectrum_relative_accuracy(
    built: Path, tmp_path: Path, case_name: str
) -> None:
    _grade_b_check(built, tmp_path, case_name)


# ---------------------------------------------------------------------------
# Clustered bidiagonal family: exactly bidiagonal by construction (real
# diagonal/superdiagonal), so ground truth per independent 2x2 diagonal
# block is read straight from A and computed via the closed-form formula
# above.
# ---------------------------------------------------------------------------


def _grade_c_check(built: Path, tmp_path: Path, case_name: str) -> None:
    m, n, A = parse_case_file(_case_path(case_name))
    d = [A[i][i].real for i in range(n)]
    e = [A[i][i + 1].real for i in range(n - 1)]
    closed = []
    for j in range(0, n, 2):
        ee = e[j] if j < len(e) else 0.0
        smax, smin = svd2x2_closed_form(d[j], ee, d[j + 1])
        closed.append(smax)
        closed.append(smin)
    closed_sorted = sorted(closed, reverse=True)

    out = _solve(built, case_name, tmp_path)
    _validate_well_formed(case_name, m, n, out)
    for i in range(n):
        expected = closed_sorted[i]
        got = out["sigma"][i]
        err = abs(got - expected) / max(expected, 1e-300)
        assert err <= GRADE_C_TOL, (
            f"{case_name}: singular value index {i} relative error {err:.3e} exceeds "
            f"{GRADE_C_TOL:.1e} (expected={expected:.6e}, got={got:.6e})"
        )


@pytest.mark.parametrize("case_name", GRADE_C_PUBLIC)
def test_public_clustered_bidiagonal_relative_accuracy(
    built: Path, tmp_path: Path, case_name: str
) -> None:
    _grade_c_check(built, tmp_path, case_name)


@pytest.mark.parametrize("case_name", GRADE_C_HIDDEN)
def test_hidden_clustered_bidiagonal_relative_accuracy(
    built: Path, tmp_path: Path, case_name: str
) -> None:
    _grade_c_check(built, tmp_path, case_name)


# ---------------------------------------------------------------------------
# Rank-deficient bidiagonal family: connected chain (real-valued or
# genuinely complex) with one entry planted at exactly zero. Ground truth
# is an independent 50-digit eigendecomposition of B^H B computed at
# authoring time, disclosed verbatim -- never produced by any bidiagonal-QR
# routine. An exact-zero pivot makes the ordinary trailing-2x2 Wilkinson
# shift singular; a candidate that never special-cases it either fails to
# converge within the iteration budget or reports a spurious spectrum, both
# caught below.
# ---------------------------------------------------------------------------


def _grade_f_check(built: Path, tmp_path: Path, case_name: str) -> None:
    m, n, A = parse_case_file(_case_path(case_name))
    sigma_true = [
        float(x) for x in (REF_DIR / f"{case_name}.sigma").read_text().split()
    ]
    assert len(sigma_true) == n
    out = _solve(built, case_name, tmp_path)
    _validate_well_formed(case_name, m, n, out)
    sigma_max = max(sigma_true) if sigma_true else 1.0
    for i in range(n):
        st = sigma_true[i]
        got = out["sigma"][i]
        if st == 0.0:
            err = abs(got)
            tol = 50.0 * EPS * max(sigma_max, 1.0)
        else:
            err = abs(got - st) / st
            tol = max(GRADE_B_TOL_FLOOR, GRADE_B_TOL_MULT * EPS / st)
        assert err <= tol, (
            f"{case_name}: singular value index {i} error {err:.3e} exceeds "
            f"tolerance {tol:.3e} (sigma_true={st:.3e}, got={got:.3e})"
        )


@pytest.mark.parametrize("case_name", GRADE_F_PUBLIC)
def test_public_gradeF_rank_deficient_accuracy(
    built: Path, tmp_path: Path, case_name: str
) -> None:
    _grade_f_check(built, tmp_path, case_name)


@pytest.mark.parametrize("case_name", GRADE_F_HIDDEN)
def test_hidden_gradeF_rank_deficient_accuracy(
    built: Path, tmp_path: Path, case_name: str
) -> None:
    _grade_f_check(built, tmp_path, case_name)


def _grade_f_self_consistency(built: Path, tmp_path: Path, case_name: str) -> None:
    m, n, A = parse_case_file(_case_path(case_name))
    out = _solve(built, case_name, tmp_path)
    _validate_well_formed(case_name, m, n, out)
    ortho_u, ortho_v, recon = _self_consistency(m, n, A, out)
    assert max(ortho_u, ortho_v, recon) <= GRADE_F_TOL, (
        f"{case_name}: ortho_u={ortho_u:.3e} ortho_v={ortho_v:.3e} recon={recon:.3e} "
        f"exceeds {GRADE_F_TOL:.1e}"
    )


@pytest.mark.parametrize("case_name", GRADE_F_PUBLIC)
def test_public_gradeF_self_consistency(
    built: Path, tmp_path: Path, case_name: str
) -> None:
    _grade_f_self_consistency(built, tmp_path, case_name)


@pytest.mark.parametrize("case_name", GRADE_F_HIDDEN)
def test_hidden_gradeF_self_consistency(
    built: Path, tmp_path: Path, case_name: str
) -> None:
    _grade_f_self_consistency(built, tmp_path, case_name)


# ---------------------------------------------------------------------------
# Naive-baseline divergence proxies: confirm, from the disclosed fixtures
# alone (never from the compiled binary), that each planted trap is real.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case_name", GRADE_C_PUBLIC + GRADE_C_HIDDEN)
def test_naive_absolute_deflation_reference_diverges_decisively(case_name: str) -> None:
    m, n, A = parse_case_file(_case_path(case_name))
    d = [A[i][i].real for i in range(n)]
    e = [A[i][i + 1].real for i in range(n - 1)]

    closed_true = []
    for j in range(0, n, 2):
        ee = e[j] if j < len(e) else 0.0
        smax, smin = svd2x2_closed_form(d[j], ee, d[j + 1])
        closed_true.append(smax)
        closed_true.append(smin)
    closed_true_sorted = sorted(closed_true, reverse=True)

    bnorm = max(max(abs(v) for v in d), max((abs(v) for v in e), default=0.0))
    e_wrong = list(e)
    any_wrongly_deflated = False
    for i in range(len(e)):
        if e[i] == 0.0:
            continue
        dk_thresh = 10.0 * EPS * (abs(d[i]) + abs(d[i + 1]))
        abs_thresh = 10.0 * EPS * bnorm
        if abs(e[i]) <= abs_thresh and abs(e[i]) > dk_thresh:
            e_wrong[i] = 0.0
            any_wrongly_deflated = True
    assert any_wrongly_deflated, (
        f"{case_name}: expected at least one within-cluster coupling that an "
        f"absolute/norm-relative-only deflation test would wrongly zero"
    )

    closed_wrong = []
    for j in range(0, n, 2):
        ee = e_wrong[j] if j < len(e_wrong) else 0.0
        smax, smin = svd2x2_closed_form(d[j], ee, d[j + 1])
        closed_wrong.append(smax)
        closed_wrong.append(smin)
    closed_wrong_sorted = sorted(closed_wrong, reverse=True)

    worst = max(
        abs(a - b) / max(a, 1e-300)
        for a, b in zip(closed_true_sorted, closed_wrong_sorted)
    )
    assert worst > 100 * GRADE_C_TOL, (
        f"{case_name}: wrongly-deflated reference unexpectedly close to the true spectrum "
        f"(relerr={worst:.3e}); this case would not discriminate an absolute-threshold "
        f"deflation criterion from the relative one"
    )


def _naive_givens(a, b):
    if b == 0.0:
        return 1.0, 0.0
    if a == 0.0:
        return 0.0, 1.0
    if abs(b) > abs(a):
        t = a / b
        s = 1.0 / math.sqrt(1.0 + t * t)
        c = s * t
    else:
        t = b / a
        c = 1.0 / math.sqrt(1.0 + t * t)
        s = c * t
    return c, s


def _naive_wilkinson_shift(d0, d1, e0):
    t11 = d0 * d0
    t22 = d1 * d1 + e0 * e0
    t12 = d0 * e0
    if t12 == 0.0:
        return t22
    dmid = (t11 - t22) / 2.0
    denom = (
        math.copysign(math.sqrt(dmid * dmid + t12 * t12), dmid) + dmid
        if dmid != 0.0
        else abs(t12)
    )
    return t22 - (t12 * t12) / denom


@pytest.mark.parametrize(
    "case_name",
    [
        "case_gradeF_pub_chain_start_n5",
        "case_gradeF_pub_cchain_start_n5",
        "case_gradeF_hid_chain_start_n7",
        "case_gradeF_hid_cchain_start_n7",
    ],
)
def test_naive_zero_pivot_reference_stalls_decisively(case_name: str) -> None:
    m, n, A = parse_case_file(_case_path(case_name))
    # the naive-shift stall is a real-diagonal phenomenon (the bidiagonal QR
    # phase is always real once bidiagonalization is done); genuinely
    # complex fixtures still plant an exact-zero diagonal entry, but the
    # entries surrounding it are complex, so only the STRUCTURAL fact (an
    # exact zero at the leading position) is asserted here, and the
    # decisive stall proof runs on the real-part reduction that the
    # trailing-2x2 shift actually sees once B is real.
    d0 = A[0][0]
    assert d0 == 0j, f"{case_name}: expected an exact-zero leading pivot"
    d1 = A[1][1].real
    e0 = A[0][1].real
    mu = _naive_wilkinson_shift(0.0, d1, e0)
    y = 0.0 * 0.0 - mu
    z = 0.0 * e0
    c, s = _naive_givens(y, z)
    assert (c, s) == (1.0, 0.0), (
        f"{case_name}: expected the naive shift step to degenerate to an identity "
        f"rotation at a zero leading pivot (got c={c!r}, s={s!r}); if it doesn't, "
        "this fixture no longer demonstrates the zero-pivot stall"
    )


# ---------------------------------------------------------------------------
# Metamorphic relations: compare the candidate's own two outputs, no stored
# reference required.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("base_name,derived_name", META_UNITARY)
def test_metamorphic_unitary_invariance(
    built: Path, tmp_path: Path, base_name: str, derived_name: str
) -> None:
    mb, nb, _ = parse_case_file(_case_path(base_name))
    out_base = _solve(built, base_name, tmp_path)
    _validate_well_formed(base_name, mb, nb, out_base)

    md, nd, _ = parse_case_file(_case_path(derived_name))
    out_der = _solve(built, derived_name, tmp_path)
    _validate_well_formed(derived_name, md, nd, out_der)

    worst = max(
        abs(a - b) / max(abs(a), 1e-300)
        for a, b in zip(out_base["sigma"], out_der["sigma"])
    )
    assert worst <= META_TOL, (
        f"{base_name} vs {derived_name}: unitary-invariance relative mismatch {worst:.3e} "
        f"exceeds {META_TOL:.1e}"
    )


@pytest.mark.parametrize("base_name,derived_name,cre,cim", META_SCALE)
def test_metamorphic_complex_scaling(
    built: Path,
    tmp_path: Path,
    base_name: str,
    derived_name: str,
    cre: float,
    cim: float,
) -> None:
    mb, nb, _ = parse_case_file(_case_path(base_name))
    out_base = _solve(built, base_name, tmp_path)
    _validate_well_formed(base_name, mb, nb, out_base)

    md, nd, _ = parse_case_file(_case_path(derived_name))
    out_der = _solve(built, derived_name, tmp_path)
    _validate_well_formed(derived_name, md, nd, out_der)

    k = abs(complex(cre, cim))
    worst = max(
        abs(k * a - b) / max(k * a, 1e-300)
        for a, b in zip(out_base["sigma"], out_der["sigma"])
    )
    assert worst <= META_TOL, (
        f"{base_name} x{k:.3g} vs {derived_name}: scaling relative mismatch {worst:.3e} "
        f"exceeds {META_TOL:.1e}"
    )


@pytest.mark.parametrize("base_name,derived_name", META_CONJT)
def test_metamorphic_conjugate_transpose(
    built: Path, tmp_path: Path, base_name: str, derived_name: str
) -> None:
    mb, nb, _ = parse_case_file(_case_path(base_name))
    out_base = _solve(built, base_name, tmp_path)
    _validate_well_formed(base_name, mb, nb, out_base)

    md, nd, _ = parse_case_file(_case_path(derived_name))
    out_der = _solve(built, derived_name, tmp_path)
    _validate_well_formed(derived_name, md, nd, out_der)

    worst = max(
        abs(a - b) / max(abs(a), 1e-300)
        for a, b in zip(out_base["sigma"], out_der["sigma"])
    )
    assert worst <= META_TOL, (
        f"{base_name} vs {derived_name} (conjugate transpose): relative mismatch {worst:.3e} "
        f"exceeds {META_TOL:.1e}"
    )
