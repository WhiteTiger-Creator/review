import math
import os
import re
import shutil
import struct
import subprocess
import tempfile

import pytest

APP = "/app"
TESTS = os.path.dirname(os.path.abspath(__file__))
BINARY = os.environ.get(
    "CANDIDATE_BIN", os.path.join(APP, "target", "release", "fpexp")
)

MANT_MASK = (1 << 52) - 1
QUIET = 1 << 51
POS_INF = 0x7FF0000000000000
NEG_INF = 0xFFF0000000000000
MAXFIN_POS = 0x7FEFFFFFFFFFFFFF
MAXFIN_NEG = 0xFFEFFFFFFFFFFFFF
LEAST_NORMAL = 0x0010000000000000
ALPHA = 1536

MODES = ["rne", "rna", "rtp", "rtn", "rtz"]
HANDLINGS = ["def", "wrap"]
TININESS = ["tb", "ta"]
DESTINATIONS = ["b16", "b32", "b64"]

# destination token -> (precision, emax, emin, exponent field width)
FORMATS = {
    "b16": (11, 15, -14, 5),
    "b32": (24, 127, -126, 8),
    "b64": (53, 1023, -1022, 11),
}
PACK_CODE = {"b16": ">e", "b32": ">f", "b64": ">d"}

STRATA = [
    "logb_normal",
    "logb_powers",
    "logb_subnormal",
    "logb_zero",
    "logb_inf",
    "logb_nan",
    "scalbn_exact_normal",
    "scalbn_overflow",
    "scalbn_boundary",
    "scalbn_underflow_inexact",
    "scalbn_underflow_exact",
    "scalbn_to_zero",
    "scalbn_huge_n",
    "scalbn_subnormal_input",
    "scalbn_specials",
    "scalbn_directed_overflow",
    "scalbn_directed_underflow",
    "scalbn_wrap_overflow",
    "scalbn_wrap_underflow",
    "scalbn_wrap_fallback",
    "scalbn_tininess_boundary",
    "narrow_exact",
    "narrow_round_normal",
    "narrow_tie",
    "narrow_subnormal",
    "narrow_overflow",
    "narrow_wrap",
    "narrow_wrap_inexact",
    "narrow_specials",
]

CORNER = [
    "logb_subnormal",
    "scalbn_underflow_inexact",
    "scalbn_underflow_exact",
    "scalbn_boundary",
    "scalbn_to_zero",
    "scalbn_directed_overflow",
    "scalbn_directed_underflow",
    "scalbn_wrap_overflow",
    "scalbn_wrap_underflow",
    "scalbn_wrap_fallback",
    "scalbn_tininess_boundary",
    "narrow_tie",
    "narrow_subnormal",
    "narrow_overflow",
    "narrow_wrap",
    "narrow_wrap_inexact",
    "narrow_specials",
]

FORBIDDEN = [
    "ldexp",
    "scalbln",
    "ilogb",
    "frexp",
    "libm",
    ".powi(",
    ".powf(",
    ".exp2(",
    "num-traits",
    "num_traits",
    "twofloat",
    "softfloat",
    "rustc_apfloat",
]


# ----------------------------------------------------------------------
# independent reference: integer decode of binary64, exact logb, and scalbn
# under the rounding-direction, exception-handling, and tininess-detection
# attributes named on the request
# ----------------------------------------------------------------------


def classify(word):
    return (word >> 63) & 1, (word >> 52) & 0x7FF, word & MANT_MASK


def sign_shift(dest):
    p, _, _, w = FORMATS[dest]
    return p - 1 + w


def hex_digits(dest):
    p, _, _, w = FORMATS[dest]
    return (p + w) // 4


def alpha_of(dest):
    """The clause 8.2 exponent adjustment 3 * 2^(w - 2) of a destination."""
    _, _, _, w = FORMATS[dest]
    return 3 << (w - 2)


def inf_body(dest):
    p, emax, _, _ = FORMATS[dest]
    return (2 * emax + 1) << (p - 1)


def maxfin_body(dest):
    p, emax, _, _ = FORMATS[dest]
    return ((2 * emax) << (p - 1)) | ((1 << (p - 1)) - 1)


def nan_word(dest, sign, mant):
    """Carry a binary64 NaN payload into the destination, left justified."""
    p, emax, _, _ = FORMATS[dest]
    frac = (mant >> (52 - (p - 1))) | (1 << (p - 2))
    return (sign << sign_shift(dest)) | ((2 * emax + 1) << (p - 1)) | frac


def overflow_word(sign, mode, dest="b64"):
    """The delivered datum when the magnitude is too large to represent."""
    if sign == 0:
        body = inf_body(dest) if mode in ("rne", "rna", "rtp") else maxfin_body(dest)
    else:
        body = inf_body(dest) if mode in ("rne", "rna", "rtn") else maxfin_body(dest)
    return (sign << sign_shift(dest)) | body


def _round_up(mode, sign, low, half, keep_odd):
    if low == 0:
        return False
    if mode == "rtz":
        return False
    if mode == "rtp":
        return sign == 0
    if mode == "rtn":
        return sign == 1
    if mode == "rne":
        return low > half or (low == half and keep_odd)
    return low > half or low == half  # rna


def round_unbounded(sign, m, e, p, mode):
    """Round m * 2^e to p significant bits with no exponent range limit.

    Returns the significand, the exponent of its last bit, and the loss."""
    shift = m.bit_length() - p
    if shift <= 0:
        return m << (-shift), e + shift, False
    low = m & ((1 << shift) - 1)
    q = m >> shift
    inexact = low != 0
    half = 1 << (shift - 1)
    if _round_up(mode, sign, low, half, (q & 1) == 1):
        q += 1
        if q.bit_length() > p:
            q >>= 1
            shift += 1
    return q, e + shift, inexact


def pack_normal(sign, q, e, dest):
    """Encode a p bit significand q whose last bit weighs two to the e."""
    p, emax, _, _ = FORMATS[dest]
    expfield = e + p - 1 + emax
    return (sign << sign_shift(dest)) | (expfield << (p - 1)) | (q - (1 << (p - 1)))


def encode_value(sign, m, e, mode, dest="b64"):
    """Round (-1)^sign * m * 2^e (m>0) into `dest` under `mode`.

    Returns (word, inexact, overflow, tiny_after), where tiny_after says the
    delivered magnitude lies below the smallest normal of the destination."""
    p, emax, emin, _ = FORMATS[dest]
    sbit = sign_shift(dest)
    lsig = m.bit_length()
    exp2 = e + lsig - 1
    if exp2 > emax:
        return overflow_word(sign, mode, dest), True, True, False
    ulp_exp = exp2 - (p - 1) if exp2 >= emin else emin - (p - 1)
    shift = ulp_exp - e
    if shift <= 0:
        q = m << (-shift)
        inexact = False
    elif shift >= 128:
        inexact = True
        away = (mode == "rtp" and sign == 0) or (mode == "rtn" and sign == 1)
        q = 1 if away else 0
    else:
        low = m & ((1 << shift) - 1)
        q = m >> shift
        inexact = low != 0
        half = 1 << (shift - 1)
        if _round_up(mode, sign, low, half, (q & 1) == 1):
            q += 1
    if q == 0:
        return (sign << sbit), True, False, True
    lq = q.bit_length()
    new_exp2 = ulp_exp + lq - 1
    if new_exp2 > emax:
        return overflow_word(sign, mode, dest), True, True, False
    if new_exp2 < emin:
        k = q << (ulp_exp - (emin - (p - 1)))
        return (sign << sbit) | k, inexact, False, True
    s = (p - 1) - (lq - 1)
    sig = q << s if s >= 0 else q >> (-s)
    expfield = new_exp2 + emax
    return (
        (sign << sbit) | (expfield << (p - 1)) | (sig - (1 << (p - 1))),
        inexact,
        False,
        False,
    )


def int_to_f64(v):
    if v == 0:
        return 0
    word, _, _, _ = encode_value(1 if v < 0 else 0, abs(v), 0, "rne")
    return word


def logb_op(word):
    _, exp, mant = classify(word)
    flags = [0, 0, 0, 0, 0]
    if exp == 0x7FF and mant != 0:
        if (mant & QUIET) == 0:
            flags[0] = 1
        return word | QUIET, flags
    if exp == 0x7FF:
        return POS_INF, flags
    if exp == 0 and mant == 0:
        flags[1] = 1
        return NEG_INF, flags
    e = -1074 + (mant.bit_length() - 1) if exp == 0 else exp - 1023
    return int_to_f64(e), flags


def scalbn_op(word, n, mode, handling, tininess, dest="b64"):
    sign, exp, mant = classify(word)
    p, emax, emin, _ = FORMATS[dest]
    flags = [0, 0, 0, 0, 0]
    if exp == 0x7FF and mant != 0:
        if (mant & QUIET) == 0:
            flags[0] = 1
        return nan_word(dest, sign, mant), flags
    if exp == 0x7FF:
        return (sign << sign_shift(dest)) | inf_body(dest), flags
    if exp == 0 and mant == 0:
        return sign << sign_shift(dest), flags
    if exp == 0:
        m, e = mant, -1074 + n
    else:
        m, e = mant | (1 << 52), exp - 1075 + n
    if handling == "wrap":
        a = alpha_of(dest)
        q, qe, qinexact = round_unbounded(sign, m, e, p, mode)
        wlead = qe + p - 1
        adjusted = None
        if wlead > emax and emin <= wlead - a <= emax:
            flags[2] = 1
            adjusted = qe - a
        elif wlead < emin <= wlead + a <= emax:
            flags[3] = 1
            adjusted = qe + a
        if adjusted is not None:
            if qinexact:
                flags[4] = 1
            return pack_normal(sign, q, adjusted, dest), flags
    lead = e + m.bit_length() - 1
    out, inexact, overflow, tiny_after = encode_value(sign, m, e, mode, dest)
    if overflow:
        flags[2] = 1
        flags[4] = 1
    elif inexact:
        flags[4] = 1
        if tiny_after if tininess == "ta" else lead < emin:
            flags[3] = 1
    return out, flags


def clamp_n(text):
    cap = 1 << 40
    try:
        return max(-cap, min(cap, int(text)))
    except ValueError:
        return cap if not text.startswith("-") else -cap


def expected_line(line):
    fields = line.split()
    if fields[0] == "logb":
        out, flags = logb_op(int(fields[1], 16))
        digits = 16
    else:
        out, flags = scalbn_op(
            int(fields[1], 16),
            clamp_n(fields[2]),
            fields[4],
            fields[5],
            fields[6],
            fields[3],
        )
        digits = hex_digits(fields[3])
    return f"{out:0{digits}x} {''.join(str(b) for b in flags)}"


def to_bits(f):
    return struct.unpack("<Q", struct.pack("<d", f))[0]


def to_float(bits):
    return struct.unpack("<d", struct.pack("<Q", bits))[0]


# ----------------------------------------------------------------------
# harness
# ----------------------------------------------------------------------


def read_lines(path):
    with open(path, encoding="utf-8") as handle:
        return [line.rstrip("\n") for line in handle if line.strip() != ""]


def load(stem, where=TESTS):
    base = os.path.join(where, stem)
    inputs = read_lines(base + ".in")
    expected = read_lines(base + ".expected")
    assert len(inputs) == len(expected)
    return inputs, expected


def execute(binary, lines, timeout=600):
    joined = "\n".join(lines) + "\n"
    result = subprocess.run(
        [binary],
        input=joined,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    assert result.returncode == 0, (
        f"kernel exited {result.returncode}: {result.stderr[-2000:]}"
    )
    return result.stdout.splitlines()


def build_crate(where):
    result = subprocess.run(
        ["cargo", "build", "--release", "--offline"],
        cwd=where,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert result.returncode == 0, f"build failed:\n{result.stderr[-4000:]}"
    binary = os.path.join(where, "target", "release", "fpexp")
    assert os.path.exists(binary), "release binary was not produced"
    return binary


@pytest.fixture(scope="session")
def built():
    """Build the candidate kernel once; a build failure fails every case."""
    build_crate(APP)
    assert os.path.exists(BINARY), f"candidate binary {BINARY} is missing"
    return BINARY


def build_naive(name):
    work = tempfile.mkdtemp()
    shutil.copytree(os.path.join(TESTS, name), work, dirs_exist_ok=True)
    return build_crate(work)


@pytest.fixture(scope="session")
def naive_silent():
    """The reading that computes correct values but never raises a flag."""
    return build_naive("naive_silent")


@pytest.fixture(scope="session")
def naive_stored():
    """The reading that logb's a subnormal with its stored exponent."""
    return build_naive("naive_stored")


@pytest.fixture(scope="session")
def naive_flagless():
    """The reading that emits an all zero flag mask for every request."""
    return build_naive("naive_flagless")


@pytest.fixture(scope="session")
def naive_rne():
    """The reading that ignores the mode and always rounds ties to even."""
    return build_naive("naive_rne")


@pytest.fixture(scope="session")
def naive_defonly():
    """The reading that ignores the exception-handling attribute."""
    return build_naive("naive_defonly")


@pytest.fixture(scope="session")
def naive_tinyafter():
    """The reading that always judges tininess on the delivered result."""
    return build_naive("naive_tinyafter")


@pytest.fixture(scope="session")
def naive_alpha64():
    """The reading that adjusts every destination by the binary64 amount."""
    return build_naive("naive_alpha64")


@pytest.fixture(scope="session")
def naive_b64tiny():
    """The reading that keeps the binary64 tininess threshold."""
    return build_naive("naive_b64tiny")


@pytest.fixture(scope="session")
def battery(built):
    inputs, expected = load("battery")
    strata = read_lines(os.path.join(TESTS, "battery.strata"))
    return inputs, expected, execute(built, inputs), strata


@pytest.fixture(scope="session")
def generalization(built):
    inputs, expected = load("generalization")
    strata = read_lines(os.path.join(TESTS, "generalization.strata"))
    return inputs, expected, execute(built, inputs), strata


def indices_of(strata, name):
    return [i for i, value in enumerate(strata) if value == name]


def check_stratum(bundle, name):
    inputs, expected, actual, strata = bundle
    assert len(actual) == len(expected)
    picked = indices_of(strata, name)
    assert picked, f"stratum {name} is empty"
    wrong = [i for i in picked if actual[i] != expected[i]]
    assert not wrong, (
        f"{name}: {len(wrong)} of {len(picked)} wrong, first "
        f"{inputs[wrong[0]]} -> {actual[wrong[0]]} want {expected[wrong[0]]}"
    )


# ----------------------------------------------------------------------
# reference self-consistency and cross-check
# ----------------------------------------------------------------------


def test_reference_agrees_with_ldexp_over_a_grid():
    """Round-to-nearest scalbn matches math.ldexp on every finite case."""
    checked = 0
    for mbits in [0, 1, 3, 5, 1 << 26, 1 << 51, MANT_MASK]:
        for exp in [1, 2, 700, 1022, 1023, 1500, 2046]:
            word = (exp << 52) | mbits
            for n in range(-80, 81):
                out, _ = scalbn_op(word, n, "rne", "def", "ta")
                try:
                    ref = math.ldexp(to_float(word), n)
                except OverflowError:
                    continue
                if math.isinf(ref) or ref == 0:
                    continue
                assert out == to_bits(ref), (hex(word), n)
                checked += 1
    assert checked >= 2000


def test_int_to_f64_round_trips_small_integers():
    """Encoding an integer exponent value reproduces that integer exactly."""
    for v in [*range(-1074, 1024, 7), -1074, -1023, -1, 0, 1, 1023]:
        assert to_float(int_to_f64(v)) == float(v), v


def test_logb_of_a_power_of_two_is_its_exponent():
    """logb of two to the k returns k as a floating value with no flag."""
    for k in [-5, 0, 1, 10, 100, 1000, 1023]:
        word = to_bits(2.0**k)
        out, flags = logb_op(word)
        assert to_float(out) == float(k) and flags == [0] * 5, k


def test_logb_of_smallest_subnormal_is_true_exponent():
    """logb of the least subnormal is -1074, not the format minimum exponent."""
    out, flags = logb_op(0x0000000000000001)
    assert to_float(out) == -1074.0 and flags == [0] * 5


def test_logb_of_largest_subnormal_is_minus_1023():
    """logb of the greatest subnormal recovers -1023 from the top set bit."""
    out, flags = logb_op(0x000FFFFFFFFFFFFF)
    assert to_float(out) == -1023.0 and flags == [0] * 5


def test_logb_subnormal_true_exponent_across_the_ladder():
    """Every single bit subnormal reports the position of its only set bit."""
    for pos in range(52):
        out, flags = logb_op(1 << pos)
        assert to_float(out) == float(pos - 1074) and flags == [0] * 5, pos


def test_logb_of_zero_is_negative_infinity_with_divbyzero():
    """logb of either signed zero raises DivByZero and returns -Infinity."""
    for word in (0x0000000000000000, 0x8000000000000000):
        out, flags = logb_op(word)
        assert out == NEG_INF and flags == [0, 1, 0, 0, 0]


def test_logb_of_infinity_is_positive_infinity():
    """logb of either signed infinity returns positive infinity with no flag."""
    for word in (POS_INF, NEG_INF):
        out, flags = logb_op(word)
        assert out == POS_INF and flags == [0] * 5


def test_signaling_nan_operand_raises_invalid_and_quiets():
    """A signalling NaN operand raises Invalid and is returned quieted."""
    sig = 0x7FF4000000000000
    ops = [
        logb_op(sig),
        scalbn_op(sig, 3, "rne", "def", "ta"),
        scalbn_op(sig, 3, "rtz", "wrap", "tb"),
    ]
    for out, flags in ops:
        assert flags == [1, 0, 0, 0, 0]
        assert (out & QUIET) != 0 and (out >> 52) & 0x7FF == 0x7FF


def test_quiet_nan_operand_raises_no_flag():
    """A quiet NaN operand passes through with no exception raised."""
    out, flags = logb_op(0x7FF8000000000000)
    assert out == 0x7FF8000000000000 and flags == [0] * 5


def test_scalbn_overflow_returns_infinity_with_overflow_inexact():
    """Round to nearest overflow gives a signed infinity, Overflow, ineXact."""
    out, flags = scalbn_op(0x3FF0000000000000, 2000, "rne", "def", "ta")
    assert out == POS_INF and flags == [0, 0, 1, 0, 1]
    out, flags = scalbn_op(0xBFF0000000000000, 2000, "rne", "def", "ta")
    assert out == NEG_INF and flags == [0, 0, 1, 0, 1]


def test_scalbn_exact_subnormal_raises_nothing():
    """A power of two landing exactly in the subnormal range raises no flag."""
    for mode in MODES:
        for tininess in TININESS:
            for j in [-1074, -1050, -1030, -1023]:
                out, flags = scalbn_op(0x3FF0000000000000, j, mode, "def", tininess)
                assert to_float(out) == 2.0**j and flags == [0] * 5, (mode, j)


def test_scalbn_inexact_subnormal_raises_underflow_inexact():
    """A subnormal result that drops a non zero bit raises Underflow and ineXact."""
    for tininess in TININESS:
        _, flags = scalbn_op(0x3FF0000000000001, -1074, "rne", "def", tininess)
        assert flags == [0, 0, 0, 1, 1]


def test_scalbn_half_way_subnormal_rounds_to_even():
    """Three least subnormals halved ties up to two; one halved ties down to zero."""
    out, flags = scalbn_op(0x0000000000000003, -1, "rne", "def", "ta")
    assert out == 0x0000000000000002 and flags == [0, 0, 0, 1, 1]
    out, flags = scalbn_op(0x0000000000000001, -1, "rne", "def", "ta")
    assert out == 0x0000000000000000 and flags == [0, 0, 0, 1, 1]


def test_scalbn_to_zero_raises_underflow_inexact():
    """A product rounding all the way to zero raises Underflow and ineXact."""
    out, flags = scalbn_op(0x3FF0000000000000, -4000, "rne", "def", "ta")
    assert out == 0x0000000000000000 and flags == [0, 0, 0, 1, 1]


def test_scalbn_huge_positive_n_saturates_to_infinity():
    """A very large positive scale overflows to infinity under round to nearest."""
    for n in [50000, 10**12, 10**30]:
        out, flags = scalbn_op(0x3FF0000000000000, n, "rne", "def", "ta")
        assert out == POS_INF and flags == [0, 0, 1, 0, 1]


def test_scalbn_huge_negative_n_saturates_to_zero():
    """A very large negative scale underflows to zero under round to nearest."""
    for n in [-50000, -(10**12), -(10**30)]:
        out, flags = scalbn_op(0x3FF0000000000000, n, "rne", "def", "ta")
        assert out == 0x0000000000000000 and flags == [0, 0, 0, 1, 1]


def test_scalbn_preserves_signed_zero_and_infinity():
    """Zeros and infinities are returned unchanged, sign kept, under every attribute."""
    for word in (0x0, 0x8000000000000000, POS_INF, NEG_INF):
        for mode in MODES:
            for handling in HANDLINGS:
                for n in (-100, 0, 100):
                    out, flags = scalbn_op(word, n, mode, handling, "tb")
                    assert out == word and flags == [0] * 5


def test_scalbn_by_zero_is_the_identity_on_finite_values():
    """A scale of zero returns a finite operand unchanged with no flag."""
    for word in [0x3FF0000000000000, 0x400921FB54442D18, 0x0008000000000000]:
        out, flags = scalbn_op(word, 0, "rne", "def", "ta")
        assert out == word and flags == [0] * 5


def test_scalbn_subnormal_input_can_return_to_normal_exactly():
    """Scaling the least subnormal up by 1074 yields one exactly."""
    out, flags = scalbn_op(0x0000000000000001, 1074, "rne", "def", "ta")
    assert out == 0x3FF0000000000000 and flags == [0] * 5


# ----------------------------------------------------------------------
# directed rounding
# ----------------------------------------------------------------------


def test_directed_overflow_delivers_maxfinite_or_infinity_per_mode():
    """IEEE 754 7.4: overflow returns a finite bound or infinity by mode and sign."""
    plus, minus = 0x3FF0000000000000, 0xBFF0000000000000

    def value(word, mode):
        return scalbn_op(word, 2000, mode, "def", "ta")[0]

    assert value(plus, "rtz") == MAXFIN_POS
    assert value(plus, "rtn") == MAXFIN_POS
    assert value(plus, "rtp") == POS_INF
    assert value(plus, "rne") == POS_INF
    assert value(plus, "rna") == POS_INF
    assert value(minus, "rtz") == MAXFIN_NEG
    assert value(minus, "rtp") == MAXFIN_NEG
    assert value(minus, "rtn") == NEG_INF
    assert value(minus, "rne") == NEG_INF


def test_overflow_flags_do_not_depend_on_the_mode():
    """Under default handling overflow always sets Overflow and ineXact."""
    for word in (0x3FF0000000000000, 0xBFF0000000000000):
        for mode in MODES:
            _, flags = scalbn_op(word, 3000, mode, "def", "ta")
            assert flags == [0, 0, 1, 0, 1], mode


def test_directed_rounding_lifts_a_tiny_value_off_zero():
    """A tiny positive value rounds up to the least subnormal toward +infinity."""
    plus, minus = 0x3FF0000000000000, 0xBFF0000000000000
    tiny = [0, 0, 0, 1, 1]
    assert scalbn_op(plus, -4000, "rtp", "def", "ta") == (0x1, tiny)
    assert scalbn_op(plus, -4000, "rtz", "def", "ta") == (0x0, tiny)
    assert scalbn_op(plus, -4000, "rtn", "def", "ta") == (0x0, tiny)
    assert scalbn_op(minus, -4000, "rtn", "def", "ta") == (0x8000000000000001, tiny)
    assert scalbn_op(minus, -4000, "rtp", "def", "ta") == (0x8000000000000000, tiny)


def test_subnormal_tie_breaks_follow_the_selected_mode():
    """Halving three least subnormals ties differently under each mode."""
    three = 0x0000000000000003
    assert scalbn_op(three, -1, "rne", "def", "ta")[0] == 0x2
    assert scalbn_op(three, -1, "rna", "def", "ta")[0] == 0x2
    assert scalbn_op(three, -1, "rtz", "def", "ta")[0] == 0x1
    assert scalbn_op(three, -1, "rtn", "def", "ta")[0] == 0x1
    assert scalbn_op(three, -1, "rtp", "def", "ta")[0] == 0x2


def test_exact_results_are_identical_across_all_attributes():
    """A product landing in the normal range is fixed by no attribute."""
    cases = [(0x3FF0000000000000, n) for n in (-30, -3, 0, 5, 40)]
    cases += [(0x400921FB54442D18, n) for n in (-30, -3, 0, 5, 40)]
    cases += [(0x0008000000000000, n) for n in (1, 5, 40, 900)]
    for word, n in cases:
        results = [
            scalbn_op(word, n, mode, handling, tininess)
            for mode in MODES
            for handling in HANDLINGS
            for tininess in TININESS
        ]
        assert all(r == results[0] for r in results), (hex(word), n)
        assert results[0][1] == [0] * 5


def test_rounding_up_the_largest_finite_can_carry_into_overflow():
    """Scaling the largest finite by one overflows for every rounding mode."""
    for mode in MODES:
        out, flags = scalbn_op(MAXFIN_POS, 1, mode, "def", "ta")
        assert flags == [0, 0, 1, 0, 1], mode
        assert out in (POS_INF, MAXFIN_POS)


# ----------------------------------------------------------------------
# exception handling and tininess detection: the added dimensions
# ----------------------------------------------------------------------


def test_wrapped_overflow_delivers_the_exponent_adjusted_datum():
    """Alternate handling scales an overflowing result down by the adjustment."""
    for n in (1024, 1500, 2000, 2559):
        out, flags = scalbn_op(0x3FF0000000000000, n, "rne", "wrap", "ta")
        assert out == to_bits(2.0 ** (n - ALPHA)), n
        assert flags == [0, 0, 1, 0, 0], n


def test_wrapped_underflow_delivers_the_exponent_adjusted_datum():
    """Alternate handling scales a tiny result up by the adjustment."""
    for n in (-1023, -1600, -2000, -2558):
        out, flags = scalbn_op(0x3FF0000000000000, n, "rne", "wrap", "ta")
        assert out == to_bits(2.0 ** (n + ALPHA)), n
        assert flags == [0, 0, 0, 1, 0], n


def test_wrapped_binary64_delivery_never_reports_inexact(battery):
    """A binary64 wrapped datum keeps every bit, so ineXact stays clear."""
    wrapped = 0
    for line, reply in zip(battery[0], battery[2]):
        fields = line.split()
        if fields[0] != "scalbn" or fields[5] != "wrap" or fields[3] != "b64":
            continue
        flags = reply.split()[1]
        if flags[2] == "0" and flags[3] == "0":
            continue
        if flags[4] == "0":
            wrapped += 1
        else:
            assert flags in ("00101", "00011"), line
    assert wrapped >= 12


def test_wrapped_underflow_applies_even_to_an_exact_tiny_result():
    """Alternate handling reports a tiny result whether or not it is exact."""
    one = 0x3FF0000000000000
    for n in (-1023, -1050, -1074):
        out, flags = scalbn_op(one, n, "rne", "wrap", "ta")
        assert flags == [0, 0, 0, 1, 0], n
        assert out == to_bits(2.0 ** (n + ALPHA)), n
        assert scalbn_op(one, n, "rne", "def", "ta") == (to_bits(2.0**n), [0] * 5), n


def test_wrapped_result_does_not_depend_on_the_rounding_mode():
    """The adjusted datum is exact, so every mode delivers the same bits."""
    cases = [(0x3FF0000000000000, n) for n in (2400, -2400, 1800, -1800)]
    cases += [(0xC00921FB54442D18, n) for n in (2401, -2401)]
    cases += [(0x0000000000000003, n) for n in (2200, -500)]
    for word, n in cases:
        results = [scalbn_op(word, n, mode, "wrap", "tb") for mode in MODES]
        assert all(r == results[0] for r in results), (hex(word), n)
        assert results[0][1] in ([0, 0, 1, 0, 0], [0, 0, 0, 1, 0]), (hex(word), n)


def test_alternate_handling_is_inert_when_no_condition_arises():
    """A result inside the normal range is unchanged by the handling attribute."""
    cases = [(0x3FF0000000000000, n) for n in (-40, -1, 0, 1, 12)]
    cases += [(0xC00921FB54442D18, n) for n in (-8, 0, 8)]
    cases += [(0x7FE0000000000000, n) for n in (-60, -1, 0)]
    cases += [(0x0010000000000000, n) for n in (0, 1, 60)]
    for word, n in cases:
        assert scalbn_op(word, n, "rtz", "wrap", "ta") == scalbn_op(
            word, n, "rtz", "def", "ta"
        ), (hex(word), n)


def test_a_single_adjustment_that_does_not_suffice_falls_back_to_default():
    """Beyond one adjustment the request is delivered under default handling."""
    one = 0x3FF0000000000000
    for n in (2560, 4000, 10**9):
        assert scalbn_op(one, n, "rtz", "wrap", "ta") == scalbn_op(
            one, n, "rtz", "def", "ta"
        )
    for n in (-2559, -4000, -(10**9)):
        assert scalbn_op(one, n, "rtp", "wrap", "tb") == scalbn_op(
            one, n, "rtp", "def", "tb"
        )


def test_the_adjustment_boundary_separates_wrapping_from_saturation():
    """One step either side of the boundary behaves completely differently."""
    one = 0x3FF0000000000000
    assert scalbn_op(one, 2559, "rne", "wrap", "ta") == (
        to_bits(2.0 ** (2559 - ALPHA)),
        [0, 0, 1, 0, 0],
    )
    assert scalbn_op(one, 2560, "rne", "wrap", "ta") == (POS_INF, [0, 0, 1, 0, 1])
    assert scalbn_op(one, -2558, "rne", "wrap", "ta") == (
        to_bits(2.0 ** (-2558 + ALPHA)),
        [0, 0, 0, 1, 0],
    )
    assert scalbn_op(one, -2559, "rne", "wrap", "ta") == (0x0, [0, 0, 0, 1, 1])


def test_tininess_detection_splits_the_round_up_to_least_normal_case():
    """An exact value below the least normal that rounds up onto it is tiny
    only when tininess is judged before rounding."""
    for exp in (1, 5, 700, 2046):
        word = (exp << 52) | MANT_MASK
        before = scalbn_op(word, -exp, "rne", "def", "tb")
        after = scalbn_op(word, -exp, "rne", "def", "ta")
        assert before == (LEAST_NORMAL, [0, 0, 0, 1, 1]), exp
        assert after == (LEAST_NORMAL, [0, 0, 0, 0, 1]), exp


def test_tininess_detection_agrees_when_the_result_stays_subnormal():
    """Both detections report Underflow when the delivered datum is subnormal."""
    for n in (-1074, -1080, -2000):
        before = scalbn_op(0x3FF0000000000001, n, "rne", "def", "tb")
        after = scalbn_op(0x3FF0000000000001, n, "rne", "def", "ta")
        assert before == after and before[1][3] == 1, n


def test_tininess_detection_never_changes_the_delivered_datum(battery):
    """The tininess attribute moves a flag, never a result bit."""
    checked = 0
    for line in battery[0]:
        fields = line.split()
        if fields[0] != "scalbn":
            continue
        other = " ".join([*fields[:6], "ta" if fields[6] == "tb" else "tb"])
        assert expected_line(line).split()[0] == expected_line(other).split()[0], line
        checked += 1
    assert checked >= 60


# ----------------------------------------------------------------------
# the destination format named by the request
# ----------------------------------------------------------------------

ONE = 0x3FF0000000000000
ONE_ULP_UP = 0x3FF0000000000001


def test_a_wide_significand_is_rounded_to_the_destination_precision():
    """A binary64 operand carries more bits than a narrow destination holds."""
    narrow = {"b16": (0x3C00, 0x3C01), "b32": (0x3F800000, 0x3F800001)}
    for dest, (down, up) in narrow.items():
        for mode in MODES:
            out, flags = scalbn_op(ONE_ULP_UP, 0, mode, "def", "ta", dest)
            assert out == (up if mode == "rtp" else down), (dest, mode)
            assert flags == [0, 0, 0, 0, 1], (dest, mode)
    out, flags = scalbn_op(ONE_ULP_UP, 0, "rne", "def", "ta", "b64")
    assert out == ONE_ULP_UP and flags == [0] * 5


def test_the_overflow_threshold_is_the_destination_exponent_range():
    """A magnitude that a wider destination holds still overflows a narrow one."""
    cases = [("b16", 15, 16, 0x7800), ("b32", 127, 128, 0x7F000000)]
    for dest, inside, outside, word in cases:
        out, flags = scalbn_op(ONE, inside, "rne", "def", "ta", dest)
        assert out == word and flags == [0] * 5, dest
        out, flags = scalbn_op(ONE, outside, "rne", "def", "ta", dest)
        assert out == inf_body(dest) and flags == [0, 0, 1, 0, 1], dest
        assert scalbn_op(ONE, outside, "rne", "def", "ta", "b64")[1] == [0] * 5


def test_the_subnormal_grid_is_the_destination_grid():
    """Gradual underflow starts at the least normal of the named destination."""
    assert scalbn_op(ONE, -14, "rne", "def", "ta", "b16") == (0x0400, [0] * 5)
    assert scalbn_op(ONE, -24, "rne", "def", "ta", "b16") == (0x0001, [0] * 5)
    assert scalbn_op(ONE, -25, "rne", "def", "ta", "b16") == (0x0, [0, 0, 0, 1, 1])
    assert scalbn_op(ONE, -25, "rtp", "def", "ta", "b16") == (0x1, [0, 0, 0, 1, 1])
    assert scalbn_op(ONE, -149, "rne", "def", "ta", "b32") == (0x1, [0] * 5)
    assert scalbn_op(ONE, -150, "rtz", "def", "ta", "b32") == (0x0, [0, 0, 0, 1, 1])


def test_a_tie_on_the_narrow_grid_breaks_by_the_selected_mode():
    """One plus two to the minus eleven sits midway on the binary16 grid."""
    midpoint = 0x3FF0020000000000
    want = {"rne": 0x3C00, "rna": 0x3C01, "rtp": 0x3C01, "rtn": 0x3C00, "rtz": 0x3C00}
    for mode, word in want.items():
        out, flags = scalbn_op(midpoint, 0, mode, "def", "ta", "b16")
        assert out == word and flags == [0, 0, 0, 0, 1], mode


def test_a_not_a_number_payload_is_carried_into_the_destination():
    """The payload is taken from the leading trailing significand bits."""
    signalling = 0xFFF4000000000000
    assert scalbn_op(signalling, 3, "rne", "def", "ta", "b16") == (
        0xFF00,
        [1, 0, 0, 0, 0],
    )
    assert scalbn_op(signalling, 3, "rne", "def", "ta", "b32") == (
        0xFFE00000,
        [1, 0, 0, 0, 0],
    )
    quiet = 0x7FF8000000000000
    for dest in DESTINATIONS:
        out, flags = scalbn_op(quiet, -7, "rtz", "wrap", "tb", dest)
        p, emax, _, _ = FORMATS[dest]
        assert out == ((2 * emax + 1) << (p - 1)) | (1 << (p - 2)), dest
        assert flags == [0] * 5, dest


def test_zeros_and_infinities_take_the_destination_encoding():
    """A zero or an infinity keeps its sign and changes only its width."""
    for dest in DESTINATIONS:
        sbit = sign_shift(dest)
        for n in (-900, 0, 900):
            assert scalbn_op(0x0, n, "rne", "def", "ta", dest) == (0, [0] * 5)
            assert scalbn_op(0x8000000000000000, n, "rtp", "def", "ta", dest) == (
                1 << sbit,
                [0] * 5,
            )
            assert scalbn_op(POS_INF, n, "rtz", "wrap", "tb", dest) == (
                inf_body(dest),
                [0] * 5,
            )
            assert scalbn_op(NEG_INF, n, "rtn", "def", "ta", dest) == (
                (1 << sbit) | inf_body(dest),
                [0] * 5,
            )


def test_the_adjustment_scales_with_the_exponent_field_width():
    """Clause 8.2 fixes one adjustment per format, so each destination differs."""
    assert [alpha_of(dest) for dest in DESTINATIONS] == [24, 192, 1536]
    assert scalbn_op(ONE, 16, "rne", "wrap", "ta", "b16") == (0x1C00, [0, 0, 1, 0, 0])
    assert scalbn_op(ONE, 39, "rne", "wrap", "ta", "b16") == (0x7800, [0, 0, 1, 0, 0])
    assert scalbn_op(ONE, 40, "rne", "wrap", "ta", "b16") == scalbn_op(
        ONE, 40, "rne", "def", "ta", "b16"
    )
    assert scalbn_op(ONE, -15, "rne", "wrap", "ta", "b16") == (0x6000, [0, 0, 0, 1, 0])
    assert scalbn_op(ONE, -38, "rne", "wrap", "ta", "b16") == (0x0400, [0, 0, 0, 1, 0])
    assert scalbn_op(ONE, -39, "rne", "wrap", "ta", "b16") == scalbn_op(
        ONE, -39, "rne", "def", "ta", "b16"
    )
    assert scalbn_op(ONE, 128, "rne", "wrap", "ta", "b32") == (
        0x1F800000,
        [0, 0, 1, 0, 0],
    )
    assert scalbn_op(ONE, 319, "rne", "wrap", "ta", "b32") == (
        0x7F000000,
        [0, 0, 1, 0, 0],
    )
    assert scalbn_op(ONE, 320, "rne", "wrap", "ta", "b32") == scalbn_op(
        ONE, 320, "rne", "def", "ta", "b32"
    )


def test_a_wrapped_narrow_delivery_can_report_inexact():
    """A significand too wide for the destination is rounded before it is scaled."""
    assert scalbn_op(ONE_ULP_UP, 16, "rne", "wrap", "ta", "b16") == (
        0x1C00,
        [0, 0, 1, 0, 1],
    )
    assert scalbn_op(ONE_ULP_UP, 128, "rne", "wrap", "ta", "b32") == (
        0x1F800000,
        [0, 0, 1, 0, 1],
    )
    assert scalbn_op(ONE_ULP_UP, 2000, "rne", "wrap", "ta", "b64")[1] == [0, 0, 1, 0, 0]


def test_an_exact_narrow_result_is_fixed_by_no_attribute():
    """A value the destination holds exactly ignores all three attributes."""
    for dest, span in (("b16", range(-10, 11)), ("b32", range(-100, 101, 7))):
        for k in span:
            results = [
                scalbn_op(ONE, k, mode, handling, tininess, dest)
                for mode in MODES
                for handling in HANDLINGS
                for tininess in TININESS
            ]
            assert all(r == results[0] for r in results), (dest, k)
            assert results[0][1] == [0] * 5, (dest, k)


def test_reference_agrees_with_struct_on_the_narrow_destinations():
    """Where the binary64 step is exact, packing gives one correct rounding."""
    checked = 0
    for dest, span in (("b16", range(-14, 15)), ("b32", range(-120, 121, 5))):
        p, _, _, _ = FORMATS[dest]
        stride = max(1, (1 << (p - 2)) // 60)
        for bits in range(1 << (p - 2), 1 << (p - 1), stride):
            word = (1023 << 52) | ((bits << (52 - (p - 1))) & MANT_MASK)
            for n in span:
                out, _ = scalbn_op(word, n, "rne", "def", "ta", dest)
                value = to_float(word) * (2.0**n)
                want = int.from_bytes(struct.pack(PACK_CODE[dest], value), "big")
                assert out == want, (dest, hex(word), n)
                checked += 1
    assert checked >= 2000


def test_battery_uses_every_destination_often_enough(battery):
    """No destination is a token appearing only once."""
    seen = {dest: 0 for dest in DESTINATIONS}
    for line in battery[0]:
        fields = line.split()
        if fields[0] == "scalbn":
            seen[fields[3]] += 1
    assert all(count >= 20 for count in seen.values()), seen


# ----------------------------------------------------------------------
# fixture integrity
# ----------------------------------------------------------------------


def test_battery_expected_column_matches_the_reference():
    """The frozen battery answers agree with the independent recomputation."""
    inputs, expected = load("battery")
    for line, want in zip(inputs, expected):
        assert expected_line(line) == want, line


def test_generalization_expected_column_matches_the_reference():
    """The frozen generalization answers agree with the recomputation."""
    inputs, expected = load("generalization")
    for line, want in zip(inputs, expected):
        assert expected_line(line) == want, line


@pytest.mark.parametrize(
    "name",
    [
        "sample-logb",
        "sample-scalbn",
        "sample-specials",
        "sample-subnormal",
        "sample-attributes",
        "sample-formats",
    ],
)
def test_shipped_sample_answers_match_the_reference(name):
    """Each agent visible sample file carries reference correct answers."""
    inputs, expected = load(name, os.path.join(APP, "data"))
    assert inputs, name
    for line, want in zip(inputs, expected):
        assert expected_line(line) == want, line


def test_battery_covers_every_declared_stratum():
    """No stratum label is missing from the battery."""
    assert set(read_lines(os.path.join(TESTS, "battery.strata"))) == set(STRATA)


def test_generalization_covers_every_declared_stratum():
    """The generalization fixture also exercises every stratum."""
    assert set(read_lines(os.path.join(TESTS, "generalization.strata"))) == set(STRATA)


def test_corner_mass_is_within_the_design_band():
    """Between 30 and 40 percent of battery cases sit on the graded corners."""
    strata = read_lines(os.path.join(TESTS, "battery.strata"))
    corner = sum(1 for name in strata if name in CORNER)
    assert 0.30 <= corner / len(strata) <= 0.40


def test_battery_exercises_both_operations():
    """The battery contains both logb and scalbn requests."""
    ops = {line.split()[0] for line in read_lines(os.path.join(TESTS, "battery.in"))}
    assert ops == {"logb", "scalbn"}


def test_battery_scalbn_uses_every_attribute_token():
    """Every destination, rounding, handling and tininess token appears."""
    scalbns = [
        line.split()
        for line in read_lines(os.path.join(TESTS, "battery.in"))
        if line.startswith("scalbn")
    ]
    assert {fields[3] for fields in scalbns} == set(DESTINATIONS)
    assert {fields[4] for fields in scalbns} == set(MODES)
    assert {fields[5] for fields in scalbns} == set(HANDLINGS)
    assert {fields[6] for fields in scalbns} == set(TININESS)


def test_battery_has_at_least_sixty_cases():
    """The battery clears the executed case floor comfortably."""
    assert len(read_lines(os.path.join(TESTS, "battery.in"))) >= 60


# ----------------------------------------------------------------------
# whole battery against the built kernel
# ----------------------------------------------------------------------


def test_battery_emits_one_line_per_request(battery):
    """The kernel writes exactly one line per input line."""
    inputs, _, actual, _ = battery
    assert len(actual) == len(inputs)


def test_battery_matches_the_reference_on_every_case(battery):
    """Every battery case matches bit for bit and flag for flag."""
    inputs, expected, actual, _ = battery
    wrong = [i for i in range(len(expected)) if actual[i] != expected[i]]
    assert not wrong, (
        f"{len(wrong)} of {len(expected)} wrong, first "
        f"{inputs[wrong[0]]} -> {actual[wrong[0]]} want {expected[wrong[0]]}"
    )


def test_generalization_matches_the_reference_on_every_case(generalization):
    """The fresh seed fixture matches, so tuning to the battery does not pass."""
    inputs, expected, actual, _ = generalization
    wrong = [i for i in range(len(expected)) if actual[i] != expected[i]]
    assert not wrong, (
        f"{len(wrong)} of {len(expected)} wrong, "
        f"first {inputs[wrong[0]] if wrong else ''}"
    )


@pytest.mark.parametrize("name", STRATA)
def test_battery_stratum(battery, name):
    """Each battery stratum is graded on its own so failures localise."""
    check_stratum(battery, name)


@pytest.mark.parametrize("name", STRATA)
def test_generalization_stratum(generalization, name):
    """Each generalization stratum is graded on its own."""
    check_stratum(generalization, name)


# ----------------------------------------------------------------------
# output schema
# ----------------------------------------------------------------------


def test_every_line_has_the_documented_shape(battery):
    """Each reply is the destination encoding, a space, then five flag bits."""
    pattern = re.compile(r"^[0-9a-f]+ [01]{5}$")
    for line, reply in zip(battery[0], battery[2]):
        assert pattern.match(reply), reply
        fields = line.split()
        want = 16 if fields[0] == "logb" else hex_digits(fields[3])
        assert len(reply.split()[0]) == want, (line, reply)


def test_blank_and_comment_lines_produce_no_output(built):
    """Blank lines and hash lines are skipped."""
    good = "logb 3ff0000000000000"
    assert len(execute(built, ["", "   ", "# note", good, "#tail"])) == 1


def test_malformed_lines_produce_no_output(built):
    """Lines that do not match either request form are skipped."""
    good = "scalbn 3ff0000000000000 2 b64 rne def ta"
    bad = [
        "logb",
        "logb 3ff",
        "scalbn 3ff0000000000000 2",
        "scalbn 3ff0000000000000 2 b64",
        "scalbn 3ff0000000000000 2 b64 rne",
        "scalbn 3ff0000000000000 2 b64 rne def",
        "scalbn 3ff0000000000000 2 rne def ta",
        "scalbn 3ff0000000000000 2 b8 rne def ta",
        "scalbn 3ff0000000000000 2 b64 rxx def ta",
        "scalbn 3ff0000000000000 2 b64 rne dfl ta",
        "scalbn 3ff0000000000000 2 b64 rne def tx",
        good + " extra",
        "add 1 2",
    ]
    assert len(execute(built, [*bad, good])) == 1


def test_upper_case_hexadecimal_is_accepted(built):
    """Operands may use upper case hexadecimal digits."""
    lower = execute(built, ["logb 000fffffffffffff"])
    upper = execute(built, ["logb 000FFFFFFFFFFFFF"])
    assert lower == upper == [expected_line("logb 000fffffffffffff")]


# ----------------------------------------------------------------------
# domain invariants held by the emitted results
# ----------------------------------------------------------------------


def test_logb_never_raises_overflow_underflow_or_inexact(battery):
    """No logb request sets Overflow, Underflow, or ineXact."""
    for line, reply in zip(battery[0], battery[2]):
        if line.startswith("logb"):
            flags = reply.split()[1]
            assert flags[2] == "0" and flags[3] == "0" and flags[4] == "0", line


def test_underflow_under_default_handling_carries_inexact(battery):
    """Under default handling Underflow never appears without ineXact."""
    seen = 0
    for line, reply in zip(battery[0], battery[2]):
        fields = line.split()
        if fields[0] == "scalbn" and fields[5] == "wrap":
            continue
        flags = reply.split()[1]
        if flags[3] == "1":
            assert flags[4] == "1", line
            seen += 1
    assert seen >= 8


def test_overflow_under_default_handling_carries_inexact(battery):
    """Under default handling Overflow is always accompanied by ineXact."""
    seen = 0
    for line, reply in zip(battery[0], battery[2]):
        fields = line.split()
        if fields[0] == "scalbn" and fields[5] == "wrap":
            continue
        flags = reply.split()[1]
        if flags[2] == "1":
            assert flags[4] == "1", line
            seen += 1
    assert seen >= 8


def test_overflow_and_underflow_are_never_reported_together(battery):
    """No request signals both range conditions at once."""
    for line, reply in zip(battery[0], battery[2]):
        flags = reply.split()[1]
        assert not (flags[2] == "1" and flags[3] == "1"), line


def test_divbyzero_appears_only_for_logb_of_zero(battery):
    """The DivByZero flag is set exactly on logb of a zero operand."""
    for line, reply in zip(battery[0], battery[2]):
        div = reply.split()[1][1] == "1"
        fields = line.split()
        is_logb_zero = fields[0] == "logb" and (int(fields[1], 16) & ~(1 << 63)) == 0
        assert div == is_logb_zero, line


def test_conditions_do_not_carry_between_lines(built, battery):
    """A line run on its own gives the same result as inside a batch."""
    inputs, _, actual, strata = battery
    picked = (
        indices_of(strata, "scalbn_overflow")[:5]
        + indices_of(strata, "logb_zero")[:2]
        + indices_of(strata, "scalbn_underflow_inexact")[:5]
        + indices_of(strata, "scalbn_directed_overflow")[:5]
        + indices_of(strata, "scalbn_wrap_overflow")[:5]
        + indices_of(strata, "scalbn_wrap_underflow")[:5]
        + indices_of(strata, "scalbn_tininess_boundary")[:5]
    )
    for index in picked:
        assert execute(built, [inputs[index]])[0] == actual[index], inputs[index]


def test_repeated_runs_produce_identical_output(built, battery):
    """The kernel is deterministic across runs."""
    inputs, _, actual, _ = battery
    assert execute(built, inputs) == actual


# ----------------------------------------------------------------------
# wrong reading separation and anti shortcut guards
# ----------------------------------------------------------------------


def benign_indices(strata):
    benign = ("logb_normal", "logb_powers", "scalbn_exact_normal")
    picked = []
    for name in benign:
        picked += indices_of(strata, name)
    return picked


def separation(binary, benign_must_match, failing_strata):
    """Run a wrong reading and assert where it agrees and where it breaks."""
    inputs, expected = load("battery")
    strata = read_lines(os.path.join(TESTS, "battery.strata"))
    actual = execute(binary, inputs)
    if benign_must_match:
        for index in benign_indices(strata):
            assert actual[index] == expected[index], inputs[index]
    assert actual != expected
    for name in failing_strata:
        picked = indices_of(strata, name)
        assert [i for i in picked if actual[i] != expected[i]], name


def test_naive_silent_matches_values_but_fails_the_flag_strata(naive_silent):
    """A flagless scalbn is correct on exact cases yet misses overflow and underflow."""
    separation(
        naive_silent,
        True,
        ("scalbn_overflow", "scalbn_underflow_inexact", "scalbn_to_zero"),
    )


def test_naive_stored_reading_fails_the_subnormal_logb_corner(naive_stored):
    """Reading a subnormal exponent from the stored field misses the true exponent."""
    separation(naive_stored, True, ("logb_subnormal",))


def test_naive_flagless_reading_fails_every_flag_bearing_corner(naive_flagless):
    """An all zero mask is correct on values but wrong wherever a flag is raised."""
    separation(naive_flagless, False, ("scalbn_overflow", "logb_zero", "logb_nan"))


def test_naive_rne_ignores_the_mode_and_fails_the_directed_strata(naive_rne):
    """A kernel that always rounds ties to even is right on nearest cases but
    wrong wherever the directed rounding mode changes the delivered datum."""
    separation(
        naive_rne, True, ("scalbn_directed_overflow", "scalbn_directed_underflow")
    )


def test_naive_defonly_ignores_the_handling_and_fails_the_wrap_strata(naive_defonly):
    """A kernel that only ever applies default handling saturates where the
    request asked for the exponent adjusted delivery."""
    separation(naive_defonly, True, ("scalbn_wrap_overflow", "scalbn_wrap_underflow"))


def test_naive_tinyafter_ignores_the_tininess_attribute(naive_tinyafter):
    """A kernel that always judges tininess after rounding misses the Underflow
    of an exact value that rounds up onto the least normal."""
    separation(naive_tinyafter, True, ("scalbn_tininess_boundary",))


def test_naive_alpha64_uses_one_adjustment_for_every_destination(naive_alpha64):
    """A kernel that always adjusts by the binary64 amount misses the
    adjustment the narrower destinations define."""
    separation(naive_alpha64, True, ("narrow_wrap", "narrow_wrap_inexact"))


def test_naive_b64tiny_keeps_the_binary64_tininess_threshold(naive_b64tiny):
    """A kernel that judges tininess against the binary64 least normal misses
    the Underflow of a result subnormal only in the named destination."""
    separation(naive_b64tiny, True, ("narrow_subnormal",))


def test_all_naive_readings_diverge_from_the_reference(
    naive_silent,
    naive_stored,
    naive_flagless,
    naive_rne,
    naive_defonly,
    naive_tinyafter,
    naive_alpha64,
    naive_b64tiny,
):
    """All eight plausible wrong readings score below a full pass."""
    inputs, expected = load("battery")
    for binary in (
        naive_silent,
        naive_stored,
        naive_flagless,
        naive_rne,
        naive_defonly,
        naive_tinyafter,
        naive_alpha64,
        naive_b64tiny,
    ):
        assert execute(binary, inputs) != expected


def test_manifest_declares_no_forbidden_dependency(built):
    """The kernel is written from scratch with no float shortcut crate."""
    with open(os.path.join(APP, "Cargo.toml"), encoding="utf-8") as handle:
        manifest = handle.read().lower()
    for name in FORBIDDEN:
        assert name not in manifest, name


def test_sources_do_not_reach_for_a_libm_shortcut(built):
    """No source file calls a libm scaling primitive or a float power method."""
    for root, _, names in os.walk(os.path.join(APP, "src")):
        for name in names:
            if not name.endswith(".rs"):
                continue
            with open(os.path.join(root, name), encoding="utf-8") as handle:
                body = handle.read().lower()
            for banned in FORBIDDEN:
                assert banned not in body, f"{banned} in {name}"


def test_no_vendored_crate_registry_is_present(built):
    """No offline crate registry was added to smuggle a float library in."""
    for name in (".cargo", "vendor"):
        assert not os.path.isdir(os.path.join(APP, name)), name
