"""Independent HPACK decode + witness-checking oracle for hpackward.

This module is the verifier's ground truth. It decodes an HPACK header block
under a spec-compliant RFC 7541 reference maintainer and under the audited
maintainer observed in evidence/decoder.rs, and it checks whether a candidate
*witness block* realizes a requested interpretation-conflict (a divergence at an
exact emitted position, attributable to one isolated audited deviation, with a
specified accept/reject outcome). It never trusts the candidate program and
never reads the audited decoder source under evidence/, so a modified target
cannot influence grading.

The reference and audited maintainers share one octet grammar and one Huffman
codec table. They differ only in a few independent, disclosed respects, each
toggled here by a name in a ``bugs`` set:

  * ``overhead`` -- the per-entry dynamic-table size overhead. The reference
    charges name+value+32 octets (RFC 7541 4.1); the audited maintainer charges
    name+value, so it evicts less and retains entries the reference drops.
  * ``never``    -- the table effect of a Literal Header Field Never Indexed
    (0x10). The reference inserts nothing; the audited maintainer inserts it,
    shifting later dynamic indices.
  * ``huff``     -- Huffman padding validation (RFC 7541 5.2). The reference
    rejects padding that is not the all-ones EOS prefix (or is over-long, or
    decodes an EOS symbol); the audited maintainer accepts non-EOS padding.
  * ``sizeupdate`` -- the eviction step of a Dynamic Table Size Update. The
    reference evicts from the oldest end until the table fits the new maximum;
    the audited maintainer lowers the maximum but skips the eviction, retaining
    entries the reference drops.
  * ``minint`` -- integer minimality (RFC 7541 5.1 security note). The reference
    accepts any integer within the six-continuation-octet cap; the audited
    maintainer additionally *rejects* an integer whose continuation is not the
    minimal-length encoding of its value, and a rejected integer aborts the
    decode. This deviation makes the audited decoder *stricter* than the
    reference, so it can reject a block the reference accepts.

The four table/padding deviations each make the audited decoder more permissive
than the reference; ``minint`` is the one respect in which it is stricter. The
reference is ``bugs == set()``; the full audited decoder is
``bugs == {"overhead", "never", "huff", "sizeupdate", "minint"}``. Enabling any
subset yields the model used for mechanism attribution (single names for isolated
deviations, larger subsets for joint obligations whose conflict needs several
deviations acting together).
"""

PROTOCOL_MAX = 4096

STATIC = [
    (b":authority", b""),
    (b":method", b"GET"),
    (b":method", b"POST"),
    (b":path", b"/"),
    (b":path", b"/index.html"),
    (b":scheme", b"http"),
    (b":scheme", b"https"),
    (b":status", b"200"),
    (b":status", b"204"),
    (b":status", b"206"),
    (b":status", b"304"),
    (b":status", b"400"),
    (b":status", b"404"),
    (b":status", b"500"),
    (b"accept-charset", b""),
    (b"accept-encoding", b"gzip, deflate"),
    (b"accept-language", b""),
    (b"accept-ranges", b""),
    (b"accept", b""),
    (b"access-control-allow-origin", b""),
    (b"age", b""),
    (b"allow", b""),
    (b"authorization", b""),
    (b"cache-control", b""),
    (b"content-disposition", b""),
    (b"content-encoding", b""),
    (b"content-language", b""),
    (b"content-length", b""),
    (b"content-location", b""),
    (b"content-range", b""),
    (b"content-type", b""),
    (b"cookie", b""),
    (b"date", b""),
    (b"etag", b""),
    (b"expect", b""),
    (b"expires", b""),
    (b"from", b""),
    (b"host", b""),
    (b"if-match", b""),
    (b"if-modified-since", b""),
    (b"if-none-match", b""),
    (b"if-range", b""),
    (b"if-unmodified-since", b""),
    (b"last-modified", b""),
    (b"link", b""),
    (b"location", b""),
    (b"max-forwards", b""),
    (b"proxy-authenticate", b""),
    (b"proxy-authorization", b""),
    (b"range", b""),
    (b"referer", b""),
    (b"refresh", b""),
    (b"retry-after", b""),
    (b"server", b""),
    (b"set-cookie", b""),
    (b"strict-transport-security", b""),
    (b"transfer-encoding", b""),
    (b"user-agent", b""),
    (b"vary", b""),
    (b"via", b""),
    (b"www-authenticate", b""),
]
STATIC_LEN = len(STATIC)

# RFC 7541 Appendix B canonical Huffman code, indexed by symbol 0..256 (256=EOS).
HUFF = [
    (0x1FF8, 13),
    (0x7FFFD8, 23),
    (0xFFFFFE2, 28),
    (0xFFFFFE3, 28),
    (0xFFFFFE4, 28),
    (0xFFFFFE5, 28),
    (0xFFFFFE6, 28),
    (0xFFFFFE7, 28),
    (0xFFFFFE8, 28),
    (0xFFFFEA, 24),
    (0x3FFFFFFC, 30),
    (0xFFFFFE9, 28),
    (0xFFFFFEA, 28),
    (0x3FFFFFFD, 30),
    (0xFFFFFEB, 28),
    (0xFFFFFEC, 28),
    (0xFFFFFED, 28),
    (0xFFFFFEE, 28),
    (0xFFFFFEF, 28),
    (0xFFFFFF0, 28),
    (0xFFFFFF1, 28),
    (0xFFFFFF2, 28),
    (0x3FFFFFFE, 30),
    (0xFFFFFF3, 28),
    (0xFFFFFF4, 28),
    (0xFFFFFF5, 28),
    (0xFFFFFF6, 28),
    (0xFFFFFF7, 28),
    (0xFFFFFF8, 28),
    (0xFFFFFF9, 28),
    (0xFFFFFFA, 28),
    (0xFFFFFFB, 28),
    (0x14, 6),
    (0x3F8, 10),
    (0x3F9, 10),
    (0xFFA, 12),
    (0x1FF9, 13),
    (0x15, 6),
    (0xF8, 8),
    (0x7FA, 11),
    (0x3FA, 10),
    (0x3FB, 10),
    (0xF9, 8),
    (0x7FB, 11),
    (0xFA, 8),
    (0x16, 6),
    (0x17, 6),
    (0x18, 6),
    (0x0, 5),
    (0x1, 5),
    (0x2, 5),
    (0x19, 6),
    (0x1A, 6),
    (0x1B, 6),
    (0x1C, 6),
    (0x1D, 6),
    (0x1E, 6),
    (0x1F, 6),
    (0x5C, 7),
    (0xFB, 8),
    (0x7FFC, 15),
    (0x20, 6),
    (0xFFB, 12),
    (0x3FC, 10),
    (0x1FFA, 13),
    (0x21, 6),
    (0x5D, 7),
    (0x5E, 7),
    (0x5F, 7),
    (0x60, 7),
    (0x61, 7),
    (0x62, 7),
    (0x63, 7),
    (0x64, 7),
    (0x65, 7),
    (0x66, 7),
    (0x67, 7),
    (0x68, 7),
    (0x69, 7),
    (0x6A, 7),
    (0x6B, 7),
    (0x6C, 7),
    (0x6D, 7),
    (0x6E, 7),
    (0x6F, 7),
    (0x70, 7),
    (0x71, 7),
    (0x72, 7),
    (0xFC, 8),
    (0x73, 7),
    (0xFD, 8),
    (0x1FFB, 13),
    (0x7FFF0, 19),
    (0x1FFC, 13),
    (0x3FFC, 14),
    (0x22, 6),
    (0x7FFD, 15),
    (0x3, 5),
    (0x23, 6),
    (0x4, 5),
    (0x24, 6),
    (0x5, 5),
    (0x25, 6),
    (0x26, 6),
    (0x27, 6),
    (0x6, 5),
    (0x74, 7),
    (0x75, 7),
    (0x28, 6),
    (0x29, 6),
    (0x2A, 6),
    (0x7, 5),
    (0x2B, 6),
    (0x76, 7),
    (0x2C, 6),
    (0x8, 5),
    (0x9, 5),
    (0x2D, 6),
    (0x77, 7),
    (0x78, 7),
    (0x79, 7),
    (0x7A, 7),
    (0x7B, 7),
    (0x7FFE, 15),
    (0x7FC, 11),
    (0x3FFD, 14),
    (0x1FFD, 13),
    (0xFFFFFFC, 28),
    (0xFFFE6, 20),
    (0x3FFFD2, 22),
    (0xFFFE7, 20),
    (0xFFFE8, 20),
    (0x3FFFD3, 22),
    (0x3FFFD4, 22),
    (0x3FFFD5, 22),
    (0x7FFFD9, 23),
    (0x3FFFD6, 22),
    (0x7FFFDA, 23),
    (0x7FFFDB, 23),
    (0x7FFFDC, 23),
    (0x7FFFDD, 23),
    (0x7FFFDE, 23),
    (0xFFFFEB, 24),
    (0x7FFFDF, 23),
    (0xFFFFEC, 24),
    (0xFFFFED, 24),
    (0x3FFFD7, 22),
    (0x7FFFE0, 23),
    (0xFFFFEE, 24),
    (0x7FFFE1, 23),
    (0x7FFFE2, 23),
    (0x7FFFE3, 23),
    (0x7FFFE4, 23),
    (0x1FFFDC, 21),
    (0x3FFFD8, 22),
    (0x7FFFE5, 23),
    (0x3FFFD9, 22),
    (0x7FFFE6, 23),
    (0x7FFFE7, 23),
    (0xFFFFEF, 24),
    (0x3FFFDA, 22),
    (0x1FFFDD, 21),
    (0xFFFE9, 20),
    (0x3FFFDB, 22),
    (0x3FFFDC, 22),
    (0x7FFFE8, 23),
    (0x7FFFE9, 23),
    (0x1FFFDE, 21),
    (0x7FFFEA, 23),
    (0x3FFFDD, 22),
    (0x3FFFDE, 22),
    (0xFFFFF0, 24),
    (0x1FFFDF, 21),
    (0x3FFFDF, 22),
    (0x7FFFEB, 23),
    (0x7FFFEC, 23),
    (0x1FFFE0, 21),
    (0x1FFFE1, 21),
    (0x3FFFE0, 22),
    (0x1FFFE2, 21),
    (0x7FFFED, 23),
    (0x3FFFE1, 22),
    (0x7FFFEE, 23),
    (0x7FFFEF, 23),
    (0xFFFEA, 20),
    (0x3FFFE2, 22),
    (0x3FFFE3, 22),
    (0x3FFFE4, 22),
    (0x7FFFF0, 23),
    (0x3FFFE5, 22),
    (0x3FFFE6, 22),
    (0x7FFFF1, 23),
    (0x3FFFFE0, 26),
    (0x3FFFFE1, 26),
    (0xFFFEB, 20),
    (0x7FFF1, 19),
    (0x3FFFE7, 22),
    (0x7FFFF2, 23),
    (0x3FFFE8, 22),
    (0x1FFFFEC, 25),
    (0x3FFFFE2, 26),
    (0x3FFFFE3, 26),
    (0x3FFFFE4, 26),
    (0x7FFFFDE, 27),
    (0x7FFFFDF, 27),
    (0x3FFFFE5, 26),
    (0xFFFFF1, 24),
    (0x1FFFFED, 25),
    (0x7FFF2, 19),
    (0x1FFFE3, 21),
    (0x3FFFFE6, 26),
    (0x7FFFFE0, 27),
    (0x7FFFFE1, 27),
    (0x3FFFFE7, 26),
    (0x7FFFFE2, 27),
    (0xFFFFF2, 24),
    (0x1FFFE4, 21),
    (0x1FFFE5, 21),
    (0x3FFFFE8, 26),
    (0x3FFFFE9, 26),
    (0xFFFFFFD, 28),
    (0x7FFFFE3, 27),
    (0x7FFFFE4, 27),
    (0x7FFFFE5, 27),
    (0xFFFEC, 20),
    (0xFFFFF3, 24),
    (0xFFFED, 20),
    (0x1FFFE6, 21),
    (0x3FFFEA, 22),
    (0x1FFFE7, 21),
    (0x1FFFE8, 21),
    (0x7FFFF3, 23),
    (0x3FFFEB, 22),
    (0x3FFFE9, 22),
    (0x1FFFFEE, 25),
    (0x1FFFFEF, 25),
    (0xFFFFF4, 24),
    (0xFFFFF5, 24),
    (0x3FFFFEA, 26),
    (0x7FFFF4, 23),
    (0x3FFFFEB, 26),
    (0x7FFFFE6, 27),
    (0x3FFFFEC, 26),
    (0x3FFFFED, 26),
    (0x7FFFFE7, 27),
    (0x7FFFFE8, 27),
    (0x7FFFFE9, 27),
    (0x7FFFFEA, 27),
    (0x7FFFFEB, 27),
    (0xFFFFFFE, 28),
    (0x7FFFFEC, 27),
    (0x7FFFFED, 27),
    (0x7FFFFEE, 27),
    (0x7FFFFEF, 27),
    (0x7FFFFF0, 27),
    (0x3FFFFEE, 26),
    (0x3FFFFFFF, 30),
]


class DecodeError(Exception):
    pass


def _build_trie():
    root = {}
    for sym in range(257):
        code, n = HUFF[sym]
        node = root
        for k in range(n - 1, -1, -1):
            bit = (code >> k) & 1
            if k == 0:
                node[bit] = ("leaf", sym)
            else:
                nxt = node.get(bit)
                if nxt is None or nxt[0] == "leaf":
                    nxt = ("node", {})
                    node[bit] = nxt
                node = nxt[1]
    return root


_TRIE = _build_trie()


def huff_encode(data, bad_pad=False):
    """Encode with the RFC Huffman code. Padding is the all-ones EOS prefix
    unless bad_pad, which pads with zero bits (invalid). Returns (bytes, npad)."""
    bits = []
    for byte in data:
        code, n = HUFF[byte]
        bits.extend((code >> k) & 1 for k in range(n - 1, -1, -1))
    npad = (-len(bits)) % 8
    bits.extend([0 if bad_pad else 1] * npad)
    out = bytearray()
    for i in range(0, len(bits), 8):
        v = 0
        for b in bits[i : i + 8]:
            v = (v << 1) | b
        out.append(v)
    return bytes(out), npad


def _tail_bits(data, n):
    total = len(data) * 8
    return [(data[i // 8] >> (7 - (i % 8))) & 1 for i in range(total - n, total)]


def huff_decode(data, strict):
    """Decode Huffman octets. strict enforces the three RFC 7541 5.2 rules
    (padding <= 7 bits, all-ones EOS prefix, no decoded EOS); lax skips the
    all-ones check but still decodes identical symbols."""
    node = _TRIE
    out = bytearray()
    depth = 0
    for byte in data:
        for k in range(7, -1, -1):
            bit = (byte >> k) & 1
            step = node.get(bit)
            if step is None:
                raise DecodeError("huffman: no such code")
            if step[0] == "leaf":
                if step[1] == 256:
                    raise DecodeError("huffman: EOS symbol")
                out.append(step[1])
                node = _TRIE
                depth = 0
            else:
                node = step[1]
                depth += 1
    if node is not _TRIE:
        if depth > 7:
            raise DecodeError("huffman: padding too long")
        if strict and any(b != 1 for b in _tail_bits(data, depth)):
            raise DecodeError("huffman: padding not EOS prefix")
    return bytes(out)


def _minimal_continuation_octets(residual):
    """Number of continuation octets the minimal HPACK encoding uses for the
    portion of an integer beyond a saturated prefix (RFC 7541 5.1). A saturated
    prefix always spends at least one continuation octet (encoding residual 0 as
    a single 0x00)."""
    if residual == 0:
        return 1
    n = 0
    while residual > 0:
        residual >>= 7
        n += 1
    return n


def read_int(buf, pos, prefix_bits, strict_minimal=False):
    if pos >= len(buf):
        raise DecodeError("truncated prefix")
    mask = (1 << prefix_bits) - 1
    value = buf[pos] & mask
    pos += 1
    if value < mask:
        return value, pos
    shift = 0
    octets = 0
    while True:
        if pos >= len(buf):
            raise DecodeError("truncated continuation")
        b = buf[pos]
        pos += 1
        octets += 1
        if octets > 6:
            raise DecodeError("integer too long")
        value += (b & 0x7F) << shift
        shift += 7
        if (b & 0x80) == 0:
            break
    if strict_minimal and octets > _minimal_continuation_octets(value - mask):
        raise DecodeError("integer not minimally encoded")
    return value, pos


def read_string(buf, pos, huff_strict, strict_minimal=False):
    if pos >= len(buf):
        raise DecodeError("truncated string header")
    huffman = (buf[pos] & 0x80) != 0
    length, pos = read_int(buf, pos, 7, strict_minimal)
    if pos + length > len(buf):
        raise DecodeError("truncated string body")
    raw = bytes(buf[pos : pos + length])
    pos += length
    if huffman:
        return huff_decode(raw, huff_strict), pos
    return raw, pos


def decode(buf, max0, bugs):
    """Return (emitted, error_at). emitted is the list of (name, value) fields
    emitted before any error; error_at is the emit index at which a fatal decode
    error occurred, or None if the block decoded fully. ``bugs`` selects the
    maintainer (see the module docstring)."""
    overhead = 0 if "overhead" in bugs else 32
    never_ins = "never" in bugs
    huff_strict = "huff" not in bugs
    sizeupd_skip = "sizeupdate" in bugs
    strict_min = "minint" in bugs
    dyn = []
    cur_max = max0
    size = 0
    emitted = []
    pos = 0

    def esize(n, v):
        return len(n) + len(v) + overhead

    def insert(n, v):
        nonlocal size
        es = esize(n, v)
        if es > cur_max:
            dyn.clear()
            size = 0
            return
        limit = cur_max - es
        while dyn and size > limit:
            nn, vv = dyn.pop()
            size -= esize(nn, vv)
        dyn.insert(0, (n, v))
        size += es

    def resolve(idx):
        if idx == 0:
            raise DecodeError("index 0")
        if idx <= STATIC_LEN:
            return STATIC[idx - 1]
        di = idx - STATIC_LEN - 1
        if di >= len(dyn):
            raise DecodeError("dynamic index out of range")
        return dyn[di]

    try:
        while pos < len(buf):
            b = buf[pos]
            if b & 0x80:
                idx, pos = read_int(buf, pos, 7, strict_min)
                emitted.append(resolve(idx))
            elif b & 0x40:
                idx, pos = read_int(buf, pos, 6, strict_min)
                if idx == 0:
                    name, pos = read_string(buf, pos, huff_strict, strict_min)
                else:
                    name, _ = resolve(idx)
                value, pos = read_string(buf, pos, huff_strict, strict_min)
                emitted.append((name, value))
                insert(name, value)
            elif b & 0x20:
                newmax, pos = read_int(buf, pos, 5, strict_min)
                if newmax > PROTOCOL_MAX:
                    raise DecodeError("size update above protocol maximum")
                cur_max = newmax
                if not sizeupd_skip:
                    while dyn and size > cur_max:
                        nn, vv = dyn.pop()
                        size -= esize(nn, vv)
            else:
                never = (b & 0x10) != 0
                idx, pos = read_int(buf, pos, 4, strict_min)
                if idx == 0:
                    name, pos = read_string(buf, pos, huff_strict, strict_min)
                else:
                    name, _ = resolve(idx)
                value, pos = read_string(buf, pos, huff_strict, strict_min)
                emitted.append((name, value))
                if never and never_ins:
                    insert(name, value)
    except DecodeError:
        return emitted, len(emitted)
    return emitted, None


REF = frozenset()
AUD = frozenset({"overhead", "never", "huff", "sizeupdate", "minint"})

# Each obligation mechanism token maps to the set of low-level deviation names
# whose *joint* action the obligation blames for the conflict. Single-deviation
# tokens map to a one-element set; a "+"-joined token (e.g. "never+sizeupdate")
# maps to the several deviations a joint obligation requires together.
_MECH_ATOM = {
    "overhead": "overhead",
    "never": "never",
    "huffpad": "huff",
    "sizeupdate": "sizeupdate",
    "minint": "minint",
}


def mech_bugs(mech):
    """Resolve an obligation mechanism token to its frozenset of deviations."""
    atoms = []
    for part in mech.split("+"):
        if part not in _MECH_ATOM:
            return None
        atoms.append(_MECH_ATOM[part])
    return frozenset(atoms)


MECHANISMS = ("overhead", "never", "huffpad", "sizeupdate", "minint")
OUTCOMES = ("both_accept", "reference_reject", "audited_reject")


def first_divergence(ref_em, aud_em):
    """First emitted position where the reference and audited sequences differ,
    with the field taken from the audited side when it has one there (else the
    reference side). None when the sequences are identical."""
    n = max(len(ref_em), len(aud_em))
    for p in range(n):
        r = ref_em[p] if p < len(ref_em) else None
        a = aud_em[p] if p < len(aud_em) else None
        if r != a:
            return p, (a if a is not None else r)
    return None


def parse_obligation(line):
    ob = {}
    for tok in line.split():
        if "=" not in tok:
            continue
        k, v = tok.split("=", 1)
        ob[k] = v
    return {
        "mech": ob["mech"],
        "outcome": ob["outcome"],
        "pos": int(ob["pos"]),
        "max": int(ob["max"]),
        "maxlen": int(ob["maxlen"]),
        "huff": ob.get("huff", "none"),
    }


def _uses_huffman(buf):
    """Structurally scan the representation grammar for any Huffman-flagged
    string literal."""
    pos = 0
    try:
        while pos < len(buf):
            b = buf[pos]
            if b & 0x80:
                _, pos = read_int(buf, pos, 7)
            elif b & 0x40:
                idx, pos = read_int(buf, pos, 6)
                if idx == 0:
                    if pos < len(buf) and buf[pos] & 0x80:
                        return True
                    _, pos = read_string(buf, pos, True)
                if pos < len(buf) and buf[pos] & 0x80:
                    return True
                _, pos = read_string(buf, pos, False)
            elif b & 0x20:
                _, pos = read_int(buf, pos, 5)
            else:
                idx, pos = read_int(buf, pos, 4)
                if idx == 0:
                    if pos < len(buf) and buf[pos] & 0x80:
                        return True
                    _, pos = read_string(buf, pos, True)
                if pos < len(buf) and buf[pos] & 0x80:
                    return True
                _, pos = read_string(buf, pos, False)
    except DecodeError:
        pass
    return False


def check_witness(raw, ob):
    """Return (ok, reason). ok is True iff the witness block ``raw`` realizes the
    obligation ``ob`` exactly: honored initial maximum and length ceiling; a
    reference/audited divergence at the exact emitted position; the specified
    accept/reject outcome; the divergence isolated to the obligation's mechanism
    (that single deviation alone reproduces it, and removing it from the full
    audited decoder heals it at that position); and a Huffman string present when
    required."""
    if len(raw) < 4:
        return False, "block shorter than 4-byte header"
    if len(raw) > ob["maxlen"]:
        return False, f"block length {len(raw)} exceeds maxlen {ob['maxlen']}"
    max0 = int.from_bytes(raw[0:4], "big")
    if max0 != ob["max"]:
        return False, f"initial maximum {max0} != required {ob['max']}"
    buf = raw[4:]
    ref_em, ref_err = decode(buf, max0, REF)
    aud_em, aud_err = decode(buf, max0, AUD)
    d = first_divergence(ref_em, aud_em)
    if d is None:
        return False, "no divergence between reference and audited decoders"
    p, field = d
    if p != ob["pos"]:
        return False, f"divergence at position {p} != required {ob['pos']}"

    r_has = p < len(ref_em)
    a_has = p < len(aud_em)
    if ob["outcome"] == "both_accept":
        if ref_err is not None or aud_err is not None:
            return False, "outcome both_accept: a decoder rejected the block"
    elif ob["outcome"] == "reference_reject":
        if ref_err is None:
            return False, "outcome reference_reject: reference accepted the block"
        if not (a_has and not r_has):
            return (
                False,
                "outcome reference_reject: audited must emit a field the reference lacks at pos",
            )
    elif ob["outcome"] == "audited_reject":
        if aud_err is None:
            return False, "outcome audited_reject: audited accepted the block"
        if not (r_has and not a_has):
            return (
                False,
                "outcome audited_reject: reference must emit a field the audited lacks at pos",
            )
    else:
        return False, f"unknown outcome {ob['outcome']!r}"

    if (ob["huff"] == "required" or ob["mech"] == "huffpad") and not _uses_huffman(buf):
        return False, "obligation requires a Huffman-encoded string; none present"

    bugs = mech_bugs(ob["mech"])
    if bugs is None or not bugs:
        return False, f"unknown mechanism {ob['mech']!r}"

    # Sufficiency: the named deviation set, acting alone over the reference,
    # reproduces the exact conflict (same first-divergence position and field).
    only_em, _ = decode(buf, max0, bugs)
    suff = first_divergence(ref_em, only_em)
    if suff is None or suff[0] != p or suff[1] != field:
        named = ", ".join(sorted(bugs))
        return (
            False,
            f"mechanism not sufficient: enabling only {{{named}}} does not reproduce the exact divergence",
        )

    # Minimality: no proper subset of the named set already reproduces the
    # conflict -- every named deviation genuinely contributes. (For a
    # single-deviation obligation the only proper subset is the reference, which
    # never reproduces, so this is vacuous.)
    for d in bugs:
        sub_em, _ = decode(buf, max0, bugs - {d})
        sub = first_divergence(ref_em, sub_em)
        if sub is not None and sub[0] == p and sub[1] == field:
            return (
                False,
                f"mechanism not minimal: subset without {d} already reproduces the divergence",
            )

    # Necessity: removing any one named deviation from the full audited decoder
    # heals the conflict at pos (they agree there, or first diverge later).
    for d in bugs:
        without_em, _ = decode(buf, max0, AUD - {d})
        nec = first_divergence(ref_em, without_em)
        if not (nec is None or nec[0] > p):
            return (
                False,
                f"mechanism not necessary: removing {d} still diverges at position {p}",
            )
    return True, "ok"
