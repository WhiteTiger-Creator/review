"""Behavioral verifier for hpackward-rust-dynamic-table-eviction-divergence.

Builds the candidate witness synthesizer, drives it with deterministically
generated divergence obligations, and checks every emitted witness block against
the independent hpack_oracle. Grading is behavioral only: the candidate binary's
observed stdout (a hex-encoded HPACK block) is the sole signal. The oracle never
trusts the candidate and never reads the audited decoder source under evidence/,
so a modified target cannot influence ground truth. Every case must pass for
reward 1 (wired in test.sh).

Beyond the per-obligation construction check, the suite pins down that the
obligation battery is non-trivial and that the checker discriminates: every
generated obligation is independently solvable (a verifier-side builder proves
it), a witness built for one obligation fails a different one, and a witness that
exploits the wrong audited deviation fails mechanism attribution.
"""

import os
import pathlib
import subprocess

import gen_obligations
import hpack_oracle as O
import pytest
import witness_builder as W

ANALYSIS = "/app/environment/analysis"
BIN = os.path.join(ANALYSIS, "target", "release", "synth")
MANIFEST = os.path.join(ANALYSIS, "Cargo.toml")
WORK = "/tmp/hpack_verifier"

os.makedirs(WORK, exist_ok=True)

OBLIGATIONS = gen_obligations.build_obligations()
BY_TAG = dict(OBLIGATIONS)


def _build():
    r = subprocess.run(
        [
            "cargo",
            "build",
            "--release",
            "--locked",
            "--offline",
            "--manifest-path",
            MANIFEST,
        ],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    return r.returncode == 0, r.stdout + r.stderr


@pytest.fixture(scope="session", autouse=True)
def built():
    ok, log = _build()
    assert ok, "candidate build failed:\n" + log[-2000:]
    assert os.path.exists(BIN), "synth binary not produced at " + BIN


def _run(tag, line):
    path = os.path.join(WORK, tag + ".obl")
    pathlib.Path(path).write_text(line + "\n")
    r = subprocess.run(
        [BIN, path], capture_output=True, text=True, timeout=60, check=False
    )
    assert r.returncode == 0, f"synth exited {r.returncode} on {tag}: {r.stderr[:400]}"
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1, (
        f"expected exactly one output line for {tag}, got {len(lines)}"
    )
    hexstr = lines[0].strip()
    try:
        return bytes.fromhex(hexstr)
    except ValueError:
        raise AssertionError(f"output for {tag} is not hex: {hexstr[:80]!r}") from None


def test_case_floor():
    assert len(OBLIGATIONS) >= 60, (
        f"need at least 60 executed cases, have {len(OBLIGATIONS)}"
    )


def test_mechanism_coverage():
    obs = [O.parse_obligation(line) for _, line in OBLIGATIONS]
    for mech in O.MECHANISMS:
        assert sum(1 for o in obs if o["mech"] == mech) >= 8, (
            f"mechanism {mech} under-represented"
        )
    # all three outcome families exercised, including audited_reject (only
    # reachable through the stricter minint deviation)
    assert sum(1 for o in obs if o["outcome"] == "both_accept") >= 10
    assert sum(1 for o in obs if o["outcome"] == "reference_reject") >= 10
    assert sum(1 for o in obs if o["outcome"] == "audited_reject") >= 8
    # at least one joint obligation whose conflict needs several deviations
    # acting together (a per-mechanism gadget library cannot satisfy it)
    assert any("+" in o["mech"] for o in obs), "no joint-mechanism obligation present"
    # a spread of divergence positions
    assert len({o["pos"] for o in obs}) >= 5
    # Huffman genuinely required somewhere beyond the huffpad mechanism
    assert (
        sum(1 for o in obs if o["huff"] == "required" and o["mech"] != "huffpad") >= 5
    )


@pytest.mark.parametrize(("tag", "line"), OBLIGATIONS, ids=[t for t, _ in OBLIGATIONS])
def test_case(tag, line):
    ob = O.parse_obligation(line)
    witness = _run(tag, line)
    ok, why = O.check_witness(witness, ob)
    assert ok, f"witness for {tag} ({line}) rejected: {why}"


def test_every_obligation_is_solvable():
    """A verifier-side builder produces a satisfying witness for every obligation,
    proving the battery is solvable (and thus the oracle can reach reward 1)."""
    for oid, (tag, line) in enumerate(OBLIGATIONS):
        ob = O.parse_obligation(line)
        w = W.construct(ob, oid)
        ok, why = O.check_witness(w, ob)
        assert ok, f"reference witness for {tag} rejected: {why}"


def test_checker_rejects_empty_and_garbage():
    for ob_line in [line for _, line in OBLIGATIONS]:
        ob = O.parse_obligation(ob_line)
        assert not O.check_witness(b"", ob)[0]
        assert not O.check_witness(b"\x00\x00\x00\x00", ob)[0]
        assert not O.check_witness(b"\x00\x00\x00\x00\x82", ob)[0]


def test_checker_discriminates_across_obligations():
    """A witness valid for one obligation must fail obligations that differ in
    position, mechanism, or honored maximum -- otherwise a single canned block
    could pass many cases."""
    built = {}
    for oid, (tag, line) in enumerate(OBLIGATIONS):
        ob = O.parse_obligation(line)
        built[tag] = (W.construct(ob, oid), ob)
    tags = list(built)
    tested = caught = 0
    for a in tags:
        wa, oba = built[a]
        for b in tags:
            _, obb = built[b]
            if (oba["pos"], oba["mech"], oba["max"]) == (
                obb["pos"],
                obb["mech"],
                obb["max"],
            ):
                continue
            tested += 1
            if not O.check_witness(wa, obb)[0]:
                caught += 1
    assert tested > 0
    assert caught == tested, (
        f"checker failed to discriminate {tested - caught}/{tested}"
    )


def test_wrong_mechanism_is_rejected():
    """A witness that exploits a different audited deviation than the one an
    obligation names fails mechanism attribution (sufficiency / minimality /
    necessity)."""
    tested = caught = 0
    for oid, (_tag, line) in enumerate(OBLIGATIONS):
        ob = O.parse_obligation(line)
        alt = dict(ob)
        if ob["mech"] in ("never", "sizeupdate"):
            # A pure huffpad witness cannot pass a table-deviation obligation.
            alt.update(
                mech="huffpad", outcome="reference_reject", max=4096, huff="required"
            )
        else:
            # overhead, huffpad, minint, and the joint obligation all map to a
            # plain never value-substitution witness that exploits a single,
            # different deviation.
            alt.update(
                mech="never",
                outcome="both_accept",
                max=4096,
                pos=max(2, ob["pos"]),
                huff="none",
            )
        try:
            w = W.construct(alt, oid)
        except AssertionError:
            # A decoy the builder cannot construct for these params is skipped.
            continue
        tested += 1
        if not O.check_witness(w, ob)[0]:
            caught += 1
    assert tested >= 10
    assert caught == tested, (
        f"attribution failed on {tested - caught}/{tested} wrong-mechanism witnesses"
    )


def test_joint_needs_both_deviations():
    """For every joint (a+b) obligation, a witness that exploits only one of the
    two named deviations fails attribution: the joint conflict is not reducible
    to a single audited deviation."""
    joint = [
        (oid, line)
        for oid, (_, line) in enumerate(OBLIGATIONS)
        if "+" in O.parse_obligation(line)["mech"]
    ]
    assert joint, "expected at least one joint obligation"
    for oid, line in joint:
        ob = O.parse_obligation(line)
        w = W.construct(ob, oid)
        buf = w[4:]
        max0 = int.from_bytes(w[0:4], "big")
        ref_em, _ = O.decode(buf, max0, O.REF)
        for atom in O.mech_bugs(ob["mech"]):
            only_em, _ = O.decode(buf, max0, frozenset({atom}))
            div = O.first_divergence(ref_em, only_em)
            assert div is None or div[0] != ob["pos"], (
                f"single deviation {atom} reproduces joint obligation {ob}"
            )
