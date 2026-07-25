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


def _in_force_ceilings(sc, sess, scar):
    """Lowest in-force ceiling per module, merging local caps with carried scars.

    A local ``CAP`` is gated like a requirement and judged against the maximal
    cap-free demand; a scar ceiling carried from an earlier scenario is
    unconditional. The binding ceiling is the lowest of the two.
    """
    demand, dbuild = _expand(sc, sess)
    ceil = _ceilings(sc, demand, dbuild)
    for m, c in scar.items():
        if m not in ceil or vkey(c) < vkey(ceil[m]):
            ceil[m] = c
    return demand, dbuild, ceil


def step(sc, sess, scar):
    """Resolve one scenario in a given session floor and scar context.

    Returns ``(sel, build, live, ceil)``: ``sel``/``build`` are the retracted
    selection; ``live`` are the built, over-constrained modules; ``ceil`` is the
    binding-ceiling map used to score conflict and to update scars.
    """
    demand, dbuild, ceil = _in_force_ceilings(sc, sess, scar)
    conflict = {m for m in dbuild if m in ceil and vkey(demand[m]) > vkey(ceil[m])}
    sel, build = _expand(sc, sess, skip=conflict)
    live = {m for m in conflict if m in build}
    return sel, build, live, ceil


def apply_carry(sess, scar, sel, build, live, ceil):
    """Advance both session tables after a scenario resolves.

    Built, non-conflicted modules lift the monotone session floor. Each built,
    over-constrained module deposits its binding ceiling into the scar table,
    which only ratchets lower. A conflicted module lifts no floor.
    """
    for m in build:
        if m in live:
            continue
        if m not in sess or vkey(sel[m]) > vkey(sess[m]):
            sess[m] = sel[m]
    for m in live:
        c = ceil[m]
        if m not in scar or vkey(c) < vkey(scar[m]):
            scar[m] = c


def resolve(sc, sess=None, scar=None):
    """Full resolution with version-conditioned edges, floors, ceilings, scars.

    Feasibility is judged against the maximal demand: a module whose demanded
    version exceeds its lowest in-force ceiling (a local ``CAP`` or a carried
    scar) is over-constrained. Its own edges are then retracted, so modules
    reachable only through it drop out. Returns ``(sel, build, conflict)``.
    """
    if sess is None:
        sess = {}
    if scar is None:
        scar = {}
    sel, build, live, _ceil = step(sc, sess, scar)
    return sel, build, live


def resolve_stream(scen):
    """Resolve scenarios in stream order, carrying a floor table and a scar table.

    A ``reset_before`` flag clears both tables. After a scenario resolves the
    floor table only grows (built, non-conflicted modules), while the scar table
    only ratchets lower (built, over-constrained modules record their binding
    ceiling). A module carried above a remembered ceiling re-conflicts in every
    later scenario until a ``RESET``.
    """
    sess, scar = {}, {}
    out = []
    for sc in scen:
        if sc.get("reset_before"):
            sess, scar = {}, {}
        sel, build, live, ceil = step(sc, sess, scar)
        out.append((sel, build, live))
        apply_carry(sess, scar, sel, build, live, ceil)
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


def no_cap_carry_stream(scen):
    """Primary scar trap: floors carry and local caps retract correctly, but
    conflict is treated as purely per-scenario. The binding ceiling of an
    over-constrained module is never remembered, so once its scar is cleared by
    the next scenario a module carried above that ceiling is wrongly re-selected
    at its floor (and its dependents wrongly rebuilt) wherever no live ``CAP``
    is present."""
    sess = {}
    out = []
    for sc in scen:
        if sc.get("reset_before"):
            sess = {}
        sel, build, live, ceil = step(sc, sess, {})  # empty scar every scenario
        out.extend(_lines(sc, sel, build, live))
        apply_carry(sess, {}, sel, build, live, ceil)
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
