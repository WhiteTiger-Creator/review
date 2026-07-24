import json
import os
import random
import sys
from pathlib import Path

import reference as R

ROOTV = "v1.0.0"  # root edge label; the main module's edges are always active


def vt(t):
    return f"v{t[0]}.{t[1]}.{t[2]}"


def key(v):
    return R.vkey(v)


def all_mods(sc):
    s = {sc["root"]}
    for u, _uv, dep, _dv in sc["edges"]:
        s.add(u)
        s.add(dep)
    for u, _uv, dep, _mv in sc["caps"]:
        s.add(u)
        s.add(dep)
    s |= set(sc["lock"])
    s |= set(sc["queries"])
    return s


def build_index(sc, sess):
    sel, build, _conflict = R.resolve(sc, sess)
    for m in sorted(all_mods(sc)):
        vs = set()
        for _u, _uv, dep, dv in sc["edges"]:
            if dep == m:
                vs.add(dv)
        for _u, _uv, dep, mv in sc["caps"]:
            if dep == m:
                vs.add(mv)
        if m in sc["lock"]:
            vs.add(sc["lock"][m])
        if m in build:
            vs.add(sel[m])
        if not vs:
            vs.add("v1.0.0")
        top = R.vmax(sorted(vs, key=key))
        a, _b, _c = key(top)
        vs.add(vt((a + 1, 0, 0)))  # a higher dangling release, ignored
        sc["index"][m] = sorted(vs, key=key)


def mk(sid, root, edges, lock, queries, caps=None, reset_before=False):
    return {
        "sid": sid,
        "root": root,
        "edges": list(edges),
        "caps": list(caps or []),
        "index": {},
        "lock": dict(lock),
        "queries": list(queries),
        "reset_before": reset_before,
    }


def finalize_session(session):
    """Compute registry indices for every scenario using its live session floor."""
    sess = {}
    for sc in session:
        if sc.get("reset_before"):
            sess = {}
        build_index(sc, sess)
        sel, build, conflict = R.resolve(sc, sess)
        for m in build:
            if m in conflict:
                continue
            if m not in sess or R.vkey(sel[m]) > R.vkey(sess[m]):
                sess[m] = sel[m]


def to_text(sc):
    lines = []
    if sc.get("reset_before"):
        lines.append("RESET")
    lines += ["SCENARIO " + sc["sid"], "ROOT " + sc["root"]]
    for u, uv, dep, dv in sc["edges"]:
        lines.append(f"REQ {u} {uv} {dep} {dv}")
    for u, uv, dep, mv in sc["caps"]:
        lines.append(f"CAP {u} {uv} {dep} {mv}")
    for m in sorted(sc["index"]):
        lines.append(f"INDEX {m} {' '.join(sc['index'][m])}")
    for m in sorted(sc["lock"]):
        lines.append(f"LOCK {m} {sc['lock'][m]}")
    for q in sc["queries"]:
        lines.append("QUERY " + q)
    lines.append("ENDSCENARIO")
    return "\n".join(lines)


# ---- curated public sessions ----------------------------------------------
# Every naive kernel is visibly wrong on public lines: ignoring the session
# carry, textbook flatten, dropping the lock floor, ignoring the CAP ceilings,
# and marking conflicts without retracting their dependents.


def public_sessions():
    sessions = []

    # Session A: the session floor lifts a module and then activates its own
    # version-gated edge. Reading each scenario independently is wrong.
    a = [
        mk("pub01", "m0", [("m0", ROOTV, "a", "v1.4.0")], {}, ["a"], reset_before=True),
        mk("pub02", "m0", [("m0", ROOTV, "a", "v1.1.0")], {}, ["a"]),
        mk(
            "pub03",
            "m0",
            [("m0", ROOTV, "a", "v1.0.0"), ("a", "v1.4.0", "b", "v3.0.0")],
            {},
            ["a", "b"],
        ),
    ]
    sessions.append(a)

    # Session B: version-gated dormancy and lock floors (session starts fresh).
    b = [
        mk(
            "pub04",
            "m0",
            [("m0", ROOTV, "u", "v1.0.0"), ("u", "v2.0.0", "w", "v6.0.0")],
            {},
            ["u", "w"],
            reset_before=True,
        ),
        mk(
            "pub05",
            "m0",
            [
                ("m0", ROOTV, "u", "v1.0.0"),
                ("m0", ROOTV, "w", "v1.1.0"),
                ("u", "v2.0.0", "w", "v4.0.0"),
            ],
            {},
            ["w"],
        ),
        mk(
            "pub06",
            "m0",
            [
                ("m0", ROOTV, "a", "v1.0.0"),
                ("m0", ROOTV, "c", "v1.0.0"),
                ("c", "v1.0.0", "a", "v2.0.0"),
                ("a", "v2.0.0", "b", "v1.5.0"),
                ("a", "v3.0.0", "d", "v7.0.0"),
            ],
            {},
            ["a", "b", "d"],
        ),
        mk("pub07", "m0", [("m0", ROOTV, "x", "v1.2.0")], {"x": "v2.5.0"}, ["x"]),
        mk("pub08", "m0", [("m0", ROOTV, "x", "v2.0.0")], {"x": "v1.0.0"}, ["x"]),
        mk(
            "pub09",
            "m0",
            [("m0", ROOTV, "a", "v1.0.0"), ("side", "v1.0.0", "z", "v9.9.9")],
            {"z": "v9.9.9"},
            ["a", "z"],
        ),
    ]
    sessions.append(b)

    # Session C: carry across a longer run plus a self/cycle scenario.
    c = [
        mk("pub10", "m0", [("m0", ROOTV, "a", "v2.0.0")], {}, ["a"], reset_before=True),
        mk(
            "pub11",
            "m0",
            [
                ("m0", ROOTV, "a", "v1.0.0"),
                ("a", "v2.0.0", "b", "v12.3.10"),
                ("b", "v12.3.10", "a", "v1.0.0"),
            ],
            {},
            ["a", "b"],
        ),
    ]
    sessions.append(c)

    # Session D: ceilings, over-constraint, and retraction.
    # pub12: a demanded v5 but capped at v3 -> over-constrained (CONFLICT).
    # pub13: a is capped out, so a@v2's edge is retracted and c drops to NONE;
    #        a no-retract reading wrongly keeps c at v9.
    # pub14: a gated ceiling only fires once its declarer reaches v2; then y is
    #        demanded v3 but capped at v1 -> CONFLICT, while x stays v2.
    # pub15: a slack ceiling above the demand does not bite; a stays v2.
    d = [
        mk(
            "pub12",
            "m0",
            [("m0", ROOTV, "a", "v5.0.0")],
            {},
            ["a"],
            caps=[("m0", ROOTV, "a", "v3.0.0")],
            reset_before=True,
        ),
        mk(
            "pub13",
            "m0",
            [("m0", ROOTV, "a", "v2.0.0"), ("a", "v2.0.0", "c", "v9.0.0")],
            {},
            ["a", "c"],
            caps=[("m0", ROOTV, "a", "v1.0.0")],
        ),
        mk(
            "pub14",
            "m0",
            [("m0", ROOTV, "x", "v2.0.0"), ("m0", ROOTV, "y", "v3.0.0")],
            {},
            ["x", "y"],
            caps=[("x", "v2.0.0", "y", "v1.0.0")],
        ),
        mk(
            "pub15",
            "m0",
            [("m0", ROOTV, "a", "v2.0.0")],
            {},
            ["a"],
            caps=[("m0", ROOTV, "a", "v5.0.0")],
        ),
    ]
    sessions.append(d)

    return sessions


# ---- randomized hidden gadgets ---------------------------------------------


def g_plain(rng, sid):
    v = vt((rng.randint(1, 3), rng.randint(0, 12), rng.randint(0, 9)))
    return mk(sid, "m0", [("m0", ROOTV, "a", v)], {}, ["a"])


def g_bulk(rng, sid):
    n = rng.randint(2, 4)
    mods = [f"b{i}" for i in range(1, n + 1)]
    edges = []
    for i, mi in enumerate(mods):
        parent = "m0" if i == 0 else f"b{rng.randint(1, i)}"
        edges.append(
            (parent, "v0.0.0", mi, vt((rng.randint(1, 3), rng.randint(0, 9), 0)))
        )
        if i >= 1 and rng.random() < 0.5:
            edges.append(
                ("m0", "v0.0.0", mi, vt((rng.randint(1, 3), rng.randint(0, 9), 0)))
            )
    q = list(mods)
    rng.shuffle(q)
    return mk(sid, "m0", edges, {}, q[: rng.randint(1, len(q))])


def g_dormant(rng, sid):
    lo = (1, rng.randint(0, 4), 0)
    hi = (lo[0] + 1, 0, 0)
    big = (rng.randint(5, 9), rng.randint(0, 9), 0)
    edges = [("m0", ROOTV, "u", vt(lo)), ("u", vt(hi), "w", vt(big))]
    q = ["w", "u"]
    if rng.random() < 0.5:
        small = (1, rng.randint(0, 3), 0)
        edges.insert(1, ("m0", ROOTV, "w", vt(small)))
    rng.shuffle(q)
    return mk(sid, "m0", edges, {}, q)


def g_cascade(rng, sid):
    a2 = (2, rng.randint(0, 4), 0)
    b = (1, rng.randint(0, 9), 0)
    d = (rng.randint(6, 9), 0, 0)
    edges = [
        ("m0", ROOTV, "a", "v1.0.0"),
        ("m0", ROOTV, "c", "v1.0.0"),
        ("c", "v1.0.0", "a", vt(a2)),
        ("a", vt(a2), "b", vt(b)),
        ("a", "v5.0.0", "d", vt(d)),  # dormant: a never reaches 5.0.0
    ]
    q = ["b", "d", "a"]
    rng.shuffle(q)
    return mk(sid, "m0", edges, {}, q)


def g_lock_raise(rng, sid):
    p = (1, rng.randint(0, 4), 0)
    q_ = (2, rng.randint(0, 8), 0)
    edges = [("m0", ROOTV, "x", vt(p))]
    qs = ["x"]
    if rng.random() < 0.6:
        edges.append(("x", "v2.0.0", "y", vt((3, rng.randint(0, 5), 0))))
        qs.append("y")
    return mk(sid, "m0", edges, {"x": vt(q_)}, qs)


def g_lock_below(rng, sid):
    p = (2, rng.randint(0, 6), 0)
    q_ = (1, rng.randint(0, 5), 0)
    return mk(sid, "m0", [("m0", ROOTV, "x", vt(p))], {"x": vt(q_)}, ["x"])


def g_cap_conflict(rng, sid):
    """A module demanded high but capped low: over-constrained (CONFLICT)."""
    hi = (rng.randint(4, 8), rng.randint(0, 9), 0)
    cap = (rng.randint(1, 3), rng.randint(0, 5), 0)
    return mk(
        sid,
        "m0",
        [("m0", ROOTV, "a", vt(hi))],
        {},
        ["a"],
        caps=[("m0", ROOTV, "a", vt(cap))],
    )


def g_cap_retract(rng, sid):
    """A capped-out module retracts its own edge, dropping a dependent to NONE."""
    dem = (2, rng.randint(0, 5), 0)
    big = (rng.randint(6, 9), rng.randint(0, 9), 0)
    edges = [("m0", ROOTV, "a", vt(dem)), ("a", vt(dem), "c", vt(big))]
    caps = [("m0", ROOTV, "a", "v1.0.0")]
    q = ["a", "c"]
    rng.shuffle(q)
    return mk(sid, "m0", edges, {}, q, caps=caps)


def g_cap_gated(rng, sid):
    """A ceiling gated on its declarer; it bites y only once x reaches v2."""
    ydem = (rng.randint(3, 6), rng.randint(0, 9), 0)
    edges = [("m0", ROOTV, "x", "v2.0.0"), ("m0", ROOTV, "y", vt(ydem))]
    caps = [("x", "v2.0.0", "y", "v1.0.0")]
    q = ["x", "y"]
    rng.shuffle(q)
    return mk(sid, "m0", edges, {}, q, caps=caps)


def g_cap_slack(rng, sid):
    """A ceiling above the demand that does not bite; the pick is unchanged."""
    dem = (2, rng.randint(0, 6), 0)
    hi = (rng.randint(6, 9), 0, 0)
    return mk(
        sid,
        "m0",
        [("m0", ROOTV, "a", vt(dem))],
        {},
        ["a"],
        caps=[("m0", ROOTV, "a", vt(hi))],
    )


GADGETS = [
    (g_plain, 2),
    (g_bulk, 2),
    (g_dormant, 2),
    (g_cascade, 2),
    (g_lock_raise, 2),
    (g_lock_below, 1),
    (g_cap_conflict, 3),
    (g_cap_retract, 3),
    (g_cap_gated, 3),
    (g_cap_slack, 2),
]


def pick_gadget(rng):
    total = sum(w for _g, w in GADGETS)
    r = rng.randint(1, total)
    acc = 0
    for g, w in GADGETS:
        acc += w
        if r <= acc:
            return g
    return GADGETS[0][0]


def _remap_caps(sc, remap, cm):
    out = []
    for u, uv, dep, mv in sc["caps"]:
        ru, rdep = remap.get(u, u), remap.get(dep, dep)
        if ru == cm or rdep == cm:
            continue  # protect the shared carry module from ceilings
        out.append((ru, uv, rdep, mv))
    return out


def hidden_session(rng, base, length):
    """Build one session of `length` scenarios that interact through carry.

    A shared "carry module" is seeded high in the opening scenario, then later
    scenarios reference it with a lower local requirement and query it, so the
    only correct answer is the version carried forward. Gadget bodies are
    remapped onto a small shared namespace so other modules carry too, and cap
    gadgets add over-constraint and retraction.
    """
    pool = ["a", "b", "c", "u", "w"]
    rng.shuffle(pool)
    cm = pool[0]
    hi = (rng.randint(3, 6), rng.randint(0, 9), 0)
    session = []
    for j in range(length):
        g = pick_gadget(rng)
        sc = g(rng, f"hid{base + j:03d}")
        names = sorted({m for m in all_mods(sc) if m != "m0"})
        others = [p for p in pool if p != cm]
        remap = {n: others[i % len(others)] for i, n in enumerate(names)}
        remap["m0"] = "m0"
        sc["edges"] = [
            (remap.get(u, u), uv, remap.get(dep, dep), dv)
            for u, uv, dep, dv in sc["edges"]
        ]
        sc["caps"] = _remap_caps(sc, remap, cm)
        sc["lock"] = {
            remap.get(m, m): v for m, v in sc["lock"].items() if remap.get(m, m) != cm
        }
        sc["queries"] = [
            remap.get(q, q) for q in sc["queries"] if remap.get(q, q) != cm
        ]
        if j == 0:
            sc["edges"].append(("m0", ROOTV, cm, vt(hi)))
            if cm not in sc["queries"]:
                sc["queries"].append(cm)
        elif rng.random() < 0.6:
            lo = (1, rng.randint(0, 6), 0)
            sc["edges"].append(("m0", ROOTV, cm, vt(lo)))
            sc["queries"].append(cm)
        sc["reset_before"] = j == 0
        session.append(sc)
    finalize_session(session)
    return session


def build():
    public = public_sessions()
    for s in public:
        finalize_session(s)

    rng = random.Random(20260724)
    hidden = []
    base = 0
    target = 640
    lines = sum(sum(len(R.qmods(sc)) for sc in s) for s in public)
    while lines < target:
        length = rng.randint(2, 4)
        s = hidden_session(rng, base, length)
        base += length
        hidden.append(s)
        lines += sum(len(R.qmods(sc)) for sc in s)
    return public, hidden


def flatten(sessions):
    return [sc for s in sessions for sc in s]


def _div(exp, kernel_lines):
    return sum(1 for a, b in zip(exp, kernel_lines, strict=True) if a != b)


def main():
    public, hidden = build()
    outdir = sys.argv[1] if len(sys.argv) > 1 else "."
    exdir = sys.argv[2] if len(sys.argv) > 2 else None

    pub = flatten(public)
    hid = flatten(hidden)
    allrows = pub + hid

    tot = sum(len(R.qmods(sc)) for sc in allrows)
    exp = R.pinned_stream(allrows)
    kernels = {
        "per-scenario": R.per_scenario_stream(allrows),
        "flat": R.flat_stream(allrows),
        "ignore-lock": R.ignore_lock_stream(allrows),
        "cap-ignore": R.cap_ignore_stream(allrows),
        "no-retract": R.no_retract_stream(allrows),
    }
    print("public scen:", len(pub), "hidden scen:", len(hid), "rows:", tot)
    for name, lines in kernels.items():
        d = _div(exp, lines)
        print(f"{name}-traps: {d} ({d / tot:.3f})")

    pexp = R.pinned_stream(pub)
    for name, fn in [
        ("per-scenario", R.per_scenario_stream),
        ("flat", R.flat_stream),
        ("ignore-lock", R.ignore_lock_stream),
        ("cap-ignore", R.cap_ignore_stream),
        ("no-retract", R.no_retract_stream),
    ]:
        print(f"public {name} diverge:", _div(pexp, fn(pub)))

    def dump(path, sessions):
        flat_scen = flatten(sessions)
        expected = R.pinned_stream(flat_scen)
        idx = 0
        with open(path, "w", encoding="utf-8") as f:
            for sc in flat_scen:
                n = len(R.qmods(sc))
                rec = {
                    "scenario": to_text(sc),
                    "expected": expected[idx : idx + n],
                    "reset": bool(sc.get("reset_before")),
                }
                f.write(json.dumps(rec) + "\n")
                idx += n

    dump(os.path.join(outdir, "public.jsonl"), public)
    dump(os.path.join(outdir, "hidden.jsonl"), hidden)
    print("wrote battery to", outdir)

    if exdir:
        for i, s in enumerate(public):
            text = "\n".join(to_text(sc) for sc in s)
            outs = R.pinned_stream(s)
            Path(exdir, f"ex{i + 1:02d}.in").write_text(text + "\n", encoding="utf-8")
            Path(exdir, f"ex{i + 1:02d}.out").write_text(
                "\n".join(outs) + "\n", encoding="utf-8"
            )
        print(f"wrote {len(public)} example sessions to {exdir}")


if __name__ == "__main__":
    main()
