"""Verifier-side reference witness builder for hpackward's self-consistency
meta-tests. It constructs one satisfying witness per obligation so the suite can
assert that every generated obligation is solvable (oracle sanity) and that the
checker discriminates (a witness for one obligation fails a different one, and a
wrong-mechanism witness fails attribution). It is never shipped in the agent
image and is not used to grade the candidate binary; the candidate is graded
solely on its own emitted witnesses by test_hpackward."""

import hpack_oracle as O


def enc_int(value, prefix_bits, high):
    mask = (1 << prefix_bits) - 1
    if value < mask:
        return bytes([high | value])
    out = [high | mask]
    value -= mask
    while value >= 128:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def enc_str_literal(data):
    return enc_int(len(data), 7, 0x00) + data


def enc_str_huff(data, bad_pad=False):
    enc, _ = O.huff_encode(data, bad_pad=bad_pad)
    return enc_int(len(enc), 7, 0x80) + enc


def indexed(idx):
    return enc_int(idx, 7, 0x80)


def lit_incr_lit(name, value):
    return enc_int(0, 6, 0x40) + enc_str_literal(name) + enc_str_literal(value)


def lit_never_lit(name, value):
    return enc_int(0, 4, 0x10) + enc_str_literal(name) + enc_str_literal(value)


def lit_noindex_idx(name_idx, value_encoded):
    return enc_int(name_idx, 4, 0x00) + value_encoded


def size_update(newmax):
    return enc_int(newmax, 5, 0x20)


def lit_noindex_idx15_nonminimal(value_encoded):
    """A Literal Header Field without Indexing whose 4-bit-prefix name index is
    the static index 15 (accept-charset) encoded *non-minimally* as 0f 80 00 (two
    continuation octets where one suffices). The reference decodes it to index 15
    and emits; the audited maintainer rejects the over-long integer."""
    return b"\x0f\x80\x00" + value_encoded


def block(max0, octets):
    return max0.to_bytes(4, "big") + octets


GET = indexed(2)  # inert filler: emits (:method, GET); static; no table change


def _name(i):
    return ("f" + str(i)).encode()


def _val(n, seed):
    return bytes(97 + ((seed * 7 + k * 13) % 26) for k in range(n))


def valid_huff_filler(seed):
    return lit_noindex_idx(1, enc_str_huff(_val(3 + seed % 4, seed), bad_pad=False))


def construct(ob, oid):
    mech, outcome, pos, M = ob["mech"], ob["outcome"], ob["pos"], ob["max"]
    hf = ob["huff"] == "required"
    fillers = b""
    fill_emits = 0
    if hf and mech != "huffpad":
        fillers += valid_huff_filler(oid)
        fill_emits += 1

    if mech == "never" and outcome == "both_accept":
        need = pos - fill_emits - 2
        assert need >= 0, ("never/both pos too small", ob)
        body = GET * need
        body += lit_incr_lit(_name(oid), _val(6 + oid % 5, oid))
        body += lit_never_lit(_name(100 + oid), _val(5 + oid % 4, oid + 1))
        body += indexed(O.STATIC_LEN + 1)
        return block(M, fillers + body)

    if mech == "never" and outcome == "reference_reject":
        need = pos - fill_emits - 2
        assert need >= 0, ("never/reject pos too small", ob)
        body = GET * need
        body += lit_incr_lit(_name(oid), _val(6 + oid % 5, oid))
        body += lit_never_lit(_name(100 + oid), _val(5 + oid % 4, oid + 1))
        body += indexed(O.STATIC_LEN + 2)
        return block(M, fillers + body)

    if mech == "overhead" and outcome == "reference_reject":
        chosen = None
        for c in range(1, 6):
            if M % c:
                continue
            s = M // c - 32
            if s >= 2 and (c + 1) * s <= M and (pos - fill_emits) >= (c + 1):
                chosen = (c, s)
                break
        assert chosen, ("no overhead params", ob)
        c, s = chosen
        need = pos - fill_emits - (c + 1)
        body = GET * need
        nlen = 2
        for j in range(c + 1):
            nm = _name(j).ljust(nlen, b"z")[:nlen]
            body += lit_incr_lit(nm, _val(s - nlen, oid * 10 + j))
        body += indexed(O.STATIC_LEN + 1 + c)
        return block(M, fillers + body)

    if mech == "sizeupdate" and outcome == "reference_reject":
        # Insert one field via incremental indexing (emitted, and placed in the
        # dynamic table), then a Dynamic Table Size Update to 0. The reference
        # evicts the entry; the audited maintainer keeps it. A following Indexed
        # Header Field at dynamic index 62 is out of range for the reference
        # (rejects) but resolves for the audited (emits the retained field).
        need = pos - fill_emits - 1
        assert need >= 0, ("sizeupdate pos too small", ob)
        body = GET * need
        body += lit_incr_lit(_name(oid), _val(4 + oid % 5, oid))
        body += size_update(0)
        body += indexed(O.STATIC_LEN + 1)
        return block(M, fillers + body)

    if mech == "minint" and outcome == "audited_reject":
        # pos inert fillers, then a Literal without Indexing naming static index
        # 15 via a non-minimal integer. Reference emits (accept-charset, "a");
        # the audited maintainer rejects the over-long index and emits nothing
        # there -- the reference emits a field the audited lacks.
        need = pos - fill_emits
        assert need >= 0, ("minint pos too small", ob)
        body = GET * need
        body += lit_noindex_idx15_nonminimal(enc_str_literal(b"a"))
        return block(M, fillers + body)

    if mech == "never+sizeupdate" and outcome == "reference_reject":
        # A Never-Indexed field emitted at pos-1, then a Size-Update to 0, then a
        # dynamic index at 62. Only the full audited decoder (never inserts the
        # field AND sizeupdate skips the eviction that a size-update-to-0 would
        # otherwise force) still resolves index 62; the reference, and either
        # deviation alone, reject there.
        need = pos - fill_emits - 1
        assert need >= 0, ("never+sizeupdate pos too small", ob)
        body = GET * need
        body += lit_never_lit(_name(oid), _val(4 + oid % 5, oid))
        body += size_update(0)
        body += indexed(O.STATIC_LEN + 1)
        return block(M, fillers + body)

    if mech == "huffpad" and outcome == "reference_reject":
        val = None
        for cand in [b"abc", b"abcd", b"abcde", b"ab", b"abcdef", b"xyz", b"qz"]:
            _, npad = O.huff_encode(cand, bad_pad=True)
            if 1 <= npad <= 7:
                val = cand
                break
        assert val is not None
        need = pos - fill_emits
        body = GET * need
        body += lit_noindex_idx(1, enc_str_huff(val, bad_pad=True))
        return block(M, fillers + body)

    raise AssertionError(("unhandled obligation", ob))
