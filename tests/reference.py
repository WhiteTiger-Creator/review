import json
import os
from collections import deque

BASE = "v0.0.0"
CONFLICT = "CONFLICT"


def vkey(v):
    return tuple(int(x) for x in v[1:].split("."))


def vmax(vs):
    best = vs[0]
    for v in vs[1:]:
        if vkey(v) > vkey(best):
            best = v
    return best


def vmin(vs):
    best = vs[0]
    for v in vs[1:]:
        if vkey(v) < vkey(best):
            best = v
    return best


def parse_stream(text):
    """Parse the whole stdin into an ordered list of scenario dicts.

    A ``RESET`` line may appear between scenarios; the scenario that follows it
    carries ``reset_before = True``. All other scenarios carry ``False``.
    """
    scen = []
    cur = None
    reset_pending = False
    for line in text.splitlines():
        p = line.split()
        if not p:
            continue
        k = p[0]
        if k == "RESET":
            reset_pending = True
            continue
        if k == "SCENARIO":
            cur = {
                "sid": p[1],
                "root": None,
                "edges": [],
                "caps": [],
                "index": {},
                "lock": {},
                "queries": [],
                "reset_before": reset_pending,
            }
            reset_pending = False
        elif cur is None:
            continue
        elif k == "ROOT":
            cur["root"] = p[1]
        elif k == "REQ":
            cur["edges"].append((p[1], p[2], p[3], p[4]))
        elif k == "CAP":
            cur["caps"].append((p[1], p[2], p[3], p[4]))
        elif k == "INDEX":
            cur["index"][p[1]] = list(p[2:])
        elif k == "LOCK":
            cur["lock"][p[1]] = p[2]
        elif k == "QUERY":
            cur["queries"].append(p[1])
        elif k == "ENDSCENARIO":
            scen.append(cur)
            cur = None
    return scen


def parse_scenario(text):
    """Parse a single scenario block (session context empty)."""
    return parse_stream(text)[0]


def qmods(sc):
    return sorted(set(sc["queries"]))


def _floor(sc, sess, m):
    cands = [BASE]
    if m in sc.get("lock", {}):
        cands.append(sc["lock"][m])
    if m in sess:
        cands.append(sess[m])
    return vmax(cands)


def _expand(sc, sess, skip=None):
    """Monotone lower-bound expansion.

    Returns ``(sel, build)`` where an edge declared by version ``uver`` of ``u``
    is in force only once ``u`` is in the build list and its selected version has
    reached ``uver`` (the root's edges are always in force). Requirers named in
    ``skip`` contribute no edges (used to retract conflicted providers).
    """
    if skip is None:
        skip = set()
    root = sc["root"]
    sel = {root: _floor(sc, sess, root)}
    build = {root}
    changed = True
    while changed:
        changed = False
        for u, uver, dep, depver in sc["edges"]:
            if u not in build or u in skip:
                continue
            if u != root and vkey(uver) > vkey(sel[u]):
                continue
            if dep not in build:
                build.add(dep)
                sel[dep] = _floor(sc, sess, dep)
                changed = True
            if vkey(depver) > vkey(sel[dep]):
                sel[dep] = depver
                changed = True
    return sel, build


def _ceilings(sc, demand, build):
    """Lowest in-force ceiling per module.

    A ``CAP`` declared by version ``uver`` of ``u`` limits ``dep`` to at most
    ``maxver``; it is in force under the same gate as a requirement, evaluated
    against the maximal (cap-free) demand.
    """
    root = sc["root"]
    ceil = {}
    for u, uver, dep, maxver in sc.get("caps", []):
        if u not in build:
            continue
        if u != root and vkey(uver) > vkey(demand[u]):
            continue
        ceil[dep] = maxver if dep not in ceil else vmin([ceil[dep], maxver])
    return ceil


def resolve(sc, sess=None):
    """Full resolution with version-conditioned edges, floors, ceilings.

    Feasibility is judged against the maximal demand: a module whose demanded
    version exceeds its lowest in-force ceiling is over-constrained. Its own
    edges are then retracted, so modules reachable only through it drop out.
    Returns ``(sel, build, conflict)``; ``sel`` holds the retracted selection
    for every built, non-conflicted module.
    """
    if sess is None:
        sess = {}
    demand, dbuild = _expand(sc, sess)
    ceil = _ceilings(sc, demand, dbuild)
    conflict = {m for m in dbuild if m in ceil and vkey(demand[m]) > vkey(ceil[m])}
    sel, build = _expand(sc, sess, skip=conflict)
    live_conflict = {m for m in conflict if m in build}
    return sel, build, live_conflict


def resolve_stream(scen):
    """Resolve scenarios in stream order, carrying a monotone session floor.

    A ``reset_before`` flag clears the floor. After a scenario resolves, every
    built, non-conflicted module lifts the session floor for itself to at least
    its selected version; conflicted and unreachable modules carry nothing.
    """
    sess = {}
    out = []
    for sc in scen:
        if sc.get("reset_before"):
            sess = {}
        sel, build, conflict = resolve(sc, sess)
        out.append((sel, build, conflict))
        for m in build:
            if m in conflict:
                continue
            if m not in sess or vkey(sel[m]) > vkey(sess[m]):
                sess[m] = sel[m]
    return out


def _value(sc, sel, build, conflict, m):
    if m not in build:
        return "NONE"
    if m in conflict:
        return CONFLICT
    return sel[m]


def _lines(sc, sel, build, conflict):
    return [f"{sc['sid']}|{m}|{_value(sc, sel, build, conflict, m)}" for m in qmods(sc)]


def pinned_stream(scen):
    out = []
    for sc, (sel, build, conflict) in zip(scen, resolve_stream(scen), strict=True):
        out.extend(_lines(sc, sel, build, conflict))
    return out


def pinned_one(sc, sess=None):
    """Reference answer for one scenario in a given session context."""
    sel, build, conflict = resolve(sc, sess or {})
    return _lines(sc, sel, build, conflict)


# -- naive kernels (traps); each must fail the full battery ------------------


def per_scenario_stream(scen):
    """Trap: resolve every scenario independently, no session carry."""
    out = []
    for sc in scen:
        out.extend(pinned_one(sc, {}))
    return out


def _cap_ignore_resolve(sc, sess):
    """Correct lower-bound resolution but blind to ceilings (no conflicts)."""
    sel, build = _expand(sc, sess)
    return sel, build, set()


def cap_ignore_stream(scen):
    """Primary trap: floors, carry, and gating are correct but CAP rows are
    ignored, so no module is ever over-constrained or retracted."""
    sess = {}
    out = []
    for sc in scen:
        if sc.get("reset_before"):
            sess = {}
        sel, build, conflict = _cap_ignore_resolve(sc, sess)
        out.extend(_lines(sc, sel, build, conflict))
        for m in build:
            if m not in sess or vkey(sel[m]) > vkey(sess[m]):
                sess[m] = sel[m]
    return out


def _no_retract_resolve(sc, sess):
    """Detect conflicts but keep the maximal demand for everyone else."""
    demand, dbuild = _expand(sc, sess)
    ceil = _ceilings(sc, demand, dbuild)
    conflict = {m for m in dbuild if m in ceil and vkey(demand[m]) > vkey(ceil[m])}
    return demand, dbuild, conflict


def no_retract_stream(scen):
    """Trap: mark over-constrained modules CONFLICT but never retract their
    edges, so their dependents keep the inflated demand instead of dropping."""
    sess = {}
    out = []
    for sc in scen:
        if sc.get("reset_before"):
            sess = {}
        sel, build, conflict = _no_retract_resolve(sc, sess)
        out.extend(_lines(sc, sel, build, conflict))
        for m in build:
            if m in conflict:
                continue
            if m not in sess or vkey(sel[m]) > vkey(sess[m]):
                sess[m] = sel[m]
    return out


def _reach_flat(sc):
    adj = {}
    for u, _uv, dep, _dv in sc["edges"]:
        adj.setdefault(u, []).append(dep)
    seen = {sc["root"]}
    q = deque([sc["root"]])
    while q:
        cur = q.popleft()
        for dep in adj.get(cur, []):
            if dep not in seen:
                seen.add(dep)
                q.append(dep)
    return seen


def flat(sc):
    """Textbook MVS: every edge active, max required version, no floors, no
    ceilings, no conflicts."""
    reach = _reach_flat(sc)
    out = []
    for m in qmods(sc):
        cands = [dv for u, _uv, dep, dv in sc["edges"] if dep == m and u in reach]
        v = vmax(cands) if cands else "NONE"
        out.append(f"{sc['sid']}|{m}|{v}")
    return out


def flat_stream(scen):
    out = []
    for sc in scen:
        out.extend(flat(sc))
    return out


def ignore_lock_stream(scen):
    """Correct gating, ceilings, and carry but the explicit lock floor dropped."""
    sess = {}
    out = []
    for sc in scen:
        if sc.get("reset_before"):
            sess = {}
        stripped = dict(sc)
        stripped["lock"] = {}
        sel, build, conflict = resolve(stripped, sess)
        out.extend(_lines(sc, sel, build, conflict))
        for m in build:
            if m in conflict:
                continue
            if m not in sess or vkey(sel[m]) > vkey(sess[m]):
                sess[m] = sel[m]
    return out


def load_battery(name):
    path = os.path.join(os.path.dirname(__file__), "battery", name)
    recs = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line:
                recs.append(json.loads(line))
    return recs
