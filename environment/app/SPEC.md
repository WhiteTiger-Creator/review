# Cosign quorum release ledger — reference

This document pins the release-ledger grammar, the whole-file value schema, the
hand-rolled keyed MAC, the order-dependent aggregate combine, the positional
signer-roster and key-rotation semantics, the k-of-n threshold rule, the output
object, the exit codes, and the per-release verdict precedence. Every 64-bit
value is unsigned two's-complement; all arithmetic (`+`, `*`, shifts, rotates)
is computed modulo 2^64 and every intermediate is truncated to 64 bits. Worked
vectors are given for the MAC and the combine so an implementation can be
checked bit-for-bit.

## 1. Ledger grammar

The ledger is UTF-8 text, one record per line. Blank lines and lines whose first
non-space character is `#` are ignored. Tokens are separated by single spaces.
Eight keywords exist:

    enroll <sid> <key>
    remove <sid>
    rotate <sid> <key>
    release <rid> <k> <digest>
    cosign <rid> <sid> <tag>
    authorize <seq> <rid> <claim>
    anchor <sid>
    vouch <voucher-sid> <target-sid>

* `<sid>`, `<rid>`, `<key>`, `<digest>`, `<tag>`, `<claim>`, `<voucher-sid>`,
  `<target-sid>` — exactly 16 lowercase hex characters, each denoting one
  unsigned 64-bit word (most significant nibble first).
* `<k>` — a decimal integer threshold.
* `<seq>` — a decimal integer; the i-th `authorize` line of the file (counting
  from 0) must carry seq = i.

Any line that does not fit this grammar — unknown keyword, wrong field count,
bad hex, uppercase hex, a non-integer where an integer is required, or a file
that is not valid UTF-8 — makes the whole file unparseable: exit 3, nothing
written.

## 2. Whole-file value schema

Checked over the entire file regardless of line order; a violation is reported
as status `malformed` (section 6) with exit 0:

* a `release` rid repeated by another `release` line;
* a negative `<k>` on any `release` line;
* a `cosign` rid that no `release` line anywhere declares;
* a `cosign`, `remove`, `rotate`, or `anchor` sid that no `enroll` line
  anywhere declares;
* a `vouch` line whose voucher or target sid no `enroll` line anywhere
  declares, or whose voucher and target are the same sid;
* an `authorize` seq that is negative or out of order.

An `authorize` rid is exempt: authorizing an rid the file never declares above
the line is schema-valid and yields the `unknown_release` verdict. Repeated
`cosign` lines, repeated `enroll` lines, repeated `anchor` lines for the same
sid, and repeated `vouch` lines for the same voucher/target pair are all
schema-valid.

## 3. The keyed MAC

Each signer tag is a 64-bit keyed MAC of the message `[rid, sid, digest]` under
the signer's key, all four being 64-bit words. Do not use any library MAC;
reproduce this construction exactly. Let `M = 2^64 - 1` and

    ROTL(x, r) = ((x << r) | (x >>> (64 - r))) & M      // logical right shift

with the fixed 64-bit constants

    C0  = 0x736f6d6570736575   C1  = 0x646f72616e646f6d
    C2  = 0x6c7967656e657261   PAD = 0x0f0f0f0f0f0f0f0f
    FIN = 0xff00ff00ff00ff00

The mixing round `RND` transforms a three-word state `(v0, v1, v2)`:

    v0 = (v0 + v1) & M
    v1 = ROTL(v1, 13);  v1 = v1 ^ v0
    v0 = ROTL(v0, 32)
    v2 = (v2 + v0) & M
    v0 = ROTL(v0, 16);  v0 = v0 ^ v2
    v2 = ROTL(v2, 21)
    v1 = (v1 + v2) & M; v2 = v2 ^ v1

`MAC(key, [rid, sid, digest])` is computed as:

    v0 = key ^ C0
    v1 = ROTL(key, 32) ^ C1
    v2 = key ^ C2
    for w in [rid, sid, digest] in that exact order:      // absorb
        v0 = (v0 + w) & M
        v2 = v2 ^ w
        RND; RND                                          // two rounds per word
    v2 = v2 ^ PAD
    RND; RND
    v1 = v1 ^ FIN
    RND
    return (v0 ^ v1 ^ v2) & M

The word order `[rid, sid, digest]` is normative — absorbing the words in any
other order, or padding/finalizing differently, yields a different MAC.

**Worked vector.** With `key = 0f1e2d3c4b5a6978`, `rid = 1111111111111111`,
`sid = aaaaaaaaaaaaaaaa`, `digest = cafebabedeadbeef`, the initial state is
`v0 = 7c7140593b290c0d`, `v1 = 2f351b19617a4251`, `v2 = 63674a59253f1b19`, and

    MAC = 71db7e9206abdec5

## 4. The aggregate combine

The aggregate authorization tag over a set of signer tags is an ordered fold; it
is deliberately **not** an order-independent XOR. Sort the contributing signers
by their sid (ascending, as unsigned 64-bit words) and fold their tags in that
order. With `SEED = 0xc3d2e1f0a1b2c3d4` and `MULT = 0x9e3779b97f4a7c15`:

    acc = SEED
    for t in tags, in ascending signer-id order:
        acc = acc ^ t
        acc = ROTL(acc, 7)
        acc = (acc + MULT) & M
        acc = acc ^ ROTL(t, 40)
    acc = acc ^ (acc >>> 33)
    acc = (acc * 0xff51afd7ed558ccd) & M
    acc = acc ^ (acc >>> 33)
    acc = (acc * 0xc4ceb9fe1a85ec53) & M
    acc = acc ^ (acc >>> 33)
    return acc & M

The `ROTL(acc, 7)` between folds makes the result depend on the fold order, so a
tag folded first mixes differently from one folded last. The aggregate over the
empty set is the finalize of `SEED` alone: `8bd598aebf5e5330`.

**Worked example.** Two signers with `sid = 00000000000000aa` (key
`00000000000000ab`) and `sid = 00000000000000bb` (key `00000000000000cd`), over
`rid = 0123456789abcdef`, `digest = fedcba9876543210`, have tags
`3600208980ae1253` and `3b9040e1997f017f`. Folded in sid order (the `...aa`
signer first) the aggregate is `9b4eb153b4e32286`; folded in the opposite order
it would be `87c1a71047472674` and an XOR would give `0d90606819d1132c` — three
different values, only the first of which is correct.

## 5. Positional roster and release verification

Each `authorize` line is decided using only the lines above it and nothing
below; the final `releases` array (section 6) is a separate whole-file pass.

**Signer roster.** `enroll <sid> <key>` makes sid active from that line on and
sets its key. `remove <sid>` makes sid inactive from that line on. A signer's
**key in force** at a line is the key set by the most recent `enroll` or
`rotate` for that sid at or above the line. A signer is **active** at a line when
the most recent `enroll` or `remove` for that sid strictly above the line is an
`enroll`.

**Key rotation voids earlier cosignatures.** `rotate <sid> <key>` changes sid's
key in force from that line on and **voids every cosignature that sid recorded
before the rotation**. A cosignature recorded before a rotation never counts at
any authorize below that rotation, even though its tag verified under the old
key.

**Cosignature validity.** A `cosign <rid> <sid> <tag>` line at position L counts
toward the release rid at an authorize at position A (with L above A) exactly
when all of the following hold:

* sid has a key in force at L (a cosignature recorded before sid is first
  enrolled has no key and never counts);
* no `rotate` for sid appears strictly between L and A;
* sid is active at A (a removed signer's cosignature does not count);
* the tag equals `MAC(key-in-force-at-L, [rid, sid, digest])`, where digest is
  the digest on rid's `release` line;
* sid has **standing** at A whenever standing gating is active (section 5.5).

A signer counts **once** no matter how many valid cosignatures it holds for the
release; its contributed tag is the valid MAC value. The set of contributing
signers is the distinct such sids.

**Aggregate and threshold.** Let `cosigners` be the number of contributing
signers and `aggregate` be the combine (section 4) of their tags in sid order.
The release's threshold is the `<k>` on its `release` line.

## 5.5 Signer standing

A ledger MAY name **anchors**: `anchor <sid>` marks sid an anchor from that
line on. An anchor's designation is permanent (there is no `unanchor`); only
its *activity*, governed by `enroll`/`remove` exactly as for any other sid,
can lapse. **Standing gating is active for the whole file iff the file
contains at least one `anchor` line anywhere.** If the file contains no
`anchor` line, standing gating is inactive and cosignature counting is
decided by the four bullets above alone, unchanged. Everything below in this
section applies only when standing gating is active.

`vouch <voucher-sid> <target-sid>` records one signer backing another. A
repeated `vouch` for the same voucher/target pair counts once; the order
among `vouch` lines for different targets does not matter.

**Standing at a position A** is the **least** (smallest) set S of sids, each
active at A, such that:

* every anchor active at A is in S;
* any other sid active at A is in S if at least **two distinct** voucher
  sids, each itself already in S, have a `vouch <voucher-sid> sid` line at
  or above A (index < A).

S is the least fixpoint satisfying those two closure conditions, not the
greatest: a sid's membership must be earned by a finite chain of grounded
vouches that terminates at an active anchor. Mutual consistency among a set
of sids that never reaches an anchor by such a chain does not, by itself,
put any of them in S, no matter how many vouches they exchange among
themselves or how the `vouch` lines are ordered or repeated.

## 6. Output object

On success the tool writes this JSON object to `/app/output/result.json` and
prints the identical JSON as a single line to standard output, with keys in
exactly this order:

    {"status": "ok",
     "decisions": [{"seq": 0, "verdict": "authorized",
                    "cosigners": <int>, "aggregate": "<16hex>"}, ...],
     "releases": [{"id": "<rid>", "authorized": <bool>,
                   "cosigners": <int>, "aggregate": "<16hex>"}, ...],
     "authorized_count": <int>, "under_threshold_count": <int>,
     "tag_mismatch_count": <int>, "unknown_count": <int>,
     "release_count": <int>, "authorize_count": <int>}

`decisions` holds one entry per `authorize` line in file order. Each entry
carries `cosigners` (the count of contributing signers at that line) and
`aggregate` (their sid-ordered combine as 16 lowercase hex). For an
`unknown_release` verdict `cosigners` is 0 and `aggregate` is
`0000000000000000`. `releases` lists every declared release in declaration order
with the cosigner count, the sid-ordered aggregate, and `authorized` computed as
`cosigners >= k`, all evaluated under the whole file (the end state). The four
verdict counters count the four verdict strings; `release_count` and
`authorize_count` are the numbers of `release` and `authorize` lines. A schema
failure is reported as

    {"status": "malformed", "decisions": [], "releases": [],
     "authorized_count": 0, "under_threshold_count": 0,
     "tag_mismatch_count": 0, "unknown_count": 0,
     "release_count": 0, "authorize_count": 0}

with exit 0.

## 7. Exit codes

* 0 — ran to completion (status `ok` or `malformed`).
* 1 — the ledger file is unreadable. Nothing is written.
* 2 — wrong argument count. Nothing is written.
* 3 — the ledger is unparseable per section 1. Nothing is written.

## 8. Verdict precedence

For each `authorize <seq> <rid> <claim>` the verdict is the first that holds:

1. `unknown_release` — rid is declared nowhere above the authorize line.
2. `under_threshold` — `cosigners < k`.
3. `tag_mismatch` — `cosigners >= k` but the computed `aggregate` differs from
   the claimed `<claim>`.
4. `authorized` — `cosigners >= k` and the computed `aggregate` equals `<claim>`.

Build the tool as Java source compiled with the JDK standard library alone
(no `javax.crypto`, no third-party jar), fully offline, as an executable at
`/app/audit` taking exactly one argument, the ledger path.

## 9. Worked example

    enroll 00000000000000aa 00000000000000ab
    enroll 00000000000000bb 00000000000000cd
    release 0123456789abcdef 2 fedcba9876543210
    cosign 0123456789abcdef 00000000000000aa 3600208980ae1253
    cosign 0123456789abcdef 00000000000000bb 3b9040e1997f017f
    authorize 0 0123456789abcdef 9b4eb153b4e32286
    rotate 00000000000000aa 00000000000000ff
    authorize 1 0123456789abcdef 87c1a71047472674

Running the tool against this ledger prints exactly:

    {"status": "ok", "decisions": [{"seq": 0, "verdict": "authorized", "cosigners": 2, "aggregate": "9b4eb153b4e32286"}, {"seq": 1, "verdict": "under_threshold", "cosigners": 1, "aggregate": "7d450a340c9c35de"}], "releases": [{"id": "0123456789abcdef", "authorized": false, "cosigners": 1, "aggregate": "7d450a340c9c35de"}], "authorized_count": 1, "under_threshold_count": 1, "tag_mismatch_count": 0, "unknown_count": 0, "release_count": 1, "authorize_count": 2}

This example is a check on shape and bit-exactness only; derive every value in
it — including which cosignatures count at each `authorize` line and why —
from sections 3 through 5 above, not from this output.
