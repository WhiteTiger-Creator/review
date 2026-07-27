"""Deterministic divergence-obligation generator for hpackward (verifier-side).

Emits a fixed, seed-stable list of (tag, obligation_line) cases. Each obligation
names an interpretation-conflict the candidate must *construct* a witness block
for: which audited deviation must cause the desync (mech), the accept/reject
outcome, the exact emitted-field position of the first divergence (pos), the
honored initial dynamic-table maximum (max), a wire-length ceiling (maxlen), and
whether a Huffman-encoded string is required (huff).

The battery spans all five isolated mechanisms and one joint mechanism across a
range of positions, maxima, and Huffman requirements, so a candidate that has
reverse-engineered only some deviations, or that cannot control the divergence
position, fails many cases. The wire-length ceiling (maxlen) is tight, so a candidate cannot pad a
canned block into shape. No expected witness is encoded here; the independent
hpack_oracle checks whatever the candidate emits. Byte-identical across runs.
"""

MAXLEN = 128


def build_obligations():
    obs = []
    seen = set()
    oid = 0

    def add(mech, outcome, pos, mx, huff):
        nonlocal oid
        tag = f"{mech}_{outcome}_{oid}"
        assert tag not in seen, tag
        seen.add(tag)
        line = f"mech={mech} outcome={outcome} pos={pos} max={mx} maxlen={MAXLEN} huff={huff}"
        obs.append((tag, line))
        oid += 1

    # Never-Indexed value substitution, both decoders accept (gadget emits 2
    # fields before the divergent index; a Huffman filler adds one more).
    for i in range(14):
        hf = "required" if i % 3 == 0 else "none"
        base = 2 + (1 if hf == "required" else 0)
        add("never", "both_accept", base + (i % 7), 4096, hf)

    # Never-Indexed insertion lengthens the audited table so a later index the
    # reference cannot resolve rejects there (reference_reject).
    for i in range(10):
        hf = "required" if i % 4 == 0 else "none"
        base = 2 + (1 if hf == "required" else 0)
        add("never", "reference_reject", base + (i % 6), 4096, hf)

    # Missing +32 overhead: the reference evicts entries the audited retains, so
    # a later dynamic index is out of range for the reference only. max is set to
    # c*(s+32) so exactly c reference entries survive; the candidate must recover
    # a compatible (c, s) for the honored max.
    for i in range(16):
        c = 1 + (i % 3)
        s = 3 + (i % 6)
        mx = c * (s + 32)
        hf = "required" if i % 5 == 0 else "none"
        base = (c + 1) + (1 if hf == "required" else 0)
        add("overhead", "reference_reject", base + (i % 4), mx, hf)

    # Huffman padding: audited accepts non-EOS padding the reference rejects, so
    # the reference stops at that string while the audited emits the field.
    for i in range(14):
        add("huffpad", "reference_reject", i % 8, 4096, "required")

    # Size-update under-eviction: a Dynamic Table Size Update lowers the maximum
    # but the audited maintainer skips the eviction, retaining an entry the
    # reference drops, so a following dynamic index is out of range for the
    # reference only (reference_reject).
    for i in range(12):
        hf = "required" if i % 3 == 0 else "none"
        base = 1 + (1 if hf == "required" else 0)
        add("sizeupdate", "reference_reject", base + (i % 6), 4096, hf)

    # Additional never-substitution cases at higher positions.
    for i in range(10):
        hf = "required" if i % 2 == 0 else "none"
        base = 3 + (1 if hf == "required" else 0)
        add("never", "both_accept", base + (i % 5), 4096, hf)

    # Non-minimal integer rejection: the audited maintainer is *stricter* than
    # the reference here, rejecting an over-long integer the reference accepts.
    # The reference emits the field the over-long index names; the audited aborts
    # the decode -- so the reference emits a field the audited lacks
    # (audited_reject). This is the only outcome family in which the audited
    # decoder rejects a block the reference accepts.
    for i in range(10):
        add("minint", "audited_reject", i % 8, 4096, "none")

    # Joint obligation: the conflict fires only when the Never-Indexed table
    # insertion (never) AND the skipped Size-Update eviction (sizeupdate) act
    # together. Neither alone retains the entry a later dynamic index needs --
    # never alone inserts it but the size update evicts it; sizeupdate alone
    # never inserts it -- so the divergence is attributable to the pair, not to
    # any single deviation. A per-mechanism gadget cannot satisfy it.
    for i in range(10):
        add("never+sizeupdate", "reference_reject", 1 + (i % 7), 4096, "none")

    return obs
