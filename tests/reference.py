import json
import os

TOKEN_NONE = "NONE"
TOKEN_INCOMP = "INCOMPARABLE"


def parse_version(s):
    if "-" in s:
        core_s, pre_s = s.split("-", 1)
        pre = pre_s.split(".")
    else:
        core_s, pre = s, []
    a, b, c = core_s.split(".")
    return {"core": (int(a), int(b), int(c)), "pre": pre, "raw": s}


def _is_num(x):
    return len(x) > 0 and x.isdigit()


def _cmp_ident(a, b):
    an, bn = _is_num(a), _is_num(b)
    if an and bn:
        ia, ib = int(a), int(b)
        return (ia > ib) - (ia < ib)
    if an and not bn:
        return -1
    if bn and not an:
        return 1
    return (a > b) - (a < b)


def _shared_prefix_cmp(a, b):
    for x, y in zip(a, b):
        c = _cmp_ident(x, y)
        if c:
            return c
    return 0


def _mat_cmp(a_pre, b_pre, length_rule):
    """Install-preference (maturity) comparison of two prerelease tags.

    Returns +1 when tag ``a`` is *more mature* (nearer to final release, ranks
    higher), -1 when ``b`` is more mature, 0 when the two tags are identical.

    Identifiers on the shared prefix compare by standard prerelease rules
    (numeric by value, numeric below alphanumeric, alphanumeric in ASCII
    order). The two length rules differ only when the shared prefix is equal
    and the tags differ in length:

    * ``"shorter_higher"`` — the resolver's install preference: the shorter
      tag (fewer pending refinements) is nearer to final release, so it is the
      more mature build. This is the reverse of standard semver precedence.
    * ``"longer_higher"`` — standard semver precedence: the longer tag ranks
      higher.
    """
    c = _shared_prefix_cmp(a_pre, b_pre)
    if c:
        return c
    if len(a_pre) == len(b_pre):
        return 0
    if length_rule == "shorter_higher":
        return 1 if len(a_pre) < len(b_pre) else -1
    return 1 if len(a_pre) > len(b_pre) else -1


def parse_block(text):
    sid = ""
    events = []
    for line in text.splitlines():
        p = line.split()
        if not p:
            continue
        if p[0] == "SCENARIO":
            sid = p[1] if len(p) > 1 else ""
        elif p[0] == "REQUIRE" and len(p) >= 2:
            events.append(("REQUIRE", p[1]))
        elif p[0] == "CMP" and len(p) >= 4:
            events.append(("CMP", p[1], p[2], p[3]))
    return sid, events


def _simulate(text, length_rule, accumulate, select, honor_floor):
    """Replay one scenario's rows and emit one line per CMP query.

    * ``length_rule`` — the within-tag maturity rule (see :func:`_mat_cmp`).
    * ``honor_floor`` — whether REQUIRE floors constrain the install at all.
    * ``accumulate`` — when honouring floors, whether the per-core floor is the
      most-mature REQUIRE seen so far (True) or only the latest one (False).
    * ``select`` — among the candidates that clear the floor, install the
      ``"min"`` (least-mature, minimal-version selection) or the ``"max"``
      (most-mature) of the two.
    """
    sid, events = parse_block(text)
    floors = {}
    out = []
    for ev in events:
        if ev[0] == "REQUIRE":
            if not honor_floor:
                continue
            v = parse_version(ev[1])
            core = v["core"]
            if not accumulate:
                floors[core] = v
            else:
                cur = floors.get(core)
                if cur is None or _mat_cmp(v["pre"], cur["pre"], length_rule) > 0:
                    floors[core] = v
            continue
        _, qid, sa, sb = ev
        a = parse_version(sa)
        b = parse_version(sb)
        if a["core"] != b["core"]:
            out.append("%s|%s|%s" % (sid, qid, TOKEN_INCOMP))
            continue
        fl = floors.get(a["core"]) if honor_floor else None
        cand = []
        for x in (a, b):
            if fl is None or _mat_cmp(x["pre"], fl["pre"], length_rule) >= 0:
                cand.append(x)
        if not cand:
            res = TOKEN_NONE
        elif len(cand) == 1:
            res = cand[0]["raw"]
        else:
            m = _mat_cmp(a["pre"], b["pre"], length_rule)
            if select == "min":
                res = a["raw"] if m < 0 else (b["raw"] if m > 0 else a["raw"])
            else:
                res = a["raw"] if m > 0 else (b["raw"] if m < 0 else a["raw"])
        out.append("%s|%s|%s" % (sid, qid, res))
    return out


def pinned_lines(text):
    """Ground truth: accumulated per-core floor, minimal install above it."""
    return _simulate(text, "shorter_higher", True, "min", True)


def nearrelease_lines(text):
    """Primary trap: stateless 'install the build nearer to final release'.

    Ignores REQUIRE floors entirely and installs the more mature of the two
    candidates. This is the direct reading of the install-preference ordering
    and the answer a per-query comparator produces.
    """
    return _simulate(text, "shorter_higher", True, "max", False)


def stateless_min_lines(text):
    """Trap: install the least-mature candidate but ignore REQUIRE floors."""
    return _simulate(text, "shorter_higher", True, "min", False)


def latest_floor_lines(text):
    """Trap: honour only the most recent REQUIRE, not the accumulated floor."""
    return _simulate(text, "shorter_higher", False, "min", True)


def semver_lines(text):
    """Trap: same policy but standard semver within-tag (longer tag higher)."""
    return _simulate(text, "longer_higher", True, "min", True)


def load_battery(name):
    path = os.path.join(os.path.dirname(__file__), "battery", name)
    recs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs
