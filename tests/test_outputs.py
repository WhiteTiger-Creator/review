"""Behavioral verifier for the cosign quorum auditor task.

Every check runs the agent's /app/audit executable against release-ledger files
generated fresh at test time (random signer rosters, key rotations, removals,
releases, valid and forged cosignatures, and authorize queries), so a tool that
hardcodes or replays a fixed answer cannot pass. The expected object is computed
by an independent Python reference implementation of the same scheme: the whole
hand-rolled keyed MAC over the [rid, sid, digest] word order, the order-dependent
aggregate combine folded in signer-id order, the positional roster replay with
enroll/remove active-set tracking, the key-rotation voiding of earlier
cosignatures, the k-of-n threshold, the per-release verification verdict
precedence, and the whole-file schema. The candidate executable is run as an
unprivileged user with /tests unreadable to it, so the reference cannot be read
at run time. No network is touched in any path.
"""

import json
import os
import random
import subprocess
import tempfile

import pytest

AUDIT = "/app/audit"
RESULT = "/app/output/result.json"

RNG = random.Random()

M = (1 << 64) - 1
C0 = 0x736f6d6570736575
C1 = 0x646f72616e646f6d
C2 = 0x6c7967656e657261
PAD = 0x0f0f0f0f0f0f0f0f
FIN = 0xff00ff00ff00ff00
SEED = 0xc3d2e1f0a1b2c3d4
MULT = 0x9e3779b97f4a7c15
STANDING_THRESHOLD = 2


def rotl(x, r):
    x &= M
    return ((x << r) | (x >> (64 - r))) & M


def rnd(v0, v1, v2):
    v0 = (v0 + v1) & M
    v1 = rotl(v1, 13)
    v1 ^= v0
    v0 = rotl(v0, 32)
    v2 = (v2 + v0) & M
    v0 = rotl(v0, 16)
    v0 ^= v2
    v2 = rotl(v2, 21)
    v1 = (v1 + v2) & M
    v2 ^= v1
    return v0 & M, v1 & M, v2 & M


def mac(key, words):
    v0 = key ^ C0
    v1 = rotl(key, 32) ^ C1
    v2 = key ^ C2
    for w in words:
        v0 = (v0 + w) & M
        v2 ^= w
        v0, v1, v2 = rnd(v0, v1, v2)
        v0, v1, v2 = rnd(v0, v1, v2)
    v2 ^= PAD
    v0, v1, v2 = rnd(v0, v1, v2)
    v0, v1, v2 = rnd(v0, v1, v2)
    v1 ^= FIN
    v0, v1, v2 = rnd(v0, v1, v2)
    return (v0 ^ v1 ^ v2) & M


def combine(tags):
    acc = SEED
    for t in tags:
        acc ^= t
        acc = rotl(acc, 7)
        acc = (acc + MULT) & M
        acc ^= rotl(t, 40)
    acc ^= acc >> 33
    acc = (acc * 0xff51afd7ed558ccd) & M
    acc ^= acc >> 33
    acc = (acc * 0xc4ceb9fe1a85ec53) & M
    acc ^= acc >> 33
    return acc & M


def u(s):
    return int(s, 16)


def h(x):
    return f"{x:016x}"


def tag_of(key_hex, rid, sid, digest):
    """The correct keyed tag a signer holding key_hex would record."""
    return h(mac(u(key_hex), [u(rid), u(sid), u(digest)]))


def reference(recs):
    """recs: ("enroll", sid, key) / ("remove", sid) / ("rotate", sid, key)
    / ("release", rid, k, digest) / ("cosign", rid, sid, tag)
    / ("authorize", seq, rid, claim) / ("anchor", sid)
    / ("vouch", voucher_sid, target_sid)."""

    def malformed():
        return {"status": "malformed", "decisions": [], "releases": [],
                "authorized_count": 0, "under_threshold_count": 0,
                "tag_mismatch_count": 0, "unknown_count": 0,
                "release_count": 0, "authorize_count": 0}

    releases = {}
    enrolled = set()
    for r in recs:
        if r[0] == "release":
            if r[1] in releases:
                return malformed()
            releases[r[1]] = (r[2], r[3])
        elif r[0] == "enroll":
            enrolled.add(r[1])
    release_count = sum(1 for r in recs if r[0] == "release")
    authorize_count = sum(1 for r in recs if r[0] == "authorize")

    qi = 0
    for r in recs:
        if r[0] == "release":
            if r[2] < 0:
                return malformed()
        elif r[0] == "cosign":
            if r[1] not in releases or r[2] not in enrolled:
                return malformed()
        elif r[0] in ("remove", "rotate", "anchor"):
            if r[1] not in enrolled:
                return malformed()
        elif r[0] == "vouch":
            if r[1] not in enrolled or r[2] not in enrolled:
                return malformed()
            if r[1] == r[2]:
                return malformed()
        elif r[0] == "authorize":
            if r[1] < 0 or r[1] != qi:
                return malformed()
            qi += 1

    idx_recs = list(enumerate(recs))

    def key_in_force(sid, upto):
        k = None
        for i, r in idx_recs:
            if i > upto:
                break
            if r[0] in ("enroll", "rotate") and r[1] == sid:
                k = r[2]
        return k

    def is_active(sid, upto):
        st = None
        for i, r in idx_recs:
            if i >= upto:
                break
            if r[0] == "enroll" and r[1] == sid:
                st = True
            elif r[0] == "remove" and r[1] == sid:
                st = False
        return st is True

    anchors = {r[1] for r in recs if r[0] == "anchor"}

    def standing_set(upto):
        """Section 5.5: least-fixpoint standing at position `upto`. Returns
        None when standing gating is inactive (no anchor declared anywhere in
        the file), meaning every active signer qualifies regardless."""
        if not anchors:
            return None
        vouchers_of = {}
        for i, r in idx_recs:
            if i >= upto:
                break
            if r[0] == "vouch":
                vouchers_of.setdefault(r[2], set()).add(r[1])
        standing = {a for a in anchors if is_active(a, upto)}
        changed = True
        while changed:
            changed = False
            for target, vouchers in vouchers_of.items():
                if target in standing:
                    continue
                if not is_active(target, upto):
                    continue
                if len(vouchers & standing) >= STANDING_THRESHOLD:
                    standing.add(target)
                    changed = True
        return standing

    def eval_release(rid, k, digest, upto):
        qual = {}
        standing = standing_set(upto)
        for i, r in idx_recs:
            if i >= upto:
                break
            if r[0] != "cosign" or r[1] != rid:
                continue
            sid, tag = r[2], r[3]
            kf = key_in_force(sid, i)
            if kf is None:
                continue
            voided = any(rr[0] == "rotate" and rr[1] == sid and i < j < upto
                         for j, rr in idx_recs)
            if voided:
                continue
            if not is_active(sid, upto):
                continue
            if standing is not None and sid not in standing:
                continue
            if h(mac(u(kf), [u(rid), u(sid), u(digest)])) != tag:
                continue
            qual[sid] = mac(u(kf), [u(rid), u(sid), u(digest)])
        sids = sorted(qual)
        return len(sids), h(combine([qual[s] for s in sids]))

    decisions = []
    counts = {"authorized": 0, "under_threshold": 0,
              "tag_mismatch": 0, "unknown_release": 0}
    declared_above = set()
    for i, r in idx_recs:
        if r[0] == "release":
            declared_above.add(r[1])
        elif r[0] == "authorize":
            seq, rid, claim = r[1], r[2], r[3]
            if rid not in declared_above:
                v = "unknown_release"
                cos, agg = 0, "0" * 16
            else:
                k, digest = releases[rid]
                cos, agg = eval_release(rid, k, digest, i)
                if cos < k:
                    v = "under_threshold"
                elif agg != claim:
                    v = "tag_mismatch"
                else:
                    v = "authorized"
            counts[v] += 1
            decisions.append({"seq": seq, "verdict": v,
                              "cosigners": cos, "aggregate": agg})

    rel_list = []
    total = len(recs)
    for rid in [r[1] for r in recs if r[0] == "release"]:
        k, digest = releases[rid]
        cos, agg = eval_release(rid, k, digest, total)
        rel_list.append({"id": rid, "authorized": cos >= k,
                         "cosigners": cos, "aggregate": agg})

    return {"status": "ok", "decisions": decisions, "releases": rel_list,
            "authorized_count": counts["authorized"],
            "under_threshold_count": counts["under_threshold"],
            "tag_mismatch_count": counts["tag_mismatch"],
            "unknown_count": counts["unknown_release"],
            "release_count": release_count, "authorize_count": authorize_count}


def serialize(recs):
    lines = []
    for r in recs:
        if r[0] == "enroll":
            lines.append(f"enroll {r[1]} {r[2]}")
        elif r[0] == "remove":
            lines.append(f"remove {r[1]}")
        elif r[0] == "rotate":
            lines.append(f"rotate {r[1]} {r[2]}")
        elif r[0] == "release":
            lines.append(f"release {r[1]} {r[2]} {r[3]}")
        elif r[0] == "cosign":
            lines.append(f"cosign {r[1]} {r[2]} {r[3]}")
        elif r[0] == "anchor":
            lines.append(f"anchor {r[1]}")
        elif r[0] == "vouch":
            lines.append(f"vouch {r[1]} {r[2]}")
        else:
            lines.append(f"authorize {r[1]} {r[2]} {r[3]}")
    return "\n".join(lines) + "\n"


def hid():
    return "".join(RNG.choice("0123456789abcdef") for _ in range(16))


def agg_at(prefix, rid):
    """The aggregate the reference computes at an authorize placed right after
    `prefix` — used to build correctly-claimed (authorized) fixtures."""
    seq = sum(1 for r in prefix if r[0] == "authorize")
    out = reference(prefix + [("authorize", seq, rid, "0" * 16)])
    return out["decisions"][-1]["aggregate"]


WORK = tempfile.mkdtemp(prefix="cqa-fixtures-")
os.chmod(WORK, 0o755)

try:
    import pwd
    _SB = pwd.getpwnam("sandbox")

    def _DEMOTE():
        os.setgid(_SB.pw_gid)
        os.setuid(_SB.pw_uid)
except (ImportError, KeyError):
    _DEMOTE = None

try:
    os.chmod("/tests", 0o700)
except OSError:
    pass
try:
    os.makedirs("/app/output", exist_ok=True)
    os.chmod("/app/output", 0o1777)
except OSError:
    pass


def _write(recs):
    path = os.path.join(WORK, f"led-{RNG.randrange(1 << 40):010x}.txt")
    with open(path, "w") as f:
        f.write(serialize(recs))
    os.chmod(path, 0o644)
    return path


def _write_raw(text, binary=False):
    path = os.path.join(WORK, f"raw-{RNG.randrange(1 << 40):010x}.txt")
    with open(path, "wb" if binary else "w") as f:
        f.write(text)
    os.chmod(path, 0o644)
    return path


def _run(path):
    if os.path.exists(RESULT):
        os.remove(RESULT)
    kwargs = {}
    if _DEMOTE is not None and os.geteuid() == 0:
        kwargs["preexec_fn"] = _DEMOTE
    proc = subprocess.run([AUDIT, path], capture_output=True, text=True,
                          timeout=120, check=False, **kwargs)
    parsed = None
    if os.path.exists(RESULT):
        with open(RESULT) as f:
            parsed = json.load(f)
    return proc, parsed


def _run_ok(recs):
    path = _write(recs)
    proc, parsed = _run(path)
    assert proc.returncode == 0, f"expected exit 0, got {proc.returncode}: {proc.stderr}"
    assert parsed is not None, "result.json was not written"
    stdout = proc.stdout.strip()
    assert stdout, "nothing printed to stdout"
    assert json.loads(stdout) == parsed, "stdout line and result.json differ"
    exp = reference(recs)
    assert parsed == exp, f"\n got {parsed}\n exp {exp}\n file=\n{serialize(recs)}"
    return parsed


def _verdicts(r):
    return [d["verdict"] for d in r["decisions"]]


# --------------------------------------------------------------------------
# Infrastructure anchors
# --------------------------------------------------------------------------

def test_executable_exists():
    assert os.path.exists(AUDIT), "/app/audit missing"
    assert os.access(AUDIT, os.X_OK), "/app/audit is not executable"


def test_candidate_cannot_read_reference():
    if _DEMOTE is None or os.geteuid() != 0:
        pytest.skip("not running as root with a sandbox account")
    proc = subprocess.run(["cat", "/tests/test_outputs.py"], capture_output=True,
                          text=True, check=False, preexec_fn=_DEMOTE)
    assert proc.returncode != 0
    assert not proc.stdout


def test_output_schema():
    s, k, rid, dig = hid(), hid(), hid(), hid()
    t = tag_of(k, rid, s, dig)
    recs = [("enroll", s, k), ("release", rid, 1, dig),
            ("cosign", rid, s, t),
            ("authorize", 0, rid, agg_at([("enroll", s, k), ("release", rid, 1, dig),
                                          ("cosign", rid, s, t)], rid))]
    out = _run_ok(recs)
    assert set(out.keys()) == {"status", "decisions", "releases", "authorized_count",
                               "under_threshold_count", "tag_mismatch_count",
                               "unknown_count", "release_count", "authorize_count"}
    d = out["decisions"][0]
    assert set(d.keys()) == {"seq", "verdict", "cosigners", "aggregate"}
    assert d["verdict"] == "authorized"
    rl = out["releases"][0]
    assert set(rl.keys()) == {"id", "authorized", "cosigners", "aggregate"}


# --------------------------------------------------------------------------
# Behavioural anchors (hand-verified)
# --------------------------------------------------------------------------

def test_worked_three_signer_aggregate():
    """Fixed vector: three valid cosigners, threshold 2, the aggregate folded
    in signer-id order authorizes the release; a wrong claim is tag_mismatch."""
    k1, s1 = "0000000000000011", "1111111111111111"
    k2, s2 = "0000000000000022", "2222222222222222"
    k3, s3 = "0000000000000033", "3333333333333333"
    rid, dig = "abcdef0123456789", "cafebabedeadbeef"
    t1, t2, t3 = (tag_of(k1, rid, s1, dig), tag_of(k2, rid, s2, dig),
                  tag_of(k3, rid, s3, dig))
    agg = h(combine([u(t1), u(t2), u(t3)]))
    assert agg == "8ab313b523ab134c"  # hand-computed order-dependent aggregate
    recs = [("enroll", s1, k1), ("enroll", s2, k2), ("enroll", s3, k3),
            ("release", rid, 2, dig),
            ("cosign", rid, s1, t1), ("cosign", rid, s2, t2), ("cosign", rid, s3, t3),
            ("authorize", 0, rid, agg),
            ("authorize", 1, rid, "deadbeefdeadbeef")]
    out = _run_ok(recs)
    assert _verdicts(out) == ["authorized", "tag_mismatch"]
    assert out["decisions"][0]["cosigners"] == 3
    assert out["decisions"][0]["aggregate"] == "8ab313b523ab134c"


def test_aggregate_is_order_dependent_by_sid():
    """The aggregate folds in signer-id order, not cosignature-appearance order
    and not an order-independent XOR. Signers are cosigned high-id first."""
    khi, shi = "00000000000000a1", "ffffffffffffffff"
    klo, slo = "00000000000000b2", "0000000000000001"
    rid, dig = hid(), hid()
    thi, tlo = tag_of(khi, rid, shi, dig), tag_of(klo, rid, slo, dig)
    sid_order = h(combine([u(tlo), u(thi)]))       # slo < shi
    appearance = h(combine([u(thi), u(tlo)]))      # cosigned high first
    xor = h(u(thi) ^ u(tlo))
    assert sid_order != appearance and sid_order != xor
    recs = [("enroll", shi, khi), ("enroll", slo, klo), ("release", rid, 2, dig),
            ("cosign", rid, shi, thi), ("cosign", rid, slo, tlo),
            ("authorize", 0, rid, sid_order)]
    out = _run_ok(recs)
    assert _verdicts(out) == ["authorized"]
    assert out["decisions"][0]["aggregate"] == sid_order


def test_rotation_voids_earlier_cosignature():
    """A cosignature recorded before the signer's key rotation is voided even
    though its tag was valid under the old key."""
    k0, k1, s = hid(), hid(), hid()
    rid, dig = hid(), hid()
    t = tag_of(k0, rid, s, dig)
    base = [("enroll", s, k0), ("release", rid, 1, dig), ("cosign", rid, s, t)]
    out = _run_ok(base + [("authorize", 0, rid, agg_at(base, rid))])
    assert _verdicts(out) == ["authorized"]
    rotated = base + [("rotate", s, k1)]
    out2 = _run_ok(rotated + [("authorize", 0, rid, h(combine([])))])
    assert _verdicts(out2) == ["under_threshold"]
    assert out2["decisions"][0]["cosigners"] == 0


def test_forged_tag_does_not_count():
    """A tag that does not verify under the signer's key in force is ignored."""
    k, s, rid, dig = hid(), hid(), hid(), hid()
    bad = hid()
    recs = [("enroll", s, k), ("release", rid, 1, dig),
            ("cosign", rid, s, bad), ("authorize", 0, rid, h(combine([])))]
    out = _run_ok(recs)
    assert _verdicts(out) == ["under_threshold"]
    assert out["decisions"][0]["cosigners"] == 0


def test_removed_signer_cosignature_ignored():
    """A removed signer's cosignature does not count at a later authorize."""
    ka, sa, kb, sb = hid(), hid(), hid(), hid()
    rid, dig = hid(), hid()
    ta, tb = tag_of(ka, rid, sa, dig), tag_of(kb, rid, sb, dig)
    base = [("enroll", sa, ka), ("enroll", sb, kb), ("release", rid, 2, dig),
            ("cosign", rid, sa, ta), ("cosign", rid, sb, tb)]
    out = _run_ok(base + [("authorize", 0, rid, agg_at(base, rid))])
    assert _verdicts(out) == ["authorized"]
    removed = base + [("remove", sb)]
    out2 = _run_ok(removed + [("authorize", 0, rid, agg_at(removed, rid))])
    assert _verdicts(out2) == ["under_threshold"]
    assert out2["decisions"][0]["cosigners"] == 1


def test_threshold_exactly_met_vs_one_short():
    """Threshold k met exactly authorizes; one fewer valid cosigner does not."""
    ka, sa, kb, sb = hid(), hid(), hid(), hid()
    rid, dig = hid(), hid()
    ta, tb = tag_of(ka, rid, sa, dig), tag_of(kb, rid, sb, dig)
    met = [("enroll", sa, ka), ("enroll", sb, kb), ("release", rid, 2, dig),
           ("cosign", rid, sa, ta), ("cosign", rid, sb, tb)]
    out = _run_ok(met + [("authorize", 0, rid, agg_at(met, rid))])
    assert _verdicts(out) == ["authorized"]
    short = [("enroll", sa, ka), ("enroll", sb, kb), ("release", rid, 2, dig),
             ("cosign", rid, sa, ta)]
    out2 = _run_ok(short + [("authorize", 0, rid, agg_at(short, rid))])
    assert _verdicts(out2) == ["under_threshold"]
    assert out2["decisions"][0]["cosigners"] == 1


def test_forward_reference_signer_enrolled_later():
    """A cosignature recorded before its signer is enrolled has no key in force
    and cannot verify; once enrolled and re-cosigned it counts."""
    k, s, rid, dig = hid(), hid(), hid(), hid()
    t = tag_of(k, rid, s, dig)
    # cosign BEFORE enroll: build a case where the cosign precedes enroll
    early = [("release", rid, 1, dig), ("cosign", rid, s, t),
             ("authorize", 0, rid, h(combine([]))),
             ("enroll", s, k), ("cosign", rid, s, t),
             ("authorize", 1, rid, None)]
    early[-1] = ("authorize", 1, rid, agg_at(early[:5], rid))
    out = _run_ok(early)
    assert _verdicts(out) == ["under_threshold", "authorized"]
    assert out["decisions"][0]["cosigners"] == 0
    assert out["decisions"][1]["cosigners"] == 1


def test_unknown_release_is_positional():
    """An authorize on a release id not declared above the line is
    unknown_release; once the release is declared above, it is verified."""
    k, s, rid, dig = hid(), hid(), hid(), hid()
    t = tag_of(k, rid, s, dig)
    recs = [("enroll", s, k), ("authorize", 0, rid, h(combine([]))),
            ("release", rid, 1, dig), ("cosign", rid, s, t),
            ("authorize", 1, rid, None)]
    recs[-1] = ("authorize", 1, rid, agg_at(recs[:4], rid))
    out = _run_ok(recs)
    assert _verdicts(out) == ["unknown_release", "authorized"]
    assert out["decisions"][0]["cosigners"] == 0
    assert out["decisions"][0]["aggregate"] == "0000000000000000"


def test_threshold_zero_authorizes_with_matching_empty_aggregate():
    """Threshold zero with no valid cosigners authorizes only when the claim is
    the empty-set aggregate."""
    rid, dig = hid(), hid()
    empty = h(combine([]))
    recs = [("release", rid, 0, dig), ("authorize", 0, rid, empty),
            ("authorize", 1, rid, hid())]
    recs[2] = ("authorize", 1, rid, "0" * 15 + "1")
    out = _run_ok(recs)
    assert _verdicts(out)[0] == "authorized"
    assert _verdicts(out)[1] == "tag_mismatch"


def test_duplicate_cosign_counts_once():
    """The same signer cosigning a release twice still counts as one signer."""
    k, s, rid, dig = hid(), hid(), hid(), hid()
    t = tag_of(k, rid, s, dig)
    base = [("enroll", s, k), ("release", rid, 1, dig),
            ("cosign", rid, s, t), ("cosign", rid, s, t)]
    out = _run_ok(base + [("authorize", 0, rid, agg_at(base, rid))])
    assert _verdicts(out) == ["authorized"]
    assert out["decisions"][0]["cosigners"] == 1


def test_final_releases_reflect_end_state():
    """The releases array evaluates each release under the whole file: a
    rotation late in the file voids an earlier cosignature in the end state."""
    k0, k1, s, rid, dig = hid(), hid(), hid(), hid(), hid()
    t = tag_of(k0, rid, s, dig)
    recs = [("enroll", s, k0), ("release", rid, 1, dig), ("cosign", rid, s, t),
            ("authorize", 0, rid, agg_at([("enroll", s, k0),
                                          ("release", rid, 1, dig),
                                          ("cosign", rid, s, t)], rid)),
            ("rotate", s, k1)]
    out = _run_ok(recs)
    assert _verdicts(out) == ["authorized"]
    rl = out["releases"][0]
    assert rl["authorized"] is False and rl["cosigners"] == 0


# --------------------------------------------------------------------------
# Signer standing (section 5.5): anchors, vouches, the least-fixpoint gate
# --------------------------------------------------------------------------

def test_standing_gating_inactive_without_any_anchor():
    """With no `anchor` line anywhere in the file, standing gating is
    inactive: a lone unsupported `vouch` line changes nothing."""
    s, ks = hid(), hid()
    other, kother = hid(), hid()
    rid, dig = hid(), hid()
    t = tag_of(ks, rid, s, dig)
    recs = [("enroll", s, ks), ("enroll", other, kother),
            ("vouch", other, s), ("release", rid, 1, dig),
            ("cosign", rid, s, t)]
    out = _run_ok(recs + [("authorize", 0, rid, agg_at(recs, rid))])
    assert _verdicts(out) == ["authorized"]
    assert out["decisions"][0]["cosigners"] == 1


def test_standing_two_distinct_anchor_vouchers_ground_a_signer():
    """A signer needs two distinct already-standing vouchers to gain
    standing; one anchor vouching is not enough, a second distinct anchor
    vouching grounds it and its cosignature starts counting."""
    a1, ka1 = hid(), hid()
    a2, ka2 = hid(), hid()
    s, ks = hid(), hid()
    rid, dig = hid(), hid()
    t = tag_of(ks, rid, s, dig)
    base = [("enroll", a1, ka1), ("enroll", a2, ka2), ("anchor", a1), ("anchor", a2),
            ("enroll", s, ks), ("release", rid, 1, dig), ("cosign", rid, s, t)]
    one_vouch = base + [("vouch", a1, s)]
    out1 = _run_ok(one_vouch + [("authorize", 0, rid, h(combine([])))])
    assert _verdicts(out1) == ["under_threshold"]
    assert out1["decisions"][0]["cosigners"] == 0
    two_vouch = one_vouch + [("vouch", a2, s)]
    out2 = _run_ok(two_vouch + [("authorize", 0, rid, agg_at(two_vouch, rid))])
    assert _verdicts(out2) == ["authorized"]
    assert out2["decisions"][0]["cosigners"] == 1


def test_standing_isolated_ring_never_grounds_despite_meeting_voucher_count():
    """Three signers who vouch only for one another, each showing two
    distinct vouchers, never attain standing: standing is a least (grounded)
    fixpoint, not a greatest-fixpoint/2-core prune that a self-sustaining
    ring would satisfy. A separate signer grounded by two real anchors DOES
    attain standing in the same file, isolating the effect to the ring."""
    a1, ka1 = hid(), hid()
    a2, ka2 = hid(), hid()
    g, kg = hid(), hid()
    r1, k1 = hid(), hid()
    r2, k2 = hid(), hid()
    r3, k3 = hid(), hid()
    rid, dig = hid(), hid()
    tg = tag_of(kg, rid, g, dig)
    t1, t2, t3 = (tag_of(k1, rid, r1, dig), tag_of(k2, rid, r2, dig),
                  tag_of(k3, rid, r3, dig))
    recs = [
        ("enroll", a1, ka1), ("enroll", a2, ka2), ("anchor", a1), ("anchor", a2),
        ("enroll", g, kg), ("enroll", r1, k1), ("enroll", r2, k2), ("enroll", r3, k3),
        ("vouch", a1, g), ("vouch", a2, g),
        ("vouch", r1, r2), ("vouch", r2, r3), ("vouch", r3, r1),
        ("vouch", r2, r1), ("vouch", r3, r2), ("vouch", r1, r3),
        ("release", rid, 1, dig),
        ("cosign", rid, g, tg),
        ("cosign", rid, r1, t1), ("cosign", rid, r2, t2), ("cosign", rid, r3, t3),
    ]
    out = _run_ok(recs + [("authorize", 0, rid, agg_at(recs, rid))])
    assert _verdicts(out) == ["authorized"]
    assert out["decisions"][0]["cosigners"] == 1


def test_standing_vouch_from_non_standing_signer_does_not_count():
    """A vouch from a signer who is not itself in standing does not help its
    target reach the two-voucher threshold, even paired with one real anchor
    vouch."""
    a, ka = hid(), hid()
    x, kx = hid(), hid()
    s, ks = hid(), hid()
    rid, dig = hid(), hid()
    t = tag_of(ks, rid, s, dig)
    recs = [("enroll", a, ka), ("anchor", a), ("enroll", x, kx), ("enroll", s, ks),
            ("vouch", a, s), ("vouch", x, s),
            ("release", rid, 1, dig), ("cosign", rid, s, t)]
    out = _run_ok(recs + [("authorize", 0, rid, h(combine([])))])
    assert _verdicts(out) == ["under_threshold"]
    assert out["decisions"][0]["cosigners"] == 0


def test_standing_anchor_removed_no_longer_grounds():
    """An anchor that is later removed no longer grounds anyone at a query
    positioned after the removal, even though it grounded the same signer
    earlier."""
    a1, ka1 = hid(), hid()
    a2, ka2 = hid(), hid()
    s, ks = hid(), hid()
    rid, dig = hid(), hid()
    t = tag_of(ks, rid, s, dig)
    base = [("enroll", a1, ka1), ("enroll", a2, ka2), ("anchor", a1), ("anchor", a2),
            ("enroll", s, ks), ("vouch", a1, s), ("vouch", a2, s),
            ("release", rid, 1, dig), ("cosign", rid, s, t)]
    out = _run_ok(base + [("authorize", 0, rid, agg_at(base, rid))])
    assert _verdicts(out) == ["authorized"]
    removed = base + [("remove", a1)]
    out2 = _run_ok(removed + [("authorize", 0, rid, h(combine([])))])
    assert _verdicts(out2) == ["under_threshold"]
    assert out2["decisions"][0]["cosigners"] == 0


# --------------------------------------------------------------------------
# Schema / malformed anchors
# --------------------------------------------------------------------------

def test_schema_anchor_unenrolled_sid():
    out = _run_ok([("anchor", hid())])
    assert out["status"] == "malformed"


def test_schema_vouch_unenrolled_voucher():
    s = hid()
    out = _run_ok([("enroll", s, hid()), ("vouch", hid(), s)])
    assert out["status"] == "malformed"


def test_schema_vouch_unenrolled_target():
    s = hid()
    out = _run_ok([("enroll", s, hid()), ("vouch", s, hid())])
    assert out["status"] == "malformed"


def test_schema_vouch_self():
    s = hid()
    out = _run_ok([("enroll", s, hid()), ("vouch", s, s)])
    assert out["status"] == "malformed"


def test_schema_duplicate_release():
    rid, dig = hid(), hid()
    out = _run_ok([("release", rid, 1, dig), ("release", rid, 2, dig)])
    assert out["status"] == "malformed"
    assert out["releases"] == [] and out["release_count"] == 0


def test_schema_negative_threshold():
    rid, dig = hid(), hid()
    out = _run_ok([("release", rid, -1, dig)])
    assert out["status"] == "malformed"


def test_schema_cosign_unknown_release():
    k, s = hid(), hid()
    out = _run_ok([("enroll", s, k), ("cosign", hid(), s, hid())])
    assert out["status"] == "malformed"


def test_schema_cosign_unenrolled_signer():
    rid, dig = hid(), hid()
    out = _run_ok([("release", rid, 1, dig), ("cosign", rid, hid(), hid())])
    assert out["status"] == "malformed"


def test_schema_rotate_remove_unenrolled():
    assert _run_ok([("rotate", hid(), hid())])["status"] == "malformed"
    assert _run_ok([("remove", hid())])["status"] == "malformed"


def test_schema_authorize_seq_out_of_order():
    rid, dig = hid(), hid()
    out = _run_ok([("release", rid, 1, dig), ("authorize", 2, rid, hid())])
    assert out["status"] == "malformed"


# --------------------------------------------------------------------------
# Exit codes and parsing
# --------------------------------------------------------------------------

def test_exit_wrong_args():
    proc = subprocess.run([AUDIT], capture_output=True, text=True, check=False)
    assert proc.returncode == 2
    proc = subprocess.run([AUDIT, "a", "b"], capture_output=True, text=True, check=False)
    assert proc.returncode == 2


def test_exit_unreadable_file():
    proc, _ = _run("/nonexistent/ledger.txt")
    assert proc.returncode == 1


def test_exit_unknown_keyword():
    proc, _ = _run(_write_raw("mint aaaa\n"))
    assert proc.returncode == 3


def test_exit_wrong_field_count():
    proc, _ = _run(_write_raw(f"enroll {hid()}\n"))
    assert proc.returncode == 3


def test_exit_bad_hex():
    proc, _ = _run(_write_raw(f"enroll {'Z' * 16} {hid()}\n"))
    assert proc.returncode == 3


def test_exit_non_integer_threshold():
    proc, _ = _run(_write_raw(f"release {hid()} two {hid()}\n"))
    assert proc.returncode == 3


def test_exit_non_utf8():
    proc, _ = _run(_write_raw(b"enroll \xff\xfe 1 -\n", binary=True))
    assert proc.returncode == 3


def test_comments_and_blanks_ignored():
    k, s, rid, dig = hid(), hid(), hid(), hid()
    t = tag_of(k, rid, s, dig)
    body = [("enroll", s, k), ("release", rid, 1, dig), ("cosign", rid, s, t)]
    agg = agg_at(body, rid)
    text = (f"# release ledger\n\nenroll {s} {k}\n   \n"
            f"release {rid} 1 {dig}\ncosign {rid} {s} {t}\n"
            f"authorize 0 {rid} {agg}\n")
    proc, parsed = _run(_write_raw(text))
    assert proc.returncode == 0
    assert [d["verdict"] for d in parsed["decisions"]] == ["authorized"]


def test_stale_root_owned_result_is_replaced():
    if os.geteuid() != 0:
        pytest.skip("needs root to plant the stale file")
    if os.path.exists(RESULT):
        os.remove(RESULT)
    with open(RESULT, "w") as f:
        f.write("{}")
    os.chmod(RESULT, 0o644)
    k, s, rid, dig = hid(), hid(), hid(), hid()
    t = tag_of(k, rid, s, dig)
    base = [("enroll", s, k), ("release", rid, 1, dig), ("cosign", rid, s, t)]
    out = _run_ok(base + [("authorize", 0, rid, agg_at(base, rid))])
    assert _verdicts(out) == ["authorized"]


# --------------------------------------------------------------------------
# Randomized agreement sweep
# --------------------------------------------------------------------------

def _rand_recs():
    recs = []
    signers = []
    keys = {}
    releases = []
    audits = 0
    for _ in range(RNG.randint(1, 4)):
        s, k = hid(), hid()
        recs.append(("enroll", s, k))
        signers.append(s)
        keys[s] = k
    for _ in range(RNG.randint(1, 3)):
        rid, dig, k = hid(), hid(), RNG.randint(0, 4)
        recs.append(("release", rid, k, dig))
        releases.append((rid, k, dig))
    for _ in range(RNG.randint(3, 16)):
        roll = RNG.random()
        if roll < 0.12 and len(signers) < 6:
            s, k = hid(), hid()
            recs.append(("enroll", s, k))
            signers.append(s)
            keys[s] = k
        elif roll < 0.20 and signers:
            recs.append(("remove", RNG.choice(signers)))
        elif roll < 0.32 and signers:
            s, nk = RNG.choice(signers), hid()
            recs.append(("rotate", s, nk))
            keys[s] = nk
        elif roll < 0.36:
            rid, dig, k = hid(), hid(), RNG.randint(0, 4)
            recs.append(("release", rid, k, dig))
            releases.append((rid, k, dig))
        elif roll < 0.72 and signers and releases:
            rid, _, dig = RNG.choice(releases)
            s = RNG.choice(signers)
            mode = RNG.random()
            if mode < 0.6 and s in keys:
                tag = tag_of(keys[s], rid, s, dig)
            elif mode < 0.8:
                tag = tag_of(hid(), rid, s, dig)
            else:
                tag = hid()
            recs.append(("cosign", rid, s, tag))
        else:
            if not releases:
                continue
            rid, k, dig = RNG.choice(releases)
            claim = hid() if RNG.random() < 0.5 else agg_at(recs, rid)
            recs.append(("authorize", audits, rid, claim))
            audits += 1
    return recs


def test_many_random_agree():
    """Run the executable on many fresh random ledgers spanning every axis
    (enroll/remove rosters, key rotations voiding earlier cosignatures, valid
    and forged and stale-key tags, the order-dependent aggregate, the k-of-n
    threshold, positional unknown_release, the verdict precedence, and the
    end-state releases pass) and require the full output object to match the
    independent reference every time."""
    for _ in range(240):
        recs = _rand_recs()
        exp = reference(recs)
        path = _write(recs)
        proc, parsed = _run(path)
        assert proc.returncode == 0, proc.stderr
        assert parsed == exp, (f"\n got {parsed}\n exp {exp}\n"
                               f" file=\n{serialize(recs)}")


def _rand_recs_standing():
    """Same shape as _rand_recs, but also emits anchor designations and
    vouches, exercising the section 5.5 standing gate (including anchor-less
    mutual-vouch dead ends) alongside every existing axis."""
    recs = []
    signers = []
    keys = {}
    releases = []
    audits = 0
    for _ in range(RNG.randint(2, 5)):
        s, k = hid(), hid()
        recs.append(("enroll", s, k))
        signers.append(s)
        keys[s] = k
    for a in RNG.sample(signers, RNG.randint(1, min(2, len(signers)))):
        recs.append(("anchor", a))
    for _ in range(RNG.randint(1, 3)):
        rid, dig, k = hid(), hid(), RNG.randint(0, 4)
        recs.append(("release", rid, k, dig))
        releases.append((rid, k, dig))
    for _ in range(RNG.randint(6, 24)):
        roll = RNG.random()
        if roll < 0.10 and len(signers) < 8:
            s, k = hid(), hid()
            recs.append(("enroll", s, k))
            signers.append(s)
            keys[s] = k
        elif roll < 0.16 and signers:
            recs.append(("remove", RNG.choice(signers)))
        elif roll < 0.24 and signers:
            s, nk = RNG.choice(signers), hid()
            recs.append(("rotate", s, nk))
            keys[s] = nk
        elif roll < 0.27:
            rid, dig, k = hid(), hid(), RNG.randint(0, 4)
            recs.append(("release", rid, k, dig))
            releases.append((rid, k, dig))
        elif roll < 0.55 and len(signers) >= 2:
            voucher, target = RNG.sample(signers, 2)
            recs.append(("vouch", voucher, target))
        elif roll < 0.80 and signers and releases:
            rid, _, dig = RNG.choice(releases)
            s = RNG.choice(signers)
            mode = RNG.random()
            if mode < 0.6 and s in keys:
                tag = tag_of(keys[s], rid, s, dig)
            elif mode < 0.8:
                tag = tag_of(hid(), rid, s, dig)
            else:
                tag = hid()
            recs.append(("cosign", rid, s, tag))
        else:
            if not releases:
                continue
            rid, k, dig = RNG.choice(releases)
            claim = hid() if RNG.random() < 0.5 else agg_at(recs, rid)
            recs.append(("authorize", audits, rid, claim))
            audits += 1
    return recs


def test_many_random_agree_with_standing():
    """Same randomized-agreement sweep as test_many_random_agree, but every
    fixture also carries anchors and vouches, so the section 5.5
    least-fixpoint standing gate (grounded chains and anchor-less
    mutual-vouch rings alike) is checked against the independent reference
    across many fresh random ledgers, not just the pinned cases above."""
    for _ in range(200):
        recs = _rand_recs_standing()
        exp = reference(recs)
        path = _write(recs)
        proc, parsed = _run(path)
        assert proc.returncode == 0, proc.stderr
        assert parsed == exp, (f"\n got {parsed}\n exp {exp}\n"
                               f" file=\n{serialize(recs)}")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-rA"]))
