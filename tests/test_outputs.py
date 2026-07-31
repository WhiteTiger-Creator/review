"""Verification suite for the warband engine.

The game is a row of raiding bands. A turn is a raid: the commander to move picks from one
band up to as many bands as the raid limit allows, all different, and takes a positive number
of soldiers off each, and whoever takes the last soldiers off the table wins. A council is a
loss for the commander to move, and so a win for SECOND, exactly when, writing every band's
strength in binary, the number of bands carrying a soldier in each place value is a multiple
of one more than the raid limit. That reading is checked here against a full game search that
knows no such rule, over small councils and several raid limits, which pins the winning
condition and where it parts from folding the strengths together as though only one band could
be raided at a turn. The tool is then run over many random and adversarial councils and its
verdict on each is matched to the reading; every FIRST raid it names is replayed and required
to strike no more bands than the limit, take a positive number off each, and land SECOND a
losing council. Hand cases pin the echo and band numbering, the empty bands, the out-of-range
councils, the skipping of junk lines, the muster-file reading and the exit codes.

The engine is always started through an unprivileged runner, and the verifier's own files are
locked to root, so the engine cannot read this reference and echo its answers back: it has to
settle the councils itself.
"""

import functools
import itertools
import os
import random
import shutil
import subprocess
import sys
import tempfile

sys.setrecursionlimit(1000000)

APP = ["ruby", "/app/main.rb"]

INT64_MIN = -(2 ** 63)
INT64_MAX = 2 ** 63 - 1

# The engine is always started through this runner, which drops to an unprivileged user
# first. The verifier's own files are root-only (test.sh locks them down), so the engine
# cannot read the reference below and echo its answers back: it has to settle the councils
# itself. HOME is pointed at a world-writable directory so the runtime has somewhere to fall
# back on while it runs as the unprivileged user.
SANDBOX = ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "--"]
_ENV = dict(os.environ, HOME="/tmp")


def sandboxed(argv, stdin_text, timeout=120.0):
    """Run argv as the unprivileged user and return the completed process."""
    return subprocess.run(SANDBOX + argv, input=stdin_text, capture_output=True,
                          check=False, text=True, timeout=timeout, env=_ENV)


def share(path):
    """Open a path up so the unprivileged runner can reach it: 0o755 for a directory,
    0o644 for a file."""
    os.chmod(path, 0o755 if os.path.isdir(path) else 0o644)
    return path


def _run(text, positions, timeout=120.0):
    """Write a muster file holding text, feed the councils in on standard input and return
    the output lines."""
    fd, path = tempfile.mkstemp(prefix="warband-", suffix=".txt")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        share(path)
        inp = "\n".join(positions) + "\n"
        p = sandboxed(APP + [path], inp, timeout=timeout)
        assert p.returncode == 0, f"warband exited {p.returncode}: {p.stderr[:500]}"
        return p.stdout.split("\n")[:-1] if p.stdout else []
    finally:
        os.unlink(path)


def run_bin(k, positions, cap=None, timeout=120.0):
    """Run a batch of councils at a campaign whose raid limit is k and whose strength cap is
    cap (None for no cap)."""
    text = f"raid: {k}\n"
    if cap is not None:
        text += f"cap: {cap}\n"
    return _run(text, positions, timeout)


def run_bin_text(text, positions, timeout=120.0):
    """Run with a raw muster-file body (for the file-parsing tests)."""
    return _run(text, positions, timeout)


# ----- the deciding rule -----------------------------------------------------


def second_wins(bands, k):
    """A council is a loss for the mover (a win for SECOND) exactly when, for every place
    value, the count of bands carrying that bit is a multiple of one more than the raid
    limit."""
    m = k + 1
    b = 0
    while any((v >> b) for v in bands):
        col = sum((v >> b) & 1 for v in bands)
        if col % m != 0:
            return False
        b += 1
    return True


def is_int_literal(s):
    """Whether the field is a whole-number literal: an optional single leading sign followed
    by one or more decimal digits."""
    if not s:
        return False
    if s[0] == "+" or s[0] == "-":
        s = s[1:]
    return len(s) > 0 and all("0" <= c <= "9" for c in s)


def parse_line(line):
    """Return the parsed band strengths (a line that produces output), or None for a line that
    is skipped: no fields, a field that is not a whole-number literal, or a field too large to
    fit a signed 64-bit integer."""
    fields = line.split()
    if not fields:
        return None
    bands = []
    for f in fields:
        if not is_int_literal(f):
            return None
        v = int(f)
        if v < INT64_MIN or v > INT64_MAX:
            return None
        bands.append(v)
    return bands


def in_range(bands, cap):
    """Whether every band sits at nought or more and, when a cap is set, no higher than it."""
    return all(not (v < 0 or (cap is not None and v > cap)) for v in bands)


def has_single_band_win(bands, k):
    """Whether some raid on a single band alone reaches a losing council. Only used on small
    bands to pin councils whose winning raid must strike more than one band."""
    for i, v in enumerate(bands):
        for j in range(v):
            nb = list(bands)
            nb[i] = j
            if second_wins(nb, k):
                return True
    return False


# ----- full game truth over small councils -----------------------------------


@functools.cache
def _wb(state, k):
    """Whether the commander to move wins, by a full search over every raid: a nonempty choice
    of at most k bands, a positive number taken off each. State is a sorted tuple of positive
    band strengths."""
    s = tuple(sorted(x for x in state if x > 0))
    if not s:
        return False
    n = len(s)
    for r in range(1, min(k, n) + 1):
        for sub in itertools.combinations(range(n), r):
            ranges = [range(s[i]) for i in sub]
            for combo in itertools.product(*ranges):
                ns = list(s)
                for j, i in enumerate(sub):
                    ns[i] = combo[j]
                if not _wb(tuple(sorted(x for x in ns if x > 0)), k):
                    return True
    return False


def win_brute(bands, k):
    """Whether the commander to move wins the council under a full game search."""
    return _wb(tuple(sorted(x for x in bands if x > 0)), k)


# ----- output validation -----------------------------------------------------


def parse_raid(move):
    """Split a reported raid into its (band number, soldiers left) clauses."""
    assert move.startswith("raid "), ("a raid must start with raid", move)
    clauses = move[len("raid "):].split(", ")
    out = []
    for c in clauses:
        parts = c.split(" ")
        assert len(parts) == 4 and parts[0] == "band" and parts[2] == "to", ("bad clause", c, move)
        out.append((int(parts[1]), int(parts[3])))
    return out


def check_output_line(line, bands, k, cap, truth=None):
    """Validate one output line against the deciding rule. For FIRST, replay the reported raid
    and require it legal and winning: at most k bands struck, a positive number off each, every
    other band left alone, landing SECOND a council whose every place count is a multiple of
    k+1."""
    assert " | " in line, ("no separator", line)
    echo, verdict = line.split(" | ", 1)
    assert echo == " ".join(str(v) for v in bands), ("echo", echo, bands)

    if not in_range(bands, cap):
        assert verdict == "ILLEGAL", ("out of range but not ILLEGAL", line, bands, cap)
        return

    want = "SECOND" if second_wins(bands, k) else "FIRST"
    if truth is not None:
        assert truth == want, ("rule disagrees with the search", bands, k, want, truth)

    if verdict == "SECOND":
        assert want == "SECOND", ("said SECOND, rule says FIRST", bands, k)
        return
    assert verdict.startswith("FIRST"), ("bad verdict", verdict, line)
    assert want == "FIRST", ("said FIRST, rule says SECOND", bands, k)
    body = verdict[len("FIRST"):]
    assert body.startswith(" "), ("FIRST must be followed by a raid", verdict)
    move = body[1:]

    clauses = parse_raid(move)
    assert 1 <= len(clauses) <= k, ("a raid strikes at least one and at most k bands", move, k)
    idxs = [i for i, _ in clauses]
    assert len(set(idxs)) == len(idxs), ("a band struck twice in one raid", move)
    new = list(bands)
    for i, j in clauses:
        assert 1 <= i <= len(bands), ("band index out of range", i, move)
        old = bands[i - 1]
        assert j >= 0, ("a band cannot be left with fewer than nought", move)
        assert j < old, ("a raid must take a positive number off each band it strikes", move, bands)
        new[i - 1] = j
    assert second_wins(new, k), ("raid does not leave SECOND a losing council", bands, k, move, new)


def check_stream(k, positions, cap=None):
    """Stream a batch of councils through the tool and check every output line."""
    got = run_bin(k, positions, cap=cap)
    seq = [p for p in (parse_line(pos) for pos in positions) if p is not None]
    assert len(got) == len(seq), ("line count", len(got), len(seq), positions[:20])
    for line, bands in zip(got, seq, strict=False):
        check_output_line(line, bands, k, cap)
    return got


def check_singles(k, positions, brute=False, cap=None):
    """Run each council on its own and check its output line, optionally against the search."""
    for pos in positions:
        got = run_bin(k, [pos], cap=cap)
        bands = parse_line(pos)
        if bands is None:
            assert got == [], ("expected no output", pos, got)
            continue
        assert len(got) == 1, ("expected one line", pos, got)
        truth = None
        if brute and in_range(bands, cap):
            truth = "FIRST" if win_brute(bands, k) else "SECOND"
        check_output_line(got[0], bands, k, cap, truth=truth)


# ----- the rule against the full game search ---------------------------------


def test_rule_matches_the_search_small():
    """The place-count reading must agree with a full game search that knows no such rule, on
    every council of up to four bands of at most six soldiers, at raid limits one, two and
    three. This pins the winning condition and that one more than the raid limit is the divisor
    that decides it."""
    for k in (1, 2, 3):
        for n in range(5):
            for combo in itertools.product(range(7), repeat=n):
                bands = list(combo)
                want = "SECOND" if second_wins(bands, k) else "FIRST"
                got = "FIRST" if win_brute(bands, k) else "SECOND"
                assert want == got, (k, bands, want, got)


def test_rule_matches_the_search_wider_limits():
    """The same agreement at wider raid limits, four and five, over up to five bands of at most
    three soldiers, so a place is carried by enough bands for the divisor to bite."""
    for k in (4, 5):
        for n in range(6):
            for combo in itertools.product(range(4), repeat=n):
                bands = list(combo)
                want = "SECOND" if second_wins(bands, k) else "FIRST"
                got = "FIRST" if win_brute(bands, k) else "SECOND"
                assert want == got, (k, bands, want, got)


# ----- the decisive small councils -------------------------------------------


def test_three_equal_bands_is_a_second_win_at_limit_two():
    """Three bands of one soldier with a raid limit of two. Folded together as though one band
    could be raided at a turn their strengths do not cancel, so that reading calls it a win for
    the mover. But a raid may fall on two bands at once, and the ones place is carried by three
    bands, a multiple of three, so the council is a loss for the mover and SECOND wins."""
    got = run_bin(2, ["1 1 1"])
    assert got == ["1 1 1 | SECOND"], got
    assert win_brute([1, 1, 1], 2) is False
    check_output_line(got[0], [1, 1, 1], 2, None, truth="SECOND")


def test_place_counts_not_the_total_at_limit_two():
    """A council whose soldiers in total sit even by three but whose ones place, carried by a
    single band, does not: bands of one, two and two at a raid limit of two. A reading that
    only weighs the whole muster calls it a loss for the mover, but the ones place gives it away
    and FIRST wins."""
    got = run_bin(2, ["1 2 2"])
    assert got[0].startswith("1 2 2 | FIRST "), got
    assert win_brute([1, 2, 2], 2) is True
    check_output_line(got[0], [1, 2, 2], 2, None, truth="FIRST")


def test_folded_reading_lands_backwards_at_limit_two():
    """Councils that folding the strengths together gets backwards once a raid may fall on more
    than one band, each run on its own and pinned by the full game search at a raid limit of
    two."""
    check_singles(2, ["1 1 1", "1 1 1 1 1", "2 2 2", "3 3 3", "1 2 3", "5 5 5", "6 6 6 6"],
                  brute=True)


def test_limit_one_is_the_folded_reading():
    """At a raid limit of one a turn falls on a single band, and the council is a loss for the
    mover exactly when folding the strengths together cancels, so the two readings agree. Pinned
    by the search."""
    check_singles(1, ["1 2 3", "1 1", "5", "3 5 6", "7 7", "0 4 4", "2 3", "8 8 8"], brute=True)


def test_same_council_flips_with_the_raid_limit():
    """One and the same council of three bands of one, read at raid limits one, two and three.
    At limit one the ones place carried by three bands is odd, so the mover wins; at limit two
    three is a multiple of three, so the mover loses; at limit three three is not a multiple of
    four, so the mover wins again."""
    assert run_bin(1, ["1 1 1"])[0].startswith("1 1 1 | FIRST "), run_bin(1, ["1 1 1"])
    assert run_bin(2, ["1 1 1"]) == ["1 1 1 | SECOND"]
    assert run_bin(3, ["1 1 1"])[0].startswith("1 1 1 | FIRST "), run_bin(3, ["1 1 1"])
    check_singles(1, ["1 1 1"], brute=True)
    check_singles(2, ["1 1 1"], brute=True)
    check_singles(3, ["1 1 1"], brute=True)


# ----- raids that must strike several bands ----------------------------------


def test_raids_may_strike_several_bands():
    """Councils at wider raid limits, some second wins and some first wins whose winning raids
    often must fall on more than one band at a stroke. Each reported line is checked against the
    rule, and any reported raid is replayed and required legal and winning."""
    check_singles(3, ["1 1 1 1", "2 2 2 2", "3 5 6", "7 8 9 10", "1 2 4 8", "15 15 15"],
                  brute=False)
    check_singles(4, ["1 1 1 1 1", "3 3 3 3", "6 10 12 20", "31 31 31 31"], brute=False)


def test_winning_raid_must_strike_several_bands():
    """Councils a first-player win whose every winning raid must strike more than one band, so a
    build that only ever raids a single band, as folding the strengths together would, cannot
    answer them. Each is confirmed to have no single-band winning raid, and the tool's raid is
    required to strike at least two bands and land a losing council."""
    cases = {
        2: ["1 1", "1 2", "1 4", "3 4", "2 5", "1 6"],
        3: ["1 1", "2 3", "4 1", "5 2", "6 4"],
        4: ["1 1", "3 5", "2 6", "7 1"],
    }
    for k, positions in cases.items():
        for pos in positions:
            bands = [int(x) for x in pos.split()]
            assert not second_wins(bands, k), (pos, k, "expected a first win")
            assert not has_single_band_win(bands, k), (pos, k, "a single-band raid wins")
            got = run_bin(k, [pos])
            assert len(got) == 1 and got[0].startswith(pos + " | FIRST "), got
            move = got[0].split(" | FIRST ", 1)[1]
            clauses = parse_raid(move)
            assert len(clauses) >= 2, ("raid must strike several bands", pos, k, move)
            check_output_line(got[0], bands, k, None)


def test_high_bit_councils_no_cap():
    """Legal councils with no cap whose bands set the very high bits of a signed 64-bit integer,
    up to the largest value that fits, at several raid limits. These exercise the top place
    values and a winning raid that must clear a high bit, which a build working in a narrower
    width or dropping the top bit gets wrong."""
    b62 = 1 << 62
    imax = (1 << 63) - 1
    cases = [
        [b62, b62 + 1, 1],
        [b62 + 5, b62 + 3, 7],
        [imax, imax - 1, 3],
        [b62, 2, 4, 8],
        [imax, imax, imax, 1],
        [b62 + 12345, 6789, b62 + 1],
    ]
    for k in (2, 3, 4, 8):
        for bands in cases:
            got = run_bin(k, [" ".join(str(v) for v in bands)])
            assert len(got) == 1, got
            check_output_line(got[0], bands, k, None)


def test_large_raid_limits():
    """Wide raid limits, six, eight and sixteen, where a place is carried by many bands and the
    divisor is large. Councils are grown from losing ones by lifting a few bands, so the winner
    turns on getting the large divisor exactly right, and every reported raid is replayed and
    required to strike no more bands than the limit."""
    rng = random.Random(90210)
    for k in (6, 8, 16):
        positions = []
        for _ in range(40):
            base = k + 1 + rng.randint(0, k)
            bands = [rng.choice([1, 3, 7, 15, 31]) for _ in range(base)]
            # lift a few bands so the council is likely a first win
            for _ in range(rng.randint(1, k)):
                i = rng.randrange(len(bands))
                bands[i] = rng.randint(0, 1 << 40)
            positions.append(" ".join(str(v) for v in bands))
        check_stream(k, positions)


def test_larger_winning_councils():
    """Larger winning councils well past any game search, run on their own and labelled by the
    place-count rule. Every reported raid is replayed to confirm it strikes at most k bands and
    lands a loss, so a build that botches the raid on bigger bands fails."""
    cases = ["1000 1 1", "1024 2048 4096", "12345 6789 1111",
             "1000000 999999 3", "700 701 3 5", "65535 65535 65535",
             "1 2 4 8 16 32", "123456789 987654321"]
    for k in (2, 3, 4):
        for case in cases:
            got = run_bin(k, [case])
            assert len(got) == 1, got
            bands = [int(x) for x in case.split()]
            check_output_line(got[0], bands, k, None)


# ----- empty bands and echo --------------------------------------------------


def test_all_empty_is_a_second_win():
    """A council whose every band is empty is a loss for the mover, who has nothing to raid, at
    any raid limit."""
    for k in (1, 2, 3):
        assert run_bin(k, ["0"]) == ["0 | SECOND"], k
        assert run_bin(k, ["0 0"]) == ["0 0 | SECOND"], k
        assert run_bin(k, ["0 0 0 0"]) == ["0 0 0 0 | SECOND"], k


def test_empty_bands_hold_their_place():
    """Empty bands are counted in the numbering and passed over by the play; the echo keeps them
    and any reported raid names the right band."""
    check_stream(3, ["0 1 0", "1 0 1", "0 2 0 3", "0 0 3", "2 0 0 2", "0 7 0", "5 0 5 0 5"])


def test_echo_normalizes_spacing_and_signs():
    """The echo is the numbers the fields spell, written back in plain decimal and joined by
    single spaces, so runs of spaces collapse, a leading zero is dropped and a leading plus goes
    away."""
    got = run_bin(2, ["  3    4  5 ", "007 0", "+3 5"])
    assert got[0].startswith("3 4 5 | "), got
    assert got[1].startswith("7 0 | "), got
    assert got[2].startswith("3 5 | "), got
    check_stream(2, ["  3    4  5 ", "007 0", "+3 5"])


def test_single_band_on_its_own_is_a_first_win():
    """A lone band of one or more soldiers is a win for the mover, who takes the whole band and
    the last soldiers with it, at any raid limit."""
    for k in (1, 2, 3):
        check_singles(k, ["1", "2", "3", "7", "12", "128", "4096"], brute=False)


# ----- out-of-range councils -------------------------------------------------


def test_over_the_cap_is_illegal():
    """A band above the campaign cap puts the council out of range: it is echoed and reported
    ILLEGAL with no verdict. Bands at or under the cap play normally."""
    got = run_bin(2, ["11", "10", "0 11", "5 20", "10 10", "3 4 5"], cap=10)
    assert got[0] == "11 | ILLEGAL", got
    assert got[1] != "10 | ILLEGAL", got
    assert got[2] == "0 11 | ILLEGAL", got
    assert got[3] == "5 20 | ILLEGAL", got
    assert got[4] != "10 10 | ILLEGAL", got
    assert got[5] != "3 4 5 | ILLEGAL", got
    check_stream(2, ["11", "10", "0 11", "5 20", "10 10", "3 4 5"], cap=10)


def test_negative_is_out_of_range_not_skipped():
    """A negative field is a whole number all the same: it is read, judged out of range, and the
    council is echoed and reported ILLEGAL. It is never treated as junk and never dropped on
    that account."""
    got = run_bin(2, ["-1", "-1 2", "3 -5 4", "0 -1"])
    assert got == ["-1 | ILLEGAL", "-1 2 | ILLEGAL", "3 -5 4 | ILLEGAL", "0 -1 | ILLEGAL"], got


def test_number_out_of_range_versus_not_a_number():
    """-1 is a number out of range and is reported; x is not a number and the line is dropped."""
    got = run_bin(2, ["-1", "x", "1 y", "1 2 2"])
    assert len(got) == 2, got
    assert got[0] == "-1 | ILLEGAL", got
    assert got[1].startswith("1 2 2 | FIRST "), got
    check_output_line(got[1], [1, 2, 2], 2, None)


def test_non_numeric_and_blank_lines_skipped():
    """Blank lines and lines carrying a field that is not a whole-number literal are dropped with
    no output. A decimal point, an underscore, a hex marker and a letter are all not literals."""
    got = run_bin(2, ["", "   ", "3 x 5", "1 2 3.0", "1_000", "0x4", "1 2 2"])
    assert len(got) == 1, got
    assert got[0].startswith("1 2 2 | FIRST "), got
    check_output_line(got[0], [1, 2, 2], 2, None)


def test_oversized_literals_are_skipped():
    """A run of digits too large to fit a signed 64-bit integer is not a whole-number literal,
    so a line carrying one is skipped with no output, the same as any other non-literal field."""
    big = "9" * 25
    got = run_bin(2, [big, "-" + big, big + " 2", "1 2 2"])
    assert len(got) == 1, got
    assert got[0].startswith("1 2 2 | FIRST "), got
    check_output_line(got[0], [1, 2, 2], 2, None)


def test_int64_boundary_literals():
    """The boundary of a signed 64-bit integer. The largest and smallest values that fit are
    whole-number literals and are read, then judged out of range under this cap; a value one past
    either end does not fit, so its line is skipped."""
    got = run_bin(2, ["9223372036854775807", "9223372036854775808",
                      "-9223372036854775808", "-9223372036854775809", "3 4"], cap=100)
    assert got[0] == "9223372036854775807 | ILLEGAL", got
    assert got[1] == "-9223372036854775808 | ILLEGAL", got
    assert got[2].startswith("3 4 | "), got
    check_output_line(got[2], [3, 4], 2, 100)


def test_malformed_signs():
    """A whole-number literal carries at most one leading sign. A doubled or crossed sign is not
    a literal, so the line is skipped. A signed zero is the number nought and plays."""
    got = run_bin(2, ["++1", "--1", "+-1", "1 +-2", "-0", "+0 0"])
    assert got == ["0 | SECOND", "0 0 | SECOND"], got


# ----- muster-file parsing ---------------------------------------------------


def test_default_raid_limit_is_one():
    """With no raid: line a turn falls on a single band, so the council is read as though the
    strengths fold together. Three bands of one then cancel to a nonzero fold and the mover
    wins."""
    got = run_bin_text("# nothing set\n", ["1 1 1"])
    assert got[0].startswith("1 1 1 | FIRST "), got
    check_output_line(got[0], [1, 1, 1], 1, None)


def test_default_is_no_cap():
    """A muster file that never sets a cap leaves every band of nought or more in range, however
    large."""
    got = run_bin_text("raid: 2\n", ["1000000 2000000"])
    assert got[0] != "1000000 2000000 | ILLEGAL", got
    check_output_line(got[0], [1000000, 2000000], 2, None)


def test_last_raid_value_wins():
    """When several lines set the raid limit the last one stands, and the verdict follows it."""
    got = run_bin_text("raid: 1\nraid: 2\n", ["1 1 1"])
    assert got == ["1 1 1 | SECOND"], got
    got = run_bin_text("raid: 2\nraid: 1\n", ["1 1 1"])
    assert got[0].startswith("1 1 1 | FIRST "), got


def test_last_cap_value_wins():
    """When several lines set the cap the last one stands, and what is in range follows it."""
    got = run_bin_text("raid: 2\ncap: 5\ncap: 100\n", ["50"])
    assert got[0].startswith("50 | FIRST "), got
    got = run_bin_text("raid: 2\ncap: 100\ncap: 5\n", ["50"])
    assert got == ["50 | ILLEGAL"], got


def test_raid_limit_ignores_bad_words():
    """A word after raid: that is not a run of digits, or that names nought, or carries a sign,
    leaves the raid limit where it stood. Absent any good value it stays at one."""
    for body in ("raid: three\n", "raid: -2\n", "raid: 0\n"):
        got = run_bin_text(body, ["1 1 1"])
        assert got[0].startswith("1 1 1 | FIRST "), (body, got)
    # the first word after raid: is the value; trailing words are ignored
    got = run_bin_text("raid: 2 bands please\n", ["1 1 1"])
    assert got == ["1 1 1 | SECOND"], got


def test_cap_ignores_non_digit_and_signed_words():
    """A word after cap: that is not a run of digits, or that carries a sign, leaves the cap
    where it stood, so a council that no cap ever took is still in range."""
    got = run_bin_text("raid: 2\ncap: five\n", ["500"])
    assert got[0] != "500 | ILLEGAL", got
    got = run_bin_text("raid: 2\ncap: -3\n", ["500"])
    assert got[0] != "500 | ILLEGAL", got


def test_comment_stripped_from_setting_lines():
    """A comment after a setting is dropped and the setting still takes, so both the raid limit
    and the cap read the same as they would with the comment gone."""
    got = run_bin_text("raid: 2   # up to two bands\ncap: 5  # small\n", ["3", "6"])
    assert got == ["3 | FIRST raid band 1 to 0", "6 | ILLEGAL"], got


def test_cap_zero_allows_only_empty_bands():
    """A cap of nought leaves only empty bands in range; any band holding a soldier puts the
    council out of range."""
    got = run_bin_text("raid: 2\ncap: 0\n", ["0", "0 0", "1", "0 1"])
    assert got == ["0 | SECOND", "0 0 | SECOND", "1 | ILLEGAL", "0 1 | ILLEGAL"], got


def test_overflow_raid_limit_is_ignored():
    """A raid: word too large to fit a signed 64-bit integer does not set the raid limit; it is
    left where it stood, here the default of one. The council 1 1 1 is then read as a single-band
    game and the mover wins."""
    got = run_bin_text("raid: 9223372036854775808\n", ["1 1 1"])
    assert got[0].startswith("1 1 1 | FIRST "), got
    check_output_line(got[0], [1, 1, 1], 1, None)
    # a good value before an overflowing one still stands
    got = run_bin_text("raid: 2\nraid: 99999999999999999999\n", ["1 1 1"])
    assert got == ["1 1 1 | SECOND"], got


def test_overflow_cap_is_ignored():
    """A cap: word too large to fit a signed 64-bit integer does not set the cap; a council that
    would be out of range under a real cap is in range when no cap ever took."""
    got = run_bin_text("raid: 2\ncap: 9223372036854775808\n", ["1000000000000"])
    assert got[0] != "1000000000000 | ILLEGAL", got
    check_output_line(got[0], [1000000000000], 2, None)


def test_council_with_a_comment_field_is_skipped():
    """A council line carries only whole-number literals. A hash is not a whole-number literal,
    so a line carrying one is skipped whole with no output, like any other non-literal field; the
    hash does not open a comment on a council line."""
    got = run_bin(2, ["1 2 # note", "1 2 2"])
    assert len(got) == 1, got
    assert got[0].startswith("1 2 2 | FIRST "), got


# ----- exit codes ------------------------------------------------------------


def test_missing_argument_exits_two():
    """Run with no muster file at all the tool writes nothing and exits 2."""
    p = sandboxed(APP, "1\n", timeout=60.0)
    assert p.returncode == 2, f"expected exit 2, got {p.returncode}"
    assert p.stdout == "", repr(p.stdout)


def test_extra_argument_exits_two():
    """Run with more than one argument the tool writes nothing and exits 2."""
    p = sandboxed(APP + ["a", "b"], "1\n", timeout=60.0)
    assert p.returncode == 2, f"expected exit 2, got {p.returncode}"
    assert p.stdout == "", repr(p.stdout)


def test_unreadable_muster_file_exits_two():
    """A muster file that cannot be opened stops the tool before any council is read: no output
    and exit 2."""
    p = sandboxed(APP + ["/no/such/muster/file"], "1\n", timeout=60.0)
    assert p.returncode == 2, f"expected exit 2, got {p.returncode}"
    assert p.stdout == "", repr(p.stdout)


def test_muster_path_that_is_a_directory_exits_two():
    """A directory handed in where a muster file belongs cannot be read, so the tool writes
    nothing and exits 2."""
    d = tempfile.mkdtemp(prefix="warband-")
    try:
        share(d)
        p = sandboxed(APP + [d], "1\n", timeout=60.0)
        assert p.returncode == 2, f"expected exit 2, got {p.returncode}"
        assert p.stdout == "", repr(p.stdout)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_good_run_exits_zero():
    """A run over a readable muster file prints one line for the one council and exits 0."""
    fd, path = tempfile.mkstemp(prefix="warband-", suffix=".txt")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write("raid: 2\ncap: 10\n")
        share(path)
        p = sandboxed(APP + [path], "1 2 2\n", timeout=60.0)
        assert p.returncode == 0, f"expected exit 0, got {p.returncode}"
        lines = p.stdout.split("\n")
        assert len(lines) == 2 and lines[1] == "", repr(p.stdout)
        assert lines[0].startswith("1 2 2 | FIRST "), repr(p.stdout)
        check_output_line(lines[0], [1, 2, 2], 2, 10)
    finally:
        os.unlink(path)


# ----- random differentials --------------------------------------------------


def rand_small(rng):
    """A short council of small band strengths, with empty bands well represented."""
    n = rng.randint(0, 6)
    return " ".join(str(rng.choice([0, 0, 1, 1, 2, 3, 4, 5, 6, 7])) for _ in range(n))


def test_random_small_streams_match_the_rule():
    """Random small councils streamed through, every verdict and raid checked against the rule.
    A folded reading, or one that mishandles the divisor, fails."""
    for k in (1, 2, 3, 4):
        rng = random.Random(1000 + k)
        positions = [rand_small(rng) for _ in range(250)]
        check_stream(k, positions)


def test_random_small_singles_match_the_search():
    """The same shape of random small councils, each run on its own, cross-checked against the
    full game search to pin the winning rule."""
    for k in (2, 3):
        rng = random.Random(5000 + k)
        positions = []
        for _ in range(120):
            n = rng.randint(0, 3)
            positions.append(" ".join(str(rng.randint(0, 5)) for _ in range(n)))
        check_singles(k, positions, brute=True)


def rand_wide(rng):
    """A council of up to nine bands drawn from a randomly chosen width, so both narrow and very
    wide strengths turn up."""
    n = rng.randint(1, 9)
    vmax = rng.choice([7, 15, 31, 63, 255, 1023, 65535, 1 << 20])
    return " ".join(str(rng.randint(0, vmax)) for _ in range(n))


def test_random_wide_streams_match_the_rule():
    """Wider councils past any game search, streamed at several raid limits: the rule labels them
    and every reported winning raid is replayed and checked."""
    for k in (2, 3, 4, 5):
        rng = random.Random(20000 + k)
        positions = [rand_wide(rng) for _ in range(150)]
        check_stream(k, positions)


def test_random_clustered_near_the_divisor():
    """Streams of small bands clustered so a place is carried by a count near a multiple of the
    divisor, where the winner is easiest to get backwards, checked against the rule."""
    for k in (2, 3):
        rng = random.Random(30000 + k)
        positions = []
        for _ in range(200):
            n = rng.randint(1, k + 2)
            positions.append(" ".join(str(rng.choice([1, 2, 3, 4, 5, 6, 7])) for _ in range(n)))
        check_stream(k, positions)


def test_random_with_a_cap_mixes_illegal():
    """Random councils at a campaign with a cap, so legal and out-of-range councils stream
    together: the line count and the ILLEGAL reports are pinned alongside the verdicts."""
    for k in (2, 3):
        rng = random.Random(40000 + k)
        positions = []
        for _ in range(150):
            n = rng.randint(1, 5)
            positions.append(" ".join(str(rng.randint(0, 560)) for _ in range(n)))
        check_stream(k, positions, cap=512)


# ----- the verifier stays out of reach ---------------------------------------


def test_engine_cannot_read_the_verifier():
    """Everything the engine runs as is barred from the verifier's files, so an engine cannot
    read this reference and print its answers instead of settling the councils. Guards the
    isolation itself: if the lockdown in test.sh ever stops taking effect, this fails rather than
    quietly letting a delegating solution through."""
    p = sandboxed(["/bin/cat", os.path.abspath(__file__)], "", timeout=30.0)
    assert p.returncode != 0, "the verifier's own test file was readable"
    assert "win_brute" not in p.stdout, "the reference leaked to the engine"
