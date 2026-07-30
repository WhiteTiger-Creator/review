"""Verification suite for the topple engine.

The game is rows of standing dominoes, each row standing in a single colour. A turn topples
one domino along its row so that domino and everything standing beyond it that way leaves the
table, Blue pushing only blue dominoes, Red only red ones and either player a grey one, and a
player with nothing left they may push has lost. A grey row that has been pushed is grey no
longer: whatever is left standing in it stands in the pusher's colour for the rest of the
position, so a grey row is not a heap sitting apart from the two colours but a row that passes
into one of them the moment it is touched.

The winners are pinned two ways that lean on nothing this file can compute. Sealed batches
carry a line count, the sha256 of the run of verdicts and a few verdicts quoted in full: the
verdict alone goes into the seal and never the named topple, since a position may be carried
by more than one topple and any of them may be named. Alongside that, every named topple is
checked legal against the rules and then replayed through the engine itself, which must call
the position it leaves a loss for the player then to move. Hand cases pin the echo and the row
numbering, the empty rows, the rows that are out of range, the lines that carry no position,
the table file and the exit codes.
"""

import hashlib
import itertools
import os
import random
import re
import shutil
import subprocess
import tempfile

APP = ["node", "--experimental-strip-types", "/app/src/main.ts"]
TOPPLE_TERM = re.compile(r"^topple row (\d+) down to (\d+)$")


def run_bin(limit, positions, timeout=180.0):
    """Play a batch of positions at a table with the given row limit (None for no limit)
    and return the output lines."""
    text = "" if limit is None else f"rowlimit: {limit}\n"
    return _run(text, positions, timeout)


def run_bin_text(text, positions, timeout=180.0):
    """Play with a raw table-file body (for the table-file tests)."""
    return _run(text, positions, timeout)


def _run(text, positions, timeout):
    root = tempfile.mkdtemp(prefix="topple-")
    try:
        path = os.path.join(root, "table.txt")
        with open(path, "w") as fh:
            fh.write(text)
        inp = "\n".join(positions) + "\n"
        p = subprocess.run(APP + [path], input=inp, capture_output=True, check=False,
                           text=True, timeout=timeout)
        assert p.returncode == 0, f"topple exited {p.returncode}: {p.stderr[:500]}"
        return p.stdout.split("\n")[:-1] if p.stdout else []
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ----- reading a position ----------------------------------------------------


def foe(player):
    """The player who is not this one."""
    return "red" if player == "blue" else "blue"


def read_line(line):
    """Read one input line. Returns None when the line carries no position at all, and
    otherwise the player to move, the echoed fields, the rows and whether any row stands in
    more than one colour. A row is a pair of its colour and its length, and an empty row is
    a pair of None and nought."""
    fields = line.split()
    if not fields:
        return None
    mover = fields[0].lower()
    if mover not in ("blue", "red"):
        return None
    echo = [mover]
    rows = []
    mixed = False
    for f in fields[1:]:
        w = f.lower()
        if w == ".":
            echo.append(w)
            rows.append((None, 0))
            continue
        for c in w:
            if c not in "brg":
                return None
        echo.append(w)
        if len(set(w)) > 1:
            mixed = True
            rows.append((None, 0))
            continue
        rows.append((w[0], len(w)))
    return mover, echo, rows, mixed


def out_of_range(rows, mixed, limit):
    """Whether the position holds a row that is no legal row at this table."""
    if mixed:
        return True
    if limit is None:
        return False
    return any(c is not None and n > limit for c, n in rows)


def can_push(row, player):
    """Whether the player is allowed to push a domino in this row."""
    c, n = row
    if n <= 0 or c is None:
        return False
    if c == "g":
        return True
    if c == "b":
        return player == "blue"
    return player == "red"


def after_topple(rows, idx, left, mover):
    """The rows that stand after the mover topples row idx (numbered from one) down to left
    dominoes. A grey row toppled into stands in the mover's colour afterwards."""
    c, _n = rows[idx - 1]
    if c == "g":
        c = "b" if mover == "blue" else "r"
    out = list(rows)
    out[idx - 1] = (c, left) if left > 0 else (None, 0)
    return out


def write_position(rows, mover):
    """An input line for these rows with this player to move."""
    fields = [mover]
    for c, n in rows:
        fields.append("." if c is None or n == 0 else c * n)
    return " ".join(fields)


def verdict_of(out):
    """The winner's word (or ILLEGAL) from one output line."""
    return out.split(" | ")[1].split(" ")[0]


def verdict_line(out):
    """One output line with the named topple, if any, dropped: the echo and the verdict word
    alone. This is what the seals below are taken over, since more than one topple may carry a
    position and any of them may be named."""
    head, _, rest = out.partition(" | ")
    return head + " | " + rest.split(" ")[0]


def digest(outs):
    """The sha256 of a run of verdicts, the named topples left out."""
    h = hashlib.sha256()
    for out in outs:
        h.update((verdict_line(out) + "\n").encode())
    return h.hexdigest()


# ----- checking the shape of a run -------------------------------------------


def check_shape(outs, positions, limit):
    """Check that exactly the lines carrying a position produced output, that each echo is
    right, and that each verdict is well formed: ILLEGAL for a position holding a row out of
    range, one of the two players otherwise, a topple named when and only when the winner is
    the player to move, and that topple legal at the position it is named for."""
    played = [p for p in positions if read_line(p) is not None]
    assert len(outs) == len(played), (
        f"got {len(outs)} output lines for {len(played)} positions")
    for out, line in zip(outs, played, strict=False):
        mover, echo, rows, mixed = read_line(line)
        head = " ".join(echo) + " | "
        assert out.startswith(head), f"echo wrong for {line!r}: got {out!r}, wanted {head!r}"
        verdict = out[len(head):]

        if out_of_range(rows, mixed, limit):
            assert verdict == "ILLEGAL", f"{line!r} is out of range but reported {verdict!r}"
            continue

        parts = verdict.split(" ", 1)
        assert parts[0] in ("BLUE", "RED"), f"bad verdict {verdict!r} for {line!r}"
        if parts[0] != mover.upper():
            assert len(parts) == 1, (
                f"{line!r} is not won by the player to move but a topple was named: "
                f"{verdict!r}")
            continue

        assert len(parts) == 2, f"{line!r} is won by the mover but no topple was named"
        m = TOPPLE_TERM.match(parts[1])
        assert m, f"badly written topple {parts[1]!r} for {line!r}"
        idx = int(m.group(1))
        left = int(m.group(2))
        assert 1 <= idx <= len(rows), f"row {idx} out of the position for {line!r}"
        row = rows[idx - 1]
        assert can_push(row, mover), f"{mover} may not push in row {idx} of {line!r}"
        assert 0 <= left < row[1], (
            f"row {idx} of {line!r} holds {row[1]} and cannot be left at {left}")


def replay_named_topples(outs, positions, limit, timeout=180.0):
    """Play every named topple out and hand the position it leaves back to the engine with
    the other player to move. The engine must call each of those a loss for the player then to
    move, that is, report the first mover as the winner with no topple of their own named."""
    played = [p for p in positions if read_line(p) is not None]
    follow = []
    want = []
    for out, line in zip(outs, played, strict=False):
        mover, _echo, rows, mixed = read_line(line)
        if out_of_range(rows, mixed, limit):
            continue
        parts = out.split(" | ")[1].split(" ", 1)
        if parts[0] != mover.upper():
            continue
        m = TOPPLE_TERM.match(parts[1])
        assert m, f"badly written topple {parts[1]!r} for {line!r}"
        after = after_topple(rows, int(m.group(1)), int(m.group(2)), mover)
        follow.append(write_position(after, foe(mover)))
        want.append((line, parts[1], mover.upper()))
    if not follow:
        return
    outs2 = run_bin(limit, follow, timeout=timeout)
    assert len(outs2) == len(follow), f"{len(outs2)} lines back for {len(follow)} positions"
    for out2, line2, (line, move, winner) in zip(outs2, follow, want, strict=False):
        got = out2.split(" | ")[1]
        assert got == winner, (
            f"the topple {move!r} named for {line!r} leaves {line2!r}, "
            f"which the engine calls {got!r} and not a loss for the player to move")


# ----- the sealed batches ----------------------------------------------------


def _positions_small():
    """Every small mixture of rows, up to three rows drawn from the short rows of each
    colour, both players to move."""
    rows = [(c, n) for c in "brg" for n in (1, 2, 3)]
    combos = [list(combo)
              for k in (0, 1, 2, 3)
              for combo in itertools.combinations_with_replacement(rows, k)]
    return [(mover + " " + " ".join(c * n for c, n in combo)).strip()
            for combo in combos
            for mover in ("blue", "red")]


def _positions_wider():
    """Up to four rows drawn from rows of up to five dominoes, where several grey rows stand
    together and the sharing out of them decides the position."""
    rows = [(c, n) for c in "brg" for n in range(1, 6)]
    combos = [list(combo)
              for k in (1, 2, 3, 4)
              for combo in itertools.combinations_with_replacement(rows, k)]
    return [mover + " " + " ".join(c * n for c, n in combo)
            for combo in combos
            for mover in ("blue", "red")]


def _positions_twolong():
    """Up to two rows of up to six dominoes."""
    rows = [(c, n) for c in "brg" for n in range(1, 7)]
    return [mover + " " + " ".join(c * n for c, n in combo)
            for k in (1, 2)
            for combo in itertools.combinations_with_replacement(rows, k)
            for mover in ("blue", "red")]


def _positions_greyheavy():
    """Positions built mostly of grey rows, where the sharing out of them is the whole
    question."""
    greys = [("g", n) for n in range(1, 5)]
    colours = [("b", n) for n in (1, 2, 3)] + [("r", n) for n in (1, 2, 3)]
    return [mover + " " + " ".join(c * n for c, n in combo)
            for k in (2, 3, 4)
            for combo in itertools.combinations_with_replacement(greys + colours, k)
            if sum(1 for c, _ in combo if c == "g") >= 2
            for mover in ("blue", "red")]


def rand_row(rng, top):
    """A random row of one colour, up to top dominoes long."""
    c = rng.choice("bbrrgggg")
    return c * rng.randint(1, top)


def rand_position(rng, rows, top):
    """A random position of up to rows rows, each up to top dominoes long."""
    n = rng.randint(0, rows)
    fields = []
    for _ in range(n):
        if rng.random() < 0.08:
            fields.append(".")
        else:
            fields.append(rand_row(rng, top))
    return rng.choice(["blue", "red"]) + " " + " ".join(fields)


def _positions_tiny_random():
    """Random tiny positions."""
    rng = random.Random(90210)
    return [rand_position(rng, 3, 3) for _ in range(150)]


def _positions_small_random():
    """Random positions of a few short rows."""
    rng = random.Random(1337)
    return [rand_position(rng, 4, 4) for _ in range(120)]


def _positions_grey_random():
    """Random positions of grey rows only, where the sharing out settles everything."""
    rng = random.Random(24680)
    out = []
    for _ in range(120):
        k = rng.randint(1, 5)
        fields = ["g" * rng.randint(1, 5) for _ in range(k)]
        out.append(rng.choice(["blue", "red"]) + " " + " ".join(fields))
    return out


def _positions_wide_random():
    """Wide positions far past any game search."""
    rng = random.Random(4242)
    return [rand_position(rng, 8, 60) for _ in range(150)]


def _positions_level():
    """Random positions built to hold the two colours level, so the grey rows alone settle
    them and the player to move matters."""
    rng = random.Random(70707)
    out = []
    for _ in range(150):
        k = rng.randint(1, 4)
        fields = []
        for _ in range(k):
            n = rng.randint(1, 20)
            fields.append("b" * n)
            fields.append("r" * n)
        fields.extend("g" * rng.randint(1, 20) for _ in range(rng.randint(0, 3)))
        rng.shuffle(fields)
        out.append(rng.choice(["blue", "red"]) + " " + " ".join(fields))
    return out


def _positions_near_level():
    """Random positions a domino or two off level, where the grey rows are large and the
    colours nearly cancel."""
    rng = random.Random(31415)
    out = []
    for _ in range(150):
        b = rng.randint(1, 20)
        d = rng.choice([-2, -1, 0, 1, 2])
        r = max(1, b + d)
        fields = ["b" * b, "r" * r]
        fields.extend("g" * rng.randint(1, 40) for _ in range(rng.randint(1, 3)))
        rng.shuffle(fields)
        out.append(rng.choice(["blue", "red"]) + " " + " ".join(fields))
    return out


def _positions_many_grey():
    """Random positions carrying a crowd of grey rows of nearly the same length, where the
    order they are shared out in decides the position."""
    rng = random.Random(515151)
    out = []
    for _ in range(120):
        k = rng.randint(2, 9)
        base = rng.randint(1, 30)
        fields = ["g" * max(1, base + rng.randint(-1, 1)) for _ in range(k)]
        if rng.random() < 0.5:
            fields.append("b" * rng.randint(1, 5))
        if rng.random() < 0.5:
            fields.append("r" * rng.randint(1, 5))
        rng.shuffle(fields)
        out.append(rng.choice(["blue", "red"]) + " " + " ".join(fields))
    return out


def _positions_crowd():
    """Positions carrying hundreds of rows at once, most of them grey and many of a length,
    so the whole crowd has to be shared out and not weighed one row at a time."""
    rng = random.Random(808080)
    out = []
    for _ in range(12):
        fields = []
        for _ in range(rng.randint(200, 600)):
            c = rng.choice("bbrrgggggg")
            fields.append(c * rng.randint(1, 200))
        out.append(rng.choice(["blue", "red"]) + " " + " ".join(fields))
    for _ in range(4):
        fields = ["g" * rng.randint(40, 44) for _ in range(2000)]
        out.append(rng.choice(["blue", "red"]) + " " + " ".join(fields))
    return out


def _positions_limited():
    """Random positions at a table with a limit, so legal and out-of-range positions arrive
    mixed together."""
    rng = random.Random(606060)
    return [rand_position(rng, 5, 40) for _ in range(150)]


BATCHES = {
    "small": (None, _positions_small),
    "wider": (None, _positions_wider),
    "twolong": (None, _positions_twolong),
    "greyheavy": (None, _positions_greyheavy),
    "tiny_random": (None, _positions_tiny_random),
    "small_random": (None, _positions_small_random),
    "grey_random": (None, _positions_grey_random),
    "wide_random": (None, _positions_wide_random),
    "level": (None, _positions_level),
    "near_level": (None, _positions_near_level),
    "many_grey": (None, _positions_many_grey),
    "crowd": (None, _positions_crowd),
    "limited": (24, _positions_limited),
}

# BEGIN SEALS
SEALS = {
    "small": {
        "lines": 440,
        "sha256": "421d1d0ed9c1ded668b03877ca12493f8171de1ed8cd3255c2259ce380ffb02c",
        "spot": [
            [0, 'blue | RED'],
            [146, 'blue b bbb r | BLUE'],
            [293, 'red bbb r g | BLUE'],
            [439, 'red ggg ggg ggg | RED'],
        ],
    },
    "wider": {
        "lines": 7750,
        "sha256": "9bd05717cd2639a16a38984defcfb745a9172c0f821bf97215577a7c389b46dc",
        "spot": [
            [0, 'blue b | BLUE'],
            [2583, 'red b r rr ggg | RED'],
            [5166, 'blue bbbb bbbb ggg gggg | BLUE'],
            [7749, 'red ggggg ggggg ggggg ggggg | BLUE'],
        ],
    },
    "twolong": {
        "lines": 378,
        "sha256": "56cf2fdab16baf24ba02b3f591eb4cb5a2210ffa9573cfbd4e5def593695e229",
        "spot": [
            [0, 'blue b | BLUE'],
            [126, 'blue bbb g | BLUE'],
            [252, 'blue rr rrrrr | RED'],
            [377, 'red gggggg gggggg | BLUE'],
        ],
    },
    "greyheavy": {
        "lines": 910,
        "sha256": "255cb913a2cc2587ca985938c89f02f68fc906c6dbfacab2f79f7a11fe068815",
        "spot": [
            [0, 'blue g g | RED'],
            [303, 'red g gg gg r | RED'],
            [606, 'blue gg ggg ggg bbb | BLUE'],
            [909, 'red gggg gggg rrr rrr | RED'],
        ],
    },
    "tiny_random": {
        "lines": 150,
        "sha256": "228dc92db27b77ac8373d6ba1b395dd0de53511e7a64a9bd65382df694a3e2fc",
        "spot": [
            [0, 'blue | RED'],
            [50, 'blue rr | RED'],
            [100, 'blue . b g | BLUE'],
            [149, 'blue gg gg rrr | RED'],
        ],
    },
    "small_random": {
        "lines": 120,
        "sha256": "815a99a1e9fecde2f19a26ef56839bb86baa9cf41e791f399ce73016b3958d99",
        "spot": [
            [0, 'blue gg gggg ggg rrr | RED'],
            [40, 'red | BLUE'],
            [80, 'red gg g gg gggg | RED'],
            [119, 'red rrr r b rrrr | RED'],
        ],
    },
    "grey_random": {
        "lines": 120,
        "sha256": "0b9d08cbcfe37f046a7524fd9313e2c7dd7d166f25e542d421080b16cfc0dcfb",
        "spot": [
            [0, 'red ggggg ggg g gg | RED'],
            [40, 'red ggggg ggg ggg | RED'],
            [80, 'blue gg ggggg | BLUE'],
            [119, 'blue ggggg g | BLUE'],
        ],
    },
    "wide_random": {
        "lines": 150,
        "sha256": "b267a9a1876ba3a6e0ca131c6459e65d8ca615366e84922099851241c26e795f",
        "spot": [
            [50, 'red rrrrr | RED'],
            [100, 'red gggggggggggg rrrrrrrrrrrrrr g | RED'],
            [149, 'blue gggggggggggggggggggggggggggggg | BLUE'],
        ],
    },
    "level": {
        "lines": 150,
        "sha256": "5f795d12f546dda172b15a726f57bc16433bb3f6dfcd3fc6b1f70c201906bfa5",
        "spot": [
            [50, 'red gggggggggg rrrrrrrrrrrrrrr bbbbbbbbbbbbbbb | RED'],
        ],
    },
    "near_level": {
        "lines": 150,
        "sha256": "a45fb9d73a5b720cd52777dd96deda464aa26341aa6c7c9c1ee8586da900d16a",
        "spot": [
            [100, 'red rrrrrrrrrrrr ggggggggggg bbbbbbbbbb | RED'],
            [149, 'red rrrrrrrrrrrr bbbbbbbbbbb gggggggggggggggggggggg | RED'],
        ],
    },
    "many_grey": {
        "lines": 120,
        "sha256": "721a80e9824ea616f1e719a6758c6aee8e1f0deb54ef451deee8b58fe69bd2eb",
        "spot": [
            [0, 'blue gggg ggggg gggggg bbb gggggg gggggg rrrr ggggg | BLUE'],
            [80, 'red rrrr ggggg ggggg ggg ggg ggggg | RED'],
            [119, 'blue ggg gggg ggggg ggggg gggg bbbb rr | BLUE'],
        ],
    },
    "crowd": {
        "lines": 16,
        "sha256": "9052515df826d984298bfc51c2ff367d34097f11d925450a824ee769ab7ad461",
        "spot": [
        ],
    },
    "limited": {
        "lines": 150,
        "sha256": "b20562e0d435f31c0348f6d8736d3f85d069978cfa0c3889a5cb326ebb2125dd",
        "spot": [
            [0, 'blue ggggggggggggggggggggggggggggggggggg ggggggggggggg | ILLEGAL'],
            [100, 'red . ggggggggggggggg | RED'],
        ],
    },
}
# END SEALS


def check_sealed(name, replay=True, timeout=180.0):
    """Play a sealed batch and require the run to match the seal, the shape of every line to
    be right, and every named topple to beat the other player."""
    limit, build = BATCHES[name]
    positions = build()
    outs = run_bin(limit, positions, timeout=timeout)
    seal = SEALS[name]
    assert len(outs) == seal["lines"], (
        f"batch {name} gave {len(outs)} lines and not {seal['lines']}")
    for i, want in seal["spot"]:
        assert verdict_line(outs[i]) == want, (
            f"batch {name} line {i}: got {outs[i]!r}, wanted {want!r}")
    check_shape(outs, positions, limit)
    assert digest(outs) == seal["sha256"], (
        f"batch {name} does not settle the positions as the rules call them")
    if replay:
        replay_named_topples(outs, positions, limit, timeout=timeout)


def test_small_positions():
    """Every small mixture of up to three short rows, both players to move, settled as the
    rules call it, with every named topple replayed."""
    check_sealed("small")


def test_wider_positions():
    """Up to four rows of up to five dominoes, where several grey rows have to be shared
    out."""
    check_sealed("wider")


def test_two_longer_rows():
    """Up to two rows of up to six dominoes."""
    check_sealed("twolong")


def test_grey_heavy_positions():
    """Positions built mostly of grey rows, where the sharing out of them settles the
    table."""
    check_sealed("greyheavy")


def test_random_tiny_positions():
    """Random tiny positions."""
    check_sealed("tiny_random")


def test_random_small_positions():
    """Random positions of a few short rows."""
    check_sealed("small_random")


def test_random_grey_only_positions():
    """Random positions of grey rows alone."""
    check_sealed("grey_random")


def test_random_wide_positions():
    """Wide positions far past any game search, every named topple replayed."""
    check_sealed("wide_random")


def test_random_level_tables():
    """Random positions holding the two colours level, so the grey rows alone settle them."""
    check_sealed("level")


def test_random_near_level_tables():
    """Random positions a domino or two off level, with large grey rows."""
    check_sealed("near_level")


def test_random_many_grey_rows_of_close_length():
    """Random positions carrying a crowd of grey rows of nearly the same length."""
    check_sealed("many_grey")


def test_a_crowd_of_rows_on_one_line():
    """Positions carrying hundreds of rows at once, most of them grey and many of a
    length."""
    check_sealed("crowd", timeout=300.0)


def test_random_positions_with_a_limit():
    """Random positions at a table with a limit, so legal and out-of-range positions arrive
    mixed together and the line count is pinned alongside the verdicts."""
    check_sealed("limited")


# ----- the close positions ---------------------------------------------------


def test_a_grey_row_can_rescue_the_player_a_domino_behind():
    """One red domino against a grey row of two, Blue to move. Blue is behind and cannot touch
    the red row, but the grey row is Blue's to take and it levels the table with Red left to
    move."""
    lines = ["blue r gg", "red b gg", "blue rr ggg", "red bb ggg"]
    outs = run_bin(None, lines)
    assert verdict_of(outs[0]) == "BLUE", outs[0]
    assert verdict_of(outs[1]) == "RED", outs[1]
    assert verdict_of(outs[2]) == "BLUE", outs[2]
    assert verdict_of(outs[3]) == "RED", outs[3]
    check_shape(outs, lines, None)
    replay_named_topples(outs, lines, None)


def test_a_lone_grey_domino_rescues_nobody():
    """A grey row of one is a turn and nothing more: whoever pushes it is left no better off,
    so the player a domino behind stays beaten."""
    lines = ["blue r g", "red b g", "blue rr g", "red bb g"]
    outs = run_bin(None, lines)
    assert verdict_of(outs[0]) == "RED", outs[0]
    assert verdict_of(outs[1]) == "BLUE", outs[1]
    assert verdict_of(outs[2]) == "RED", outs[2]
    assert verdict_of(outs[3]) == "BLUE", outs[3]
    check_shape(outs, lines, None)


def test_the_longer_grey_row_goes_first():
    """Two grey rows of different lengths on a bare table. The player to move comes out ahead,
    and would come out behind by starting with the shorter row."""
    lines = ["blue g gg", "red g gg", "blue gg gggg", "red gggg gg",
             "blue g ggg", "red ggg g"]
    outs = run_bin(None, lines)
    for out, line in zip(outs, lines, strict=False):
        mover = read_line(line)[0]
        assert verdict_of(out) == mover.upper(), out
    check_shape(outs, lines, None)
    replay_named_topples(outs, lines, None)


def test_two_grey_rows_of_a_length_cancel():
    """Two grey rows of the same length go one to each player and leave the table as it stood,
    so the player to move is the one who runs out of turns."""
    lines = ["blue gg gg", "red ggg ggg", "blue b r gggg gggg"]
    outs = run_bin(None, lines)
    assert outs == [
        "blue gg gg | RED",
        "red ggg ggg | BLUE",
        "blue b r gggg gggg | RED",
    ], outs


def test_folding_every_row_alike_lands_backwards():
    """Positions where folding the row lengths together without regard to colour names the
    wrong player."""
    cases = [
        ("blue rr", "RED"),
        ("red bbb", "BLUE"),
        ("red bb r ggg", "RED"),
        ("blue ggg gg g", "BLUE"),
        ("red ggg gg g", "RED"),
        ("blue bbb rrrr g", "RED"),
    ]
    outs = run_bin(None, [c[0] for c in cases])
    for (line, want), out in zip(cases, outs, strict=False):
        mover, _echo, rows, _mixed = read_line(line)
        fold = 0
        for _c, n in rows:
            fold ^= n
        folded = mover if fold else foe(mover)
        assert folded.upper() != want, f"{line} does not separate the fold"
        assert verdict_of(out) == want, f"{line} should be won by {want}, got {out!r}"


def test_holding_the_grey_rows_apart_lands_backwards():
    """Positions where counting the colours against one another and settling the grey rows on
    their own, as though no grey row ever changed hands, names the wrong player."""
    cases = [
        ("blue r gg", "BLUE"),
        ("red b gg", "RED"),
        ("blue r ggg", "BLUE"),
        ("blue rr ggg", "BLUE"),
        ("red bb ggg", "RED"),
        ("blue rrr gggg", "BLUE"),
        ("blue bbb rrrr gg", "BLUE"),
        ("red rrr bbbb gg", "RED"),
        ("blue bb rrrr ggg", "BLUE"),
        ("blue bb rrr ggg", "BLUE"),
        ("blue ggg gg g", "BLUE"),
        ("red ggg gg g", "RED"),
    ]
    outs = run_bin(None, [c[0] for c in cases])
    for (line, want), out in zip(cases, outs, strict=False):
        mover, _echo, rows, _mixed = read_line(line)
        lead = 0
        grey = 0
        for c, n in rows:
            if c == "b":
                lead += n
            elif c == "r":
                lead -= n
            elif c == "g":
                grey ^= n
        if lead > 0:
            apart = "blue"
        elif lead < 0:
            apart = "red"
        else:
            apart = mover if grey else foe(mover)
        assert apart.upper() != want, f"{line} does not separate the split reading"
        assert verdict_of(out) == want, f"{line} should be won by {want}, got {out!r}"


def test_a_grey_row_is_worth_one_less_than_it_stands():
    """A player a domino behind cannot mend it with a lone grey domino but can with a grey row
    of two, and a player two behind needs a grey row of three."""
    lines = ["blue bbb rrrr g", "blue bbb rrrr gg", "blue bbb rrrr ggg",
             "red rrr bbbb g", "red rrr bbbb gg", "red rrr bbbb ggg",
             "blue bb rrrr gg", "blue bb rrrr ggg"]
    want = ["RED", "BLUE", "BLUE", "BLUE", "RED", "RED", "RED", "BLUE"]
    outs = run_bin(None, lines)
    for out, w in zip(outs, want, strict=False):
        assert verdict_of(out) == w, out
    check_shape(outs, lines, None)
    replay_named_topples(outs, lines, None)


def test_an_odd_count_of_grey_rows_turns_the_table_round():
    """When the grey rows are shared out and leave the table level, who is left to move once
    the last of them is gone turns on how many grey rows stood, and not on what they held."""
    lines = ["blue gg gg", "blue gg gg gg", "red ggg ggg", "red ggg ggg ggg",
             "blue r g gg", "red b g gg", "blue rr g ggg", "red bb g ggg"]
    want = ["RED", "BLUE", "BLUE", "RED", "RED", "BLUE", "RED", "BLUE"]
    outs = run_bin(None, lines)
    for out, w in zip(outs, want, strict=False):
        assert verdict_of(out) == w, out
    check_shape(outs, lines, None)
    replay_named_topples(outs, lines, None)


def test_a_lead_beyond_the_grey_rows_stands():
    """A player far enough ahead in their own colour wins whoever is to move, however the grey
    rows fall."""
    grey = ["g", "gg", "ggg", "g" * 7, "g" * 12, "g" * 31]
    positions = []
    for g in grey:
        positions.append("blue bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb r " + g)
        positions.append("red bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb r " + g)
    outs = run_bin(None, positions)
    for out in outs:
        assert verdict_of(out) == "BLUE", out
    check_shape(outs, positions, None)
    replay_named_topples(outs, positions, None)


def test_a_level_table_with_no_grey_goes_to_the_other_player():
    """Colours level and no grey standing: whoever must move runs out of turns first."""
    outs = run_bin(None, [
        "blue b r", "red b r", "blue bbb rrr", "red bbb rrr",
        "blue", "red", "blue . .", "red .",
    ])
    assert outs == [
        "blue b r | RED",
        "red b r | BLUE",
        "blue bbb rrr | RED",
        "red bbb rrr | BLUE",
        "blue | RED",
        "red | BLUE",
        "blue . . | RED",
        "red . | BLUE",
    ], outs


def test_a_shut_out_player_still_loses_with_dominoes_standing():
    """Blue to move with only red rows on the table has nothing to push and has lost, and the
    same for Red facing only blue rows."""
    outs = run_bin(None, ["blue rr", "red bbb", "blue r . rr", "red b ."])
    assert outs == [
        "blue rr | RED",
        "red bbb | BLUE",
        "blue r . rr | RED",
        "red b . | BLUE",
    ], outs


def test_only_a_grey_topple_wins():
    """Positions the mover holds only by claiming a grey row: spending a domino of their own
    colour throws the position away."""
    lines = ["blue r gg", "red b gg", "blue bb rrr ggg"]
    outs = run_bin(None, lines)
    for out, line in zip(outs, lines, strict=False):
        mover, _echo, rows, _mixed = read_line(line)
        move = out.split(" | ")[1].split(" ", 1)
        assert move[0] == mover.upper(), out
        idx = int(TOPPLE_TERM.match(move[1]).group(1))
        assert rows[idx - 1][0] == "g", f"{out!r} should push in a grey row"
    check_shape(outs, lines, None)
    replay_named_topples(outs, lines, None)


def test_only_a_coloured_topple_wins():
    """With no grey row on the table the winning topple has to be spent in the mover's own
    colour, and it must not spend so much that the mover falls behind."""
    lines = ["blue bb r", "red rrr bb", "blue bbbbb rrr", "red rrrrrr bbbb"]
    outs = run_bin(None, lines)
    for out, line in zip(outs, lines, strict=False):
        mover, _echo, rows, _mixed = read_line(line)
        move = out.split(" | ")[1].split(" ", 1)
        assert move[0] == mover.upper(), out
        m = TOPPLE_TERM.match(move[1])
        idx, left = int(m.group(1)), int(m.group(2))
        assert rows[idx - 1][0] == mover[0], f"{out!r} should push in the mover's colour"
        after = after_topple(rows, idx, left, mover)
        mine = sum(n for c, n in after if c == mover[0])
        theirs = sum(n for c, n in after if c == foe(mover)[0])
        assert mine >= theirs, f"{out!r} spends the mover's lead away"
    check_shape(outs, lines, None)
    replay_named_topples(outs, lines, None)


def test_a_named_topple_is_replayed_on_hand_positions():
    """A spread of hand positions, every named topple replayed and the position it leaves
    required to be a loss for the player then to move."""
    lines = [
        "blue ggg gg g", "red ggg gg g", "blue bbb rr", "red bbb rr",
        "blue b gg", "red b gg", "blue rr ggg g", "red rr ggg g",
        "blue bb gg rrr", "red bb gg rrr", "blue g g g", "red gg gg gg",
        "blue r gg", "red gggg b rr", "blue gg ggg g bb",
    ]
    outs = run_bin(None, lines)
    check_shape(outs, lines, None)
    replay_named_topples(outs, lines, None)


def test_the_row_order_does_not_change_the_verdict():
    """The rows stand side by side and do not interfere, so writing them in another order
    names the same winner."""
    base = ["gggg", "bb", "g", "rrr", "gg"]
    want = {"blue": "BLUE", "red": "RED"}
    for mover in ("blue", "red"):
        lines = [mover + " " + " ".join(p) for p in itertools.permutations(base)]
        outs = run_bin(None, lines)
        got = {verdict_of(o) for o in outs}
        assert got == {want[mover]}, (mover, got)
        check_shape(outs, lines, None)
    lines = ["blue " + " ".join(base), "red " + " ".join(base)]
    replay_named_topples(run_bin(None, lines), lines, None)


# ----- the surface -----------------------------------------------------------


def test_echo_lowercases_and_respaces():
    """The fields are echoed back in order in lower case and joined by single spaces."""
    outs = run_bin(None, ["  BLUE   GG    b ", "Red\tGgG\t.\tBB"])
    assert outs[0].startswith("blue gg b | "), outs[0]
    assert outs[1].startswith("red ggg . bb | "), outs[1]


def test_empty_rows_hold_their_place():
    """A dot is a row with nothing standing in it: it takes no part in the play but is
    counted in the row numbering."""
    lines = ["blue . . ggg", "blue ggg", "red . g gg"]
    outs = run_bin(None, lines)
    for out, line in zip(outs, lines, strict=False):
        mover = read_line(line)[0]
        assert verdict_of(out) == mover.upper(), out
        idx = int(TOPPLE_TERM.match(out.split(" | ")[1].split(" ", 1)[1]).group(1))
        assert read_line(line)[2][idx - 1][0] is not None, out
    assert outs[0].startswith("blue . . ggg | BLUE topple row 3 "), outs[0]
    assert outs[2].startswith("red . g gg | RED topple row 3 "), outs[2]
    check_shape(outs, lines, None)
    replay_named_topples(outs, lines, None)


def test_a_mixed_row_is_out_of_range():
    """A row that does not stand in a single colour is not a legal row at any table."""
    outs = run_bin(None, ["blue bg", "red ggg rb gg", "blue gbg"])
    assert outs == [
        "blue bg | ILLEGAL",
        "red ggg rb gg | ILLEGAL",
        "blue gbg | ILLEGAL",
    ], outs


def test_a_row_over_the_limit_is_out_of_range():
    """A row longer than the table allows is out of range, and a row at the limit is not."""
    outs = run_bin(4, ["blue gggg", "blue ggggg", "red bb rrrrr", "blue . gggg"])
    assert outs[0].startswith("blue gggg | BLUE topple"), outs[0]
    assert outs[1] == "blue ggggg | ILLEGAL", outs[1]
    assert outs[2] == "red bb rrrrr | ILLEGAL", outs[2]
    assert outs[3].startswith("blue . gggg | BLUE topple"), outs[3]


def test_lines_with_no_position_are_passed_over():
    """A blank line, a line whose first field names no player and a line carrying a field
    that is neither a dot nor a run of b, r and g produce nothing at all."""
    lines = [
        "blue gg", "", "   ", "green gg", "blue gx", "blue 3", "blue g.g",
        "b gg", "bluee gg", "blue gg-", "red gg",
    ]
    outs = run_bin(None, lines)
    assert len(outs) == 2, outs
    assert outs[0].startswith("blue gg | "), outs[0]
    assert outs[1].startswith("red gg | "), outs[1]


def test_a_position_with_no_rows_is_played():
    """A line naming only the player to move is a position with no rows and is played."""
    outs = run_bin(None, ["blue", "red", "BLUE"])
    assert outs == ["blue | RED", "red | BLUE", "blue | RED"], outs


def test_out_of_range_beats_nothing_but_is_beaten_by_a_skip():
    """A line carrying both a row out of range and a field that is no row at all carries no
    position and is passed over rather than called out."""
    outs = run_bin(2, ["blue ggg", "blue ggg zz", "red bg q"])
    assert outs == ["blue ggg | ILLEGAL"], outs


def test_table_file_comments_and_repeats():
    """Comments are dropped, the last rowlimit: line that sets a value stands and a word that
    is not a run of digits leaves the setting where it stood."""
    text = "# rowlimit: 1\nrowlimit: 9 # nine\nrowlimit: nine\nrowlimit: +3\nrowlimit: 4\n"
    outs = run_bin_text(text, ["blue gggg", "blue ggggg"])
    assert outs[0].startswith("blue gggg | BLUE topple"), outs[0]
    assert outs[1] == "blue ggggg | ILLEGAL", outs[1]


def test_a_limit_too_large_to_fit_is_no_limit_at_all():
    """A rowlimit: word too large for a signed 64-bit integer leaves the setting where it
    stood, so the line after it decides the table."""
    outs = run_bin_text("rowlimit: 99999999999999999999999\nrowlimit: 3\n",
                        ["blue ggg", "blue gggg"])
    assert outs == ["blue ggg | BLUE topple row 1 down to 0", "blue gggg | ILLEGAL"], outs


def test_no_limit_by_default():
    """A table file that never sets a limit lets a row stand at any length."""
    outs = run_bin_text("# nothing set here\n", ["blue " + "g" * 40])
    assert outs[0].startswith("blue " + "g" * 40 + " | BLUE topple"), outs[0]


def test_a_limit_of_nought_leaves_only_empty_rows():
    """A table that allows no dominoes in a row calls out every row that holds one."""
    outs = run_bin(0, ["blue g", "blue .", "red . ."])
    assert outs == ["blue g | ILLEGAL", "blue . | RED", "red . . | BLUE"], outs


def test_a_last_line_without_a_newline_is_played():
    """A final line that runs off the end of the input without a newline still carries a
    position and is played."""
    root = tempfile.mkdtemp(prefix="topple-")
    try:
        path = os.path.join(root, "table.txt")
        with open(path, "w") as fh:
            fh.write("")
        p = subprocess.run(APP + [path], input="blue gg\nred b r", capture_output=True,
                           check=False, text=True, timeout=60)
        assert p.returncode == 0, p.stderr[:300]
        outs = p.stdout.split("\n")[:-1]
        assert len(outs) == 2, outs
        assert outs[1] == "red b r | BLUE", outs[1]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_a_very_long_row_is_played():
    """Rows standing tens of thousands of dominoes high arrive on very long lines and are
    played like any other."""
    lines = [
        "blue " + "g" * 70000 + " " + "g" * 69999,
        "red " + "b" * 50000 + " " + "g" * 90000,
        "blue " + "g" * 70000 + " " + "g" * 69999 + " " + "r" * 40000,
    ]
    outs = run_bin(None, lines)
    assert len(outs) == 3, len(outs)
    assert outs[0].split(" | ")[1].startswith("BLUE topple row "), outs[0][-60:]
    assert outs[1].split(" | ")[1].startswith("RED topple row "), outs[1][-60:]
    assert outs[2].split(" | ")[1] == "RED", outs[2][-60:]
    check_shape(outs, lines, None)
    replay_named_topples(outs, lines, None)


def test_uppercase_rows_out_of_range_and_skipped():
    """Upper case is read like lower case, so an upper-case row of two colours is out of range
    and an upper-case field carrying any other letter carries no position."""
    lines = ["BLUE BG", "RED GG", "Blue GxG", "red Bb"]
    outs = run_bin(None, lines)
    assert len(outs) == 3, outs
    assert outs[0] == "blue bg | ILLEGAL", outs[0]
    assert outs[1].startswith("red gg | RED topple row 1 down to "), outs[1]
    assert outs[2] == "red bb | BLUE", outs[2]
    replay_named_topples([outs[1]], ["RED GG"], None)


def test_exit_codes():
    """Wrong argument count and an unreadable table file write nothing and exit 2."""
    root = tempfile.mkdtemp(prefix="topple-")
    try:
        path = os.path.join(root, "table.txt")
        with open(path, "w") as fh:
            fh.write("rowlimit: 8\n")
        p = subprocess.run(APP, input="blue gg\n", capture_output=True, check=False, text=True,
                           timeout=60)
        assert p.returncode == 2 and p.stdout == "", (p.returncode, p.stdout[:200])
        p = subprocess.run(APP + [path, path], input="blue gg\n", capture_output=True,
                           check=False, text=True, timeout=60)
        assert p.returncode == 2 and p.stdout == "", (p.returncode, p.stdout[:200])
        p = subprocess.run(APP + [os.path.join(root, "missing.txt")], input="blue gg\n",
                           capture_output=True, check=False, text=True, timeout=60)
        assert p.returncode == 2 and p.stdout == "", (p.returncode, p.stdout[:200])
        p = subprocess.run(APP + [path], input="", capture_output=True, check=False, text=True,
                           timeout=60)
        assert p.returncode == 0 and p.stdout == "", (p.returncode, p.stdout[:200])
    finally:
        shutil.rmtree(root, ignore_errors=True)
