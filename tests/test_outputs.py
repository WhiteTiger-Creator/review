"""Behavioural checks for the settlement tool in /app.

Every check builds the program from source in /app and compares its report against the
settlements recorded by the club engine.
"""

import functools
import json
import os
import pathlib
import subprocess
import tempfile

import pytest

APP = pathlib.Path("/app")
CORPUS = pathlib.Path(__file__).resolve().parent / "corpus"

PAYMENT_FIELDS = (
    "main",
    "additional",
    "mainBonus",
    "additionalBonus",
    "riichiSticks",
    "total",
)

# Cached build and run outcomes, so a broken submission is not rebuilt per check.
_STATE: dict[str, tuple] = {}


def _build_root() -> pathlib.Path:
    if (APP / "go.mod").is_file():
        return APP
    for candidate in sorted(APP.rglob("go.mod")):
        return candidate.parent
    raise AssertionError("no Go module found under /app")


def settle_binary() -> str:
    """Build the tool from /app once and return the path to the fresh binary."""
    if "binary" not in _STATE:
        try:
            _STATE["binary"] = (_build(), None)
        except AssertionError as exc:
            _STATE["binary"] = (None, str(exc))
    path, problem = _STATE["binary"]
    assert problem is None, problem
    return path


def _build() -> str:
    root = _build_root()
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="handsettle-build-"))
    env = dict(os.environ)
    env.update(
        HOME=str(scratch),
        GOCACHE=str(scratch / "cache"),
        GOPATH=str(scratch / "gopath"),
        GOFLAGS="-mod=mod",
        GOTOOLCHAIN="auto",
        CGO_ENABLED="0",
        GOPROXY="off",
    )
    subprocess.run(
        ["git", "config", "--system", "safe.directory", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )

    made = None
    if (root / "Makefile").is_file():
        subprocess.run(
            ["make", "clean"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        made = subprocess.run(
            ["make"], cwd=root, env=env, capture_output=True, text=True, check=False
        )
        produced = root / "handsettle"
        if made.returncode == 0 and produced.is_file():
            return str(produced)

    out = scratch / "handsettle"
    built = None
    for target in ("./cmd/handsettle", "."):
        built = subprocess.run(
            ["go", "build", "-o", str(out), target],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if built.returncode == 0 and out.is_file():
            return str(out)

    detail = ""
    if made is not None:
        detail += f"make exited {made.returncode}\n{made.stdout}\n{made.stderr}\n"
    if built is not None:
        detail += f"go build exited {built.returncode}\n{built.stdout}\n{built.stderr}"
    raise AssertionError("the settlement tool in /app does not build:\n" + detail)


@functools.cache
def recorded():
    with (CORPUS / "expected.json").open(encoding="utf-8") as fh:
        return json.load(fh)


@functools.cache
def logged():
    with (CORPUS / "hands.json").open(encoding="utf-8") as fh:
        return {hand["id"]: hand for hand in json.load(fh)}


def reported():
    """Run the tool over the hidden hand log and return its reports by hand id."""
    if "reports" not in _STATE:
        try:
            _STATE["reports"] = (_run(), None)
        except AssertionError as exc:
            _STATE["reports"] = (None, str(exc))
    payload, problem = _STATE["reports"]
    assert problem is None, problem
    return payload


def _run():
    binary = settle_binary()
    proc = subprocess.run(
        [binary, str(CORPUS / "hands.json")],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert proc.returncode == 0, (
        f"the tool exited {proc.returncode}\n"
        f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"stdout is not JSON ({exc}): {proc.stdout[:400]!r}"
        ) from exc
    assert isinstance(payload, list), (
        f"stdout is not a JSON array: {proc.stdout[:200]!r}"
    )
    by_id = {}
    for entry in payload:
        bad_entry = f"bad report entry: {entry!r}"
        assert isinstance(entry, dict), bad_entry
        assert "id" in entry, bad_entry
        by_id[entry["id"]] = entry
    return by_id


def cases():
    """One check per logged hand, labelled with the rule family it exercises."""
    return [f"{item['family']}:{item['id']}" for item in recorded()]


def describe(hand):
    keep = (
        "hand",
        "melds",
        "winTile",
        "win",
        "seatWind",
        "roundWind",
        "doraIndicators",
        "honba",
        "riichiSticks",
    )
    situational = (
        "riichi",
        "ippatsu",
        "rinshan",
        "chankan",
        "haitei",
        "houtei",
        "doubleRiichi",
        "tenhou",
        "chiihou",
    )
    shown = {k: hand[k] for k in keep if hand.get(k) not in (None, [], 0)}
    flags = [k for k in situational if hand.get(k)]
    if flags:
        shown["flags"] = flags
    return json.dumps(shown, sort_keys=True)


def compare(want, got):
    """Return a list of human-readable differences for one hand."""
    problems = []
    if bool(got.get("scored")) != bool(want["scored"]):
        return [f"scored = {got.get('scored')!r}, expected {want['scored']!r}"]
    if not want["scored"]:
        return []
    if got.get("han") != want["han"]:
        problems.append(f"han = {got.get('han')!r}, expected {want['han']}")
    if got.get("fu") != want["fu"]:
        problems.append(f"fu = {got.get('fu')!r}, expected {want['fu']}")
    got_yaku = got.get("yaku")
    if not isinstance(got_yaku, list) or sorted(str(y) for y in got_yaku) != sorted(
        want["yaku"]
    ):
        problems.append(f"yaku = {got_yaku!r}, expected {sorted(want['yaku'])}")
    payment = got.get("payment")
    if not isinstance(payment, dict):
        problems.append(f"payment = {payment!r}, expected {want['payment']}")
    else:
        for field in PAYMENT_FIELDS:
            if payment.get(field) != want["payment"][field]:
                problems.append(
                    f"payment.{field} = {payment.get(field)!r}, "
                    f"expected {want['payment'][field]}"
                )
    return problems


def test_one_report_per_logged_hand():
    got = reported()
    want = recorded()
    missing = [item["id"] for item in want if item["id"] not in got]
    assert not missing, (
        f"{len(missing)} logged hands have no report, e.g. {missing[:5]}"
    )
    assert len(got) == len(want), (
        f"reported {len(got)} hands for a log of {len(want)}"
    )


def test_reports_follow_log_order():
    order = list(reported())
    expected_order = [item["id"] for item in recorded()]
    first = next(
        (
            index
            for index, (left, right) in enumerate(
                zip(order, expected_order, strict=False)
            )
            if left != right
        ),
        0,
    )
    assert order == expected_order, (
        f"reports are not in log order; first difference at position {first}"
    )


@pytest.mark.parametrize("case", cases())
def test_settlement_matches_club_engine(case):
    hand_id = case.split(":", 1)[1]
    want = next(item for item in recorded() if item["id"] == hand_id)
    entry = reported().get(hand_id)
    assert entry is not None, f"{hand_id}: no report"
    hand = logged()[hand_id]
    problems = compare(want, entry)
    assert not problems, (
        f"{hand_id} {describe(hand)} settles differently\n  " + "\n  ".join(problems)
    )
