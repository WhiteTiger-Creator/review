"""Grading oracle (independent Python engine) for plane-curve-dual-class-census.

Input (one instance): line 1 is "d n" (degree 3<=d<=4, term count n>=1); the next
n lines are "i j k c" meaning coefficient c times x^i y^j z^k with i+j+k == d.
Integer tokens are strict (optional single '-', no '+', no leading zeros beyond a
lone 0, no '-0'), single-space separated, exactly one trailing newline, exactly
n+1 lines. Coeff c != 0, |c| <= 1000000. Duplicate monomials, n mismatch, wrong
degree sum, or any grammar violation is malformed.

Output for an in-domain curve, five labelled lines:
  degree = d
  class = <m>
  inflections = <iota>
  doublepoints = <nodes>
  cusps = <cusps>
Malformed input or an out-of-domain curve (not reduced, a singular point that is
not a rational node or ordinary cusp, a line component) prints ERROR.
"""

from fractions import Fraction as Fr

import census


class Malformed(Exception):
    pass


COEFBOUND = 1000000
MIN_DEGREE = 3
MAX_DEGREE = 4
MIN_TERMS = 1
MAX_TERMS = 200
_HEAD_FIELD_COUNT = 2
_TERM_FIELD_COUNT = 4


def _int_strict(tok):
    if tok in ("", "-"):
        raise Malformed()
    neg = tok[0] == "-"
    body = tok[1:] if neg else tok
    if body == "" or not body.isdigit():
        raise Malformed()
    if len(body) > 1 and body[0] == "0":
        raise Malformed()
    if neg and body == "0":
        raise Malformed()
    return -int(body) if neg else int(body)


def _parse_term_line(ln, d, F):
    """Validate and parse one monomial line, adding it to F."""
    if ln == "" or ln[0] == " " or ln[-1] == " " or "  " in ln:
        raise Malformed()
    t = ln.split(" ")
    if len(t) != _TERM_FIELD_COUNT:
        raise Malformed()
    i, j, k, c = (_int_strict(x) for x in t)
    if i < 0 or j < 0 or k < 0:
        raise Malformed()
    if i + j + k != d:
        raise Malformed()
    if c == 0 or abs(c) > COEFBOUND:
        raise Malformed()
    if (i, j, k) in F:
        raise Malformed()
    F[(i, j, k)] = Fr(c)


def parse_input(raw):
    if raw == "" or not raw.endswith("\n"):
        raise Malformed()
    parts = raw.split("\n")
    if parts[-1] != "":
        raise Malformed()
    lines = parts[:-1]
    if len(lines) < 1:
        raise Malformed()
    head = lines[0]
    if head == "" or head[0] == " " or head[-1] == " " or "  " in head:
        raise Malformed()
    ht = head.split(" ")
    if len(ht) != _HEAD_FIELD_COUNT:
        raise Malformed()
    d = _int_strict(ht[0])
    n = _int_strict(ht[1])
    if d < MIN_DEGREE or d > MAX_DEGREE:
        raise Malformed()
    if n < MIN_TERMS or n > MAX_TERMS:
        raise Malformed()
    if len(lines) != n + 1:
        raise Malformed()
    F = {}
    for r in range(1, n + 1):
        _parse_term_line(lines[r], d, F)
    return F


def solve(raw):
    try:
        F = parse_input(raw)
    except Malformed:
        return "ERROR\n"
    res = census.census(F)
    if res == "ERROR":
        return "ERROR\n"
    return (
        f"degree = {res['d']}\n"
        f"class = {res['m']}\n"
        f"inflections = {res['iota']}\n"
        f"doublepoints = {res['delta']}\n"
        f"cusps = {res['kappa']}\n"
        f"crunodes = {res['crunodes']}\n"
        f"realmeet = {res['realmeet']}\n"
    )
