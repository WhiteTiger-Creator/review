import functools
import json
import os

import reference as ref

HERE = os.path.dirname(__file__)
ENVDATA = os.path.normpath(os.path.join(HERE, "..", "environment", "data", "examples"))

CORES = [
    (1, 0, 0),
    (1, 4, 0),
    (2, 0, 0),
    (3, 7, 2),
    (0, 9, 0),
    (5, 1, 1),
    (2, 3, 4),
    (4, 0, 0),
]

BASES = ["alpha", "beta", "canary", "dev", "rc", "next", "gamma", "pre"]


def cv(core, tag):
    return "%d.%d.%d-%s" % (core[0], core[1], core[2], tag)


def mat(a, b):
    return ref._mat_cmp(
        ref.parse_version(a)["pre"], ref.parse_version(b)["pre"], "shorter_higher"
    )


def core_pool(core):
    """A deterministic maturity-sorted (least mature first) pool for one core."""
    tags = []
    for base in BASES:
        tags.append(base)
        for n in [1, 2, 3, 5, 9, 10, 12, 20]:
            tags.append("%s.%d" % (base, n))
        tags.append("%s.rc" % base)
        tags.append("%s.1.2" % base)
    for base in ["x", "m", "z"]:
        tags.append(base)
        for suf in ["1", "2", "9", "10", "1a", "2b", "a", "b"]:
            tags.append("%s.%s" % (base, suf))
    seen = set()
    ordered = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    vers = [cv(core, t) for t in ordered]
    vers.sort(key=functools.cmp_to_key(mat))
    return vers


def render(sid, events):
    lines = ["SCENARIO " + sid]
    for ev in events:
        if ev[0] == "REQUIRE":
            lines.append("REQUIRE %s" % ev[1])
        else:
            lines.append("CMP %s %s %s" % (ev[1], ev[2], ev[3]))
    lines.append("ENDSCENARIO")
    return "\n".join(lines)


def gen_core(core):
    """Return a list of (events) scenarios covering every trap family."""
    P = core_pool(core)
    n = len(P)
    lo, ml, mm, hi = n // 6, n // 3, n // 2, (5 * n) // 6
    scen = []

    # A -- no floor: install the least-mature (minimal) build. The stateless
    # "install nearer to final release" reader picks the most mature instead.
    scen.append(
        [
            ("CMP", "q0", P[lo], P[hi]),
            ("CMP", "q1", P[ml], P[hi]),
            ("CMP", "q2", P[lo], P[mm]),
            ("CMP", "q3", P[ml + 1], P[mm + 3]),
            ("CMP", "q4", P[lo + 2], P[hi - 4]),
        ]
    )

    # B -- one floor: only builds at or above the floor may be installed. A
    # reader that ignores the floor installs a below-floor build.
    scen.append(
        [
            ("REQUIRE", P[mm]),
            ("CMP", "q0", P[lo], P[hi]),  # only hi clears -> hi
            ("CMP", "q1", P[ml], P[hi - 2]),  # only the upper clears
            ("CMP", "q2", P[mm], P[hi]),  # both clear -> the lower (mm)
            ("CMP", "q3", P[mm + 1], P[hi - 1]),  # both clear -> lower
        ]
    )

    # B-NONE -- floor above both candidates: nothing installable.
    scen.append(
        [
            ("REQUIRE", P[hi]),
            ("CMP", "q0", P[lo], P[mm]),  # both below -> NONE
            ("CMP", "q1", P[ml], P[mm + 1]),  # both below -> NONE
            ("CMP", "q2", P[hi - 1], P[hi]),  # only hi clears -> hi
        ]
    )

    # C -- accumulation: a high floor then a lower floor. The accumulated floor
    # stays high; a reader that honours only the latest floor lets a
    # below-high build through.
    scen.append(
        [
            ("REQUIRE", P[hi]),
            ("REQUIRE", P[ml]),
            ("CMP", "q0", P[mm], P[hi]),  # only hi clears the high floor
            ("CMP", "q1", P[ml], P[hi - 1]),  # only upper clears high floor
            ("CMP", "q2", P[hi - 2], P[hi]),  # both clear -> lower of the two
        ]
    )

    # F -- strict-prefix pairs: the shorter tag is nearer release (more mature),
    # so minimal selection installs the LONGER one. Both the near-release reader
    # and the standard-semver reader install the shorter tag instead.
    fam_f = []
    for k, base in enumerate(["beta.2", "rc", "alpha.3", "dev", "canary.1"]):
        short = cv(core, base)
        long = cv(core, base + ".7")
        fam_f.append(("CMP", "q%d" % k, long, short))
    scen.append(fam_f)

    return scen


def gen_incomparable():
    """Cross-core CMP rows resolve to INCOMPARABLE regardless of floors."""
    out = []
    pairs = [
        ((1, 0, 0), "alpha", (2, 0, 0), "alpha"),
        ((1, 4, 0), "beta.1", (1, 5, 0), "beta.1"),
        ((3, 7, 2), "rc.2", (3, 7, 3), "rc.2"),
        ((0, 9, 0), "dev", (0, 10, 0), "dev.1"),
        ((2, 0, 1), "next.4", (2, 1, 0), "next"),
        ((5, 1, 1), "gamma.2", (5, 2, 1), "gamma.9"),
    ]
    ev = []
    for k, (ca, ta, cb, tb) in enumerate(pairs):
        ev.append(("CMP", "q%d" % k, cv(ca, ta), cv(cb, tb)))
    out.append(ev)
    # A multi-core scenario: a floor on one core must not constrain another.
    out.append(
        [
            ("REQUIRE", cv((1, 0, 0), "rc")),
            ("CMP", "q0", cv((2, 0, 0), "alpha.1"), cv((2, 0, 0), "alpha")),
            ("CMP", "q1", cv((1, 0, 0), "alpha"), cv((2, 0, 0), "alpha")),
        ]
    )
    return out


def kernels(text):
    return {
        "pinned": ref.pinned_lines(text),
        "near": ref.nearrelease_lines(text),
        "smin": ref.stateless_min_lines(text),
        "latest": ref.latest_floor_lines(text),
        "semver": ref.semver_lines(text),
    }


def stride(rows, step):
    if not rows:
        return rows
    out = []
    n = len(rows)
    for start in range(step):
        i = start
        while i < n:
            out.append(rows[i])
            i += step
    return out


def scenario_rec(sid, events):
    text = render(sid, events)
    return {"scenario": text, "expected": ref.pinned_lines(text)}


def main():
    hidden_scenarios = []
    for core in CORES:
        hidden_scenarios.extend(gen_core(core))
    hidden_scenarios = stride(hidden_scenarios, 5)
    hidden_scenarios.extend(gen_incomparable())

    # Public examples must be *disambiguating*: an honest agent testing its
    # solver against them must see every naive reading fail. By example only --
    # the docs never state the selection policy in prose.
    C = (1, 0, 0)
    public_scenarios = [
        # near-release reader wrong: minimal (least-mature) build installs.
        [("CMP", "q0", cv(C, "beta.2"), cv(C, "beta.9"))],
        [("CMP", "q0", cv(C, "rc.1"), cv(C, "rc"))],
        # floor gates the install; a floor-ignoring reader picks a below-floor build.
        [
            ("REQUIRE", cv(C, "beta")),
            ("CMP", "q0", cv(C, "alpha.9"), cv(C, "rc.1")),
        ],
        # accumulation: high floor then low floor keeps the high floor. Nothing
        # below the high floor may install, even though the latest floor is low.
        [
            ("REQUIRE", cv(C, "rc")),
            ("REQUIRE", cv(C, "alpha")),
            ("CMP", "q0", cv(C, "beta.2"), cv(C, "rc.5")),
        ],
        # accumulation yielding a build: only the candidate above the retained
        # high floor installs; honouring only the latest (low) floor picks beta.
        [
            ("REQUIRE", cv(C, "rc")),
            ("REQUIRE", cv(C, "alpha")),
            ("CMP", "q0", cv(C, "beta"), cv(C, "rc")),
        ],
        # nothing clears the floor -> NONE.
        [
            ("REQUIRE", cv(C, "rc.9")),
            ("CMP", "q0", cv(C, "alpha.1"), cv(C, "beta.2")),
        ],
        # strict-prefix: shorter is nearer release, so the longer installs.
        [("CMP", "q0", cv(C, "rc.4"), cv(C, "rc"))],
        # numeric width and numeric-below-alphanumeric within-tag rules.
        [("CMP", "q0", cv(C, "x.10"), cv(C, "x.9"))],
        [("CMP", "q0", cv(C, "x.1a"), cv(C, "x.2"))],
        # different cores -> INCOMPARABLE.
        [("CMP", "q0", cv((1, 2, 0), "alpha"), cv((1, 3, 0), "alpha"))],
        # both clear the floor -> the least-mature of the two installs.
        [
            ("REQUIRE", cv(C, "beta")),
            ("CMP", "q0", cv(C, "beta.20"), cv(C, "rc")),
        ],
    ]

    public_recs = []
    for i, ev in enumerate(public_scenarios):
        public_recs.append(scenario_rec("p%02d" % i, ev))
    hidden_recs = []
    for i, ev in enumerate(hidden_scenarios):
        hidden_recs.append(scenario_rec("h%02d" % i, ev))

    with open(os.path.join(HERE, "battery", "public.jsonl"), "w") as f:
        for rec in public_recs:
            f.write(json.dumps(rec) + "\n")
    with open(os.path.join(HERE, "battery", "hidden.jsonl"), "w") as f:
        for rec in hidden_recs:
            f.write(json.dumps(rec) + "\n")

    for i, rec in enumerate(public_recs):
        with open(os.path.join(ENVDATA, "ex%02d.in" % (i + 1)), "w") as f:
            f.write(rec["scenario"] + "\n")
        with open(os.path.join(ENVDATA, "ex%02d.out" % (i + 1)), "w") as f:
            f.write("\n".join(rec["expected"]) + "\n")

    all_recs = public_recs + hidden_recs
    total = sum(len(r["expected"]) for r in all_recs)
    counts = {"near": 0, "smin": 0, "latest": 0, "semver": 0}
    none_rows = incomp_rows = 0
    for rec in all_recs:
        k = kernels(rec["scenario"])
        pn = k["pinned"]
        for j, line in enumerate(pn):
            res = line.split("|")[2]
            if res == ref.TOKEN_NONE:
                none_rows += 1
            if res == ref.TOKEN_INCOMP:
                incomp_rows += 1
            for name in counts:
                if k[name][j] != line:
                    counts[name] += 1
    pub_total = sum(len(r["expected"]) for r in public_recs)
    pub_counts = {"near": 0, "smin": 0, "latest": 0, "semver": 0}
    for rec in public_recs:
        k = kernels(rec["scenario"])
        for j, line in enumerate(k["pinned"]):
            for name in pub_counts:
                if k[name][j] != line:
                    pub_counts[name] += 1
    print("scenarios", len(all_recs), "rows", total, "public_rows", pub_total)
    print("none_rows", none_rows, "incomparable_rows", incomp_rows)
    print("trap_rows", counts)
    print("public_trap_rows", pub_counts)
    for name, c in counts.items():
        print("  frac_%s" % name, round(c / total, 4))


if __name__ == "__main__":
    main()
