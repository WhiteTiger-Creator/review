"""Independent QR Model 2 reference model for qr-model2-segment-interleave-mask-tournament.

Implements the full label-symbol contract from /app/docs independently of the
C implementation under test: segmentation DP, version fixpoint, codeword
assembly, Reed-Solomon ECC over GF(256), block interleave, matrix build,
mask penalty tournament, and format/version BCH fields.

Every expected value used by the verifier is recomputed here at test time from
the fixture batch files, so stored outputs can never satisfy the tests.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Tables (ISO/IEC 18004, versions 1..12)
# ---------------------------------------------------------------------------

MAX_VERSION = 12

ALNUM_CHARSET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"
ALNUM_INDEX = {ch: i for i, ch in enumerate(ALNUM_CHARSET)}

MODE_NUMERIC = 0
MODE_ALNUM = 1
MODE_BYTE = 2
MODE_NAMES = ("numeric", "alphanumeric", "byte")
MODE_INDICATOR = (0b0001, 0b0010, 0b0100)

# Character-count-indicator widths per (mode, class): class 0 = v1-9, class 1 = v10-26.
CCI_WIDTH = ((10, 12), (9, 11), (8, 16))

# Per version 1..12, per level L,M,Q,H:
# (ec_codewords_per_block, g1_blocks, g1_data_cw, g2_blocks, g2_data_cw)
ECC_BLOCKS = {
    1: {"L": (7, 1, 19, 0, 0), "M": (10, 1, 16, 0, 0), "Q": (13, 1, 13, 0, 0), "H": (17, 1, 9, 0, 0)},
    2: {"L": (10, 1, 34, 0, 0), "M": (16, 1, 28, 0, 0), "Q": (22, 1, 22, 0, 0), "H": (28, 1, 16, 0, 0)},
    3: {"L": (15, 1, 55, 0, 0), "M": (26, 1, 44, 0, 0), "Q": (18, 2, 17, 0, 0), "H": (22, 2, 13, 0, 0)},
    4: {"L": (20, 1, 80, 0, 0), "M": (18, 2, 32, 0, 0), "Q": (26, 2, 24, 0, 0), "H": (16, 4, 9, 0, 0)},
    5: {"L": (26, 1, 108, 0, 0), "M": (24, 2, 43, 0, 0), "Q": (18, 2, 15, 2, 16), "H": (22, 2, 11, 2, 12)},
    6: {"L": (18, 2, 68, 0, 0), "M": (16, 4, 27, 0, 0), "Q": (24, 4, 19, 0, 0), "H": (28, 4, 15, 0, 0)},
    7: {"L": (20, 2, 78, 0, 0), "M": (18, 4, 31, 0, 0), "Q": (18, 2, 14, 4, 15), "H": (26, 4, 13, 1, 14)},
    8: {"L": (24, 2, 97, 0, 0), "M": (22, 2, 38, 2, 39), "Q": (22, 4, 18, 2, 19), "H": (26, 4, 14, 2, 15)},
    9: {"L": (30, 2, 116, 0, 0), "M": (22, 3, 36, 2, 37), "Q": (20, 4, 16, 4, 17), "H": (24, 4, 12, 4, 13)},
    10: {"L": (18, 2, 68, 2, 69), "M": (26, 4, 43, 1, 44), "Q": (24, 6, 19, 2, 20), "H": (28, 6, 15, 2, 16)},
    11: {"L": (20, 4, 81, 0, 0), "M": (30, 1, 50, 4, 51), "Q": (28, 4, 22, 4, 23), "H": (24, 3, 12, 8, 13)},
    12: {"L": (24, 2, 92, 2, 93), "M": (22, 6, 36, 2, 37), "Q": (26, 4, 20, 6, 21), "H": (28, 7, 14, 4, 15)},
}

ALIGNMENT_CENTERS = {
    1: [],
    2: [6, 18],
    3: [6, 22],
    4: [6, 26],
    5: [6, 30],
    6: [6, 34],
    7: [6, 22, 38],
    8: [6, 24, 42],
    9: [6, 26, 46],
    10: [6, 28, 50],
    11: [6, 30, 54],
    12: [6, 32, 58],
}

REMAINDER_BITS = {1: 0, 2: 7, 3: 7, 4: 7, 5: 7, 6: 7, 7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0}

ECC_FORMAT_BITS = {"L": 0b01, "M": 0b00, "Q": 0b11, "H": 0b10}

FORMAT_XOR_MASK = 0x5412
FORMAT_BCH_GEN = 0x537
VERSION_BCH_GEN = 0x1F25

MODULE_SCALE = 8
QUIET_MODULES = 4

INF = 1 << 60


def data_capacity_bits(version: int, ecc: str) -> int:
    _, g1b, g1d, g2b, g2d = ECC_BLOCKS[version][ecc]
    return (g1b * g1d + g2b * g2d) * 8


# ---------------------------------------------------------------------------
# Segmentation DP (contract in /app/docs/segmentation-dp.md)
# ---------------------------------------------------------------------------

GROUP_SIZE = (3, 2, 1)
FIRST_CHAR_BITS = (4, 6, 8)
# incremental data bits when segment char count goes r -> r+1 (mod group)
INC_BITS = ((4, 3, 3), (6, 5, 0), (8, 0, 0))


def char_modes(ch: str) -> list[int]:
    """Modes able to encode ch, in canonical order numeric < alphanumeric < byte."""
    out = []
    if ch.isdigit() and ch.isascii():
        out.append(MODE_NUMERIC)
    if ch in ALNUM_INDEX:
        out.append(MODE_ALNUM)
    if 0 <= ord(ch) <= 255:
        out.append(MODE_BYTE)
    return out


def header_bits(mode: int, cls: int) -> int:
    return 4 + CCI_WIDTH[mode][cls]


def segment_dp(text: str, cls: int) -> tuple[int, int, list[tuple[int, int]]] | None:
    """Optimal segmentation for CCI class cls.

    Returns (total_bits, segment_count, [(mode, char_count), ...]) or None when
    a character cannot be represented (never happens for byte-capable input).
    State: dp[mode][r] where r = chars in the open segment modulo group(mode).
    Comparison key is (bits, segment_count); strict improvement only; modes are
    iterated in canonical order so ties resolve to the earlier mode.
    """
    n = len(text)
    if n == 0:
        return None
    dp = [[None] * 3 for _ in range(3)]  # dp[m][r] = (bits, nsegs, parent)
    first = char_modes(text[0])
    if not first:
        return None
    for m in first:
        r = 1 % GROUP_SIZE[m]
        cand = (header_bits(m, cls) + FIRST_CHAR_BITS[m], 1, None)
        cur = dp[m][r]
        if cur is None or (cand[0], cand[1]) < (cur[0], cur[1]):
            dp[m][r] = cand
    history = [dp]
    for i in range(1, n):
        modes = char_modes(text[i])
        if not modes:
            return None
        ndp = [[None] * 3 for _ in range(3)]
        for pm in range(3):
            for pr in range(3):
                st = dp[pm][pr]
                if st is None:
                    continue
                bits, nsegs, _ = st
                for m in modes:
                    if m == pm:
                        nb = bits + INC_BITS[m][pr]
                        nr = (pr + 1) % GROUP_SIZE[m]
                        nseg = nsegs
                    else:
                        nb = bits + header_bits(m, cls) + FIRST_CHAR_BITS[m]
                        nr = 1 % GROUP_SIZE[m]
                        nseg = nsegs + 1
                    cand = (nb, nseg, (pm, pr))
                    cur = ndp[m][nr]
                    if cur is None or (cand[0], cand[1]) < (cur[0], cur[1]):
                        ndp[m][nr] = cand
        dp = ndp
        history.append(dp)
    best = None
    best_mr = None
    for m in range(3):
        for r in range(3):
            st = dp[m][r]
            if st is None:
                continue
            if best is None or (st[0], st[1]) < (best[0], best[1]):
                best = st
                best_mr = (m, r)
    assert best is not None and best_mr is not None
    # Reconstruct mode per character, then run-length into segments.
    modes_rev = []
    m, r = best_mr
    for i in range(n - 1, -1, -1):
        modes_rev.append(m)
        parent = history[i][m][r][2]
        if parent is None:
            break
        m, r = parent
    per_char = list(reversed(modes_rev))
    assert len(per_char) == n
    segments: list[tuple[int, int]] = []
    for mode in per_char:
        if segments and segments[-1][0] == mode:
            segments[-1] = (mode, segments[-1][1] + 1)
        else:
            segments.append((mode, 1))
    return best[0], best[1], segments


def segment_data_bits(mode: int, count: int) -> int:
    if mode == MODE_NUMERIC:
        return 10 * (count // 3) + (0, 4, 7)[count % 3]
    if mode == MODE_ALNUM:
        return 11 * (count // 2) + (0, 6)[count % 2]
    return 8 * count


def plan_symbol(text: str, ecc: str) -> dict:
    """Version fixpoint: run the DP per CCI class, pick the lowest version overall."""
    best = None
    for cls, (lo, hi) in ((0, (1, 9)), (1, (10, MAX_VERSION))):
        res = segment_dp(text, cls)
        if res is None:
            continue
        bits, nsegs, segments = res
        for v in range(lo, hi + 1):
            if data_capacity_bits(v, ecc) >= bits:
                if best is None or v < best["version"]:
                    best = {
                        "version": v,
                        "cci_class": cls,
                        "total_bits": bits,
                        "segment_count": nsegs,
                        "segments": [
                            {
                                "mode": MODE_NAMES[m],
                                "char_count": c,
                                "bit_count": header_bits(m, cls) + segment_data_bits(m, c),
                            }
                            for m, c in segments
                        ],
                    }
                break
    if best is None:
        raise ValueError("payload exceeds version 12 capacity")
    return best


# ---------------------------------------------------------------------------
# Bitstream assembly
# ---------------------------------------------------------------------------


class BitBuffer:
    def __init__(self) -> None:
        self.bits: list[int] = []

    def append(self, value: int, width: int) -> None:
        for shift in range(width - 1, -1, -1):
            self.bits.append((value >> shift) & 1)

    def __len__(self) -> int:
        return len(self.bits)

    def to_bytes(self) -> bytes:
        assert len(self.bits) % 8 == 0
        out = bytearray()
        for i in range(0, len(self.bits), 8):
            b = 0
            for bit in self.bits[i : i + 8]:
                b = (b << 1) | bit
            out.append(b)
        return bytes(out)


def encode_segments(text: str, plan: dict) -> BitBuffer:
    buf = BitBuffer()
    cls = plan["cci_class"]
    pos = 0
    for seg in plan["segments"]:
        mode = MODE_NAMES.index(seg["mode"])
        count = seg["char_count"]
        chunk = text[pos : pos + count]
        pos += count
        buf.append(MODE_INDICATOR[mode], 4)
        buf.append(count, CCI_WIDTH[mode][cls])
        if mode == MODE_NUMERIC:
            for i in range(0, count, 3):
                grp = chunk[i : i + 3]
                buf.append(int(grp), (4, 7, 10)[len(grp) - 1])
        elif mode == MODE_ALNUM:
            for i in range(0, count, 2):
                grp = chunk[i : i + 2]
                if len(grp) == 2:
                    buf.append(ALNUM_INDEX[grp[0]] * 45 + ALNUM_INDEX[grp[1]], 11)
                else:
                    buf.append(ALNUM_INDEX[grp[0]], 6)
        else:
            for ch in chunk:
                buf.append(ord(ch), 8)
    assert pos == len(text)
    assert len(buf) == plan["total_bits"]
    return buf


def finalize_data_codewords(buf: BitBuffer, version: int, ecc: str) -> bytes:
    cap = data_capacity_bits(version, ecc)
    assert len(buf) <= cap
    buf.append(0, min(4, cap - len(buf)))
    if len(buf) % 8:
        buf.append(0, 8 - len(buf) % 8)
    pads = (0xEC, 0x11)
    i = 0
    while len(buf) < cap:
        buf.append(pads[i % 2], 8)
        i += 1
    return buf.to_bytes()


# ---------------------------------------------------------------------------
# GF(256) Reed-Solomon (primitive polynomial 0x11D)
# ---------------------------------------------------------------------------

GF_EXP = [0] * 512
GF_LOG = [0] * 256
_x = 1
for _i in range(255):
    GF_EXP[_i] = _x
    GF_LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    GF_EXP[_i] = GF_EXP[_i - 255]


def gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return GF_EXP[GF_LOG[a] + GF_LOG[b]]


def rs_generator(degree: int) -> list[int]:
    gen = [1]
    for k in range(degree):
        nxt = [0] * (len(gen) + 1)
        for i, c in enumerate(gen):
            nxt[i] ^= gf_mul(c, GF_EXP[k])
            nxt[i + 1] ^= c
        gen = nxt
    # gen is little-endian by construction above; normalise to MSB-first.
    gen.reverse()
    assert gen[0] == 1
    return gen


def rs_remainder(data: bytes, degree: int) -> bytes:
    gen = rs_generator(degree)
    rem = [0] * degree
    for byte in data:
        factor = byte ^ rem[0]
        rem = rem[1:] + [0]
        if factor:
            for i in range(degree):
                rem[i] ^= gf_mul(gen[i + 1], factor)
    return bytes(rem)


def rs_syndromes(codeword: bytes, degree: int) -> list[int]:
    """Syndromes S_k = C(alpha^k) for k in 0..degree-1; all zero iff valid."""
    out = []
    for k in range(degree):
        acc = 0
        for byte in codeword:
            acc = gf_mul(acc, GF_EXP[k]) ^ byte
        out.append(acc)
    return out


def split_blocks(data: bytes, version: int, ecc: str) -> list[dict]:
    ec, g1b, g1d, g2b, g2d = ECC_BLOCKS[version][ecc]
    blocks = []
    pos = 0
    for b in range(g1b):
        chunk = data[pos : pos + g1d]
        pos += g1d
        blocks.append({"group": 1, "index": b, "data": chunk, "ecc": rs_remainder(chunk, ec)})
    for b in range(g2b):
        chunk = data[pos : pos + g2d]
        pos += g2d
        blocks.append({"group": 2, "index": g1b + b, "data": chunk, "ecc": rs_remainder(chunk, ec)})
    assert pos == len(data)
    return blocks


def interleave_blocks(blocks: list[dict]) -> bytes:
    out = bytearray()
    max_d = max(len(b["data"]) for b in blocks)
    for i in range(max_d):
        for b in blocks:
            if i < len(b["data"]):
                out.append(b["data"][i])
    ec_len = len(blocks[0]["ecc"])
    for i in range(ec_len):
        for b in blocks:
            out.append(b["ecc"][i])
    return bytes(out)


# ---------------------------------------------------------------------------
# Matrix construction
# ---------------------------------------------------------------------------


def symbol_size(version: int) -> int:
    return 17 + 4 * version


def build_function_grid(version: int) -> tuple[list[list[int]], list[list[bool]]]:
    """Function patterns with format/version areas reserved.

    Returns (modules, is_function). modules holds 0/1; reserved format and
    version areas start as 0 and are overwritten per mask later.
    """
    size = symbol_size(version)
    grid = [[0] * size for _ in range(size)]
    func = [[False] * size for _ in range(size)]

    def set_mod(r: int, c: int, v: int) -> None:
        grid[r][c] = v
        func[r][c] = True

    def finder(r0: int, c0: int) -> None:
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                r, c = r0 + dr, c0 + dc
                if 0 <= r < size and 0 <= c < size:
                    dist = max(abs(dr - 3), abs(dc - 3))
                    set_mod(r, c, 1 if dist != 2 and dist != 4 else 0)

    finder(0, 0)
    finder(0, size - 7)
    finder(size - 7, 0)

    for i in range(8, size - 8):
        v = 1 if i % 2 == 0 else 0
        set_mod(6, i, v)
        set_mod(i, 6, v)

    centers = ALIGNMENT_CENTERS[version]
    for cy in centers:
        for cx in centers:
            if (cy <= 8 and cx <= 8) or (cy <= 8 and cx >= size - 9) or (cy >= size - 9 and cx <= 8):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    set_mod(cy + dr, cx + dc, 1 if max(abs(dr), abs(dc)) != 1 else 0)

    # Reserve format areas (values placed per mask later).
    for i in range(9):
        if not func[8][i]:
            set_mod(8, i, 0)
        if not func[i][8]:
            set_mod(i, 8, 0)
    for i in range(8):
        if not func[8][size - 1 - i]:
            set_mod(8, size - 1 - i, 0)
        if not func[size - 1 - i][8]:
            set_mod(size - 1 - i, 8, 0)
    set_mod(size - 8, 8, 1)  # dark module

    if version >= 7:
        vinfo = version_info_bits(version)
        for i in range(18):
            bit = (vinfo >> i) & 1
            a = size - 11 + i % 3
            b = i // 3
            set_mod(b, a, bit)
            set_mod(a, b, bit)

    return grid, func


def version_info_bits(version: int) -> int:
    rem = version
    for _ in range(12):
        rem = (rem << 1) ^ ((rem >> 11) * VERSION_BCH_GEN)
    return (version << 12) | rem


def format_info_bits(ecc: str, mask: int) -> int:
    data = (ECC_FORMAT_BITS[ecc] << 3) | mask
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * FORMAT_BCH_GEN)
    return ((data << 10) | rem) ^ FORMAT_XOR_MASK


def place_data(grid: list[list[int]], func: list[list[bool]], stream: bytes, version: int) -> None:
    size = len(grid)
    total_bits = len(stream) * 8 + REMAINDER_BITS[version]
    bit_index = 0
    right = size - 1
    while right >= 1:
        if right == 6:
            right = 5
        for vert in range(size):
            for j in range(2):
                c = right - j
                upward = ((right + 1) & 2) == 0
                r = size - 1 - vert if upward else vert
                if not func[r][c] and bit_index < total_bits:
                    if bit_index < len(stream) * 8:
                        bit = (stream[bit_index >> 3] >> (7 - (bit_index & 7))) & 1
                    else:
                        bit = 0
                    grid[r][c] = bit
                    bit_index += 1
        right -= 2
    assert bit_index == total_bits


def mask_condition(mask: int, r: int, c: int) -> bool:
    if mask == 0:
        return (r + c) % 2 == 0
    if mask == 1:
        return r % 2 == 0
    if mask == 2:
        return c % 3 == 0
    if mask == 3:
        return (r + c) % 3 == 0
    if mask == 4:
        return (r // 2 + c // 3) % 2 == 0
    if mask == 5:
        return (r * c) % 2 + (r * c) % 3 == 0
    if mask == 6:
        return ((r * c) % 2 + (r * c) % 3) % 2 == 0
    return ((r + c) % 2 + (r * c) % 3) % 2 == 0


def apply_mask_and_format(base: list[list[int]], func: list[list[bool]], mask: int, ecc: str) -> list[list[int]]:
    size = len(base)
    grid = [row[:] for row in base]
    for r in range(size):
        for c in range(size):
            if not func[r][c] and mask_condition(mask, r, c):
                grid[r][c] ^= 1
    bits = format_info_bits(ecc, mask)

    def fbit(i: int) -> int:
        return (bits >> i) & 1

    for i in range(6):
        grid[i][8] = fbit(i)
    grid[7][8] = fbit(6)
    grid[8][8] = fbit(7)
    grid[8][7] = fbit(8)
    for i in range(9, 15):
        grid[8][14 - i] = fbit(i)
    for i in range(8):
        grid[8][size - 1 - i] = fbit(i)
    for i in range(8, 15):
        grid[size - 15 + i][8] = fbit(i)
    grid[size - 8][8] = 1
    return grid


# ---------------------------------------------------------------------------
# Penalty tournament (contract in /app/docs/mask-tournament.md)
# ---------------------------------------------------------------------------


def penalty_runs(grid: list[list[int]]) -> int:
    size = len(grid)
    total = 0
    for lines in (grid, list(map(list, zip(*grid)))):
        for line in lines:
            run = 1
            for i in range(1, size):
                if line[i] == line[i - 1]:
                    run += 1
                else:
                    if run >= 5:
                        total += 3 + (run - 5)
                    run = 1
            if run >= 5:
                total += 3 + (run - 5)
    return total


def penalty_blocks(grid: list[list[int]]) -> int:
    size = len(grid)
    total = 0
    for r in range(size - 1):
        for c in range(size - 1):
            v = grid[r][c]
            if grid[r][c + 1] == v and grid[r + 1][c] == v and grid[r + 1][c + 1] == v:
                total += 3
    return total


_FINDER_A = (1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0)
_FINDER_B = (0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1)


def penalty_finder(grid: list[list[int]]) -> int:
    size = len(grid)
    total = 0
    for lines in (grid, list(map(list, zip(*grid)))):
        for line in lines:
            for i in range(size - 10):
                window = tuple(line[i : i + 11])
                if window == _FINDER_A or window == _FINDER_B:
                    total += 40
    return total


def penalty_balance(grid: list[list[int]]) -> int:
    size = len(grid)
    dark = sum(sum(row) for row in grid)
    total = size * size
    k = abs(20 * dark - 10 * total) // total
    return 10 * k


def mask_tournament(base: list[list[int]], func: list[list[bool]], ecc: str) -> tuple[int, list[dict]]:
    rows = []
    best_mask = -1
    best_total = None
    for mask in range(8):
        grid = apply_mask_and_format(base, func, mask, ecc)
        p1 = penalty_runs(grid)
        p2 = penalty_blocks(grid)
        p3 = penalty_finder(grid)
        p4 = penalty_balance(grid)
        total = p1 + p2 + p3 + p4
        rows.append(
            {
                "mask_id": mask,
                "penalty_runs": p1,
                "penalty_blocks": p2,
                "penalty_finder": p3,
                "penalty_balance": p4,
                "penalty_total": total,
            }
        )
        if best_total is None or total < best_total:
            best_total = total
            best_mask = mask
    return best_mask, rows


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def matrix_sha256(grid: list[list[int]]) -> str:
    payload = "".join("".join("1" if v else "0" for v in row) for row in grid)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode_symbol(text: str, ecc: str) -> dict:
    plan = plan_symbol(text, ecc)
    version = plan["version"]
    buf = encode_segments(text, plan)
    data = finalize_data_codewords(buf, version, ecc)
    blocks = split_blocks(data, version, ecc)
    stream = interleave_blocks(blocks)
    base, func = build_function_grid(version)
    place_data(base, func, stream, version)
    mask, penalty_rows = mask_tournament(base, func, ecc)
    final = apply_mask_and_format(base, func, mask, ecc)
    ec, g1b, g1d, g2b, g2d = ECC_BLOCKS[version][ecc]
    return {
        "plan": plan,
        "version": version,
        "size": symbol_size(version),
        "ecc_level": ecc,
        "data_codewords": data,
        "blocks": blocks,
        "block_structure": {
            "ec_per_block": ec,
            "group1_blocks": g1b,
            "group1_data_codewords": g1d,
            "group2_blocks": g2b,
            "group2_data_codewords": g2d,
        },
        "interleaved": stream,
        "interleaved_sha256": sha256_hex(stream),
        "mask": mask,
        "penalty_rows": penalty_rows,
        "matrix": final,
        "matrix_sha256": matrix_sha256(final),
    }


def render_pgm(grid: list[list[int]]) -> bytes:
    size = len(grid)
    dim = (size + 2 * QUIET_MODULES) * MODULE_SCALE
    lines = [f"P2 {dim} {dim} 255"]
    for py in range(dim):
        row_vals = []
        my = py // MODULE_SCALE - QUIET_MODULES
        for px in range(dim):
            mx = px // MODULE_SCALE - QUIET_MODULES
            dark = 0 <= my < size and 0 <= mx < size and grid[my][mx] == 1
            row_vals.append("0" if dark else "255")
        lines.append(" ".join(row_vals))
    return ("\n".join(lines) + "\n").encode("ascii")


# ---------------------------------------------------------------------------
# Batch fixture helpers
# ---------------------------------------------------------------------------


def load_batches(inbox: Path) -> list[dict]:
    batches = []
    for path in sorted(inbox.glob("*.shipbatch.json")):
        with open(path, "r", encoding="ascii") as fh:
            batches.append(json.load(fh))
    return batches


def reference_payloads(inbox: Path) -> list[dict]:
    out = []
    for batch in load_batches(inbox):
        for payload in batch["payloads"]:
            out.append(
                {
                    "batch_id": batch["batch_id"],
                    "payload_id": payload["payload_id"],
                    "ecc_level": payload["ecc_level"],
                    "text": payload["text"],
                }
            )
    out.sort(key=lambda p: (p["batch_id"], p["payload_id"]))
    return out


def reference_symbols(inbox: Path) -> dict[tuple[str, str], dict]:
    return {
        (p["batch_id"], p["payload_id"]): encode_symbol(p["text"], p["ecc_level"])
        for p in reference_payloads(inbox)
    }
