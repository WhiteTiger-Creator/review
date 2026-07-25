#!/bin/bash
set -euo pipefail
cd /app || exit 1

cat > select.go <<'EOF'
package main

import "strings"

func parseVer(v string) [3]int {
	s := strings.TrimPrefix(v, "v")
	parts := strings.Split(s, ".")
	var out [3]int
	for i := 0; i < 3 && i < len(parts); i++ {
		n := 0
		for _, c := range parts[i] {
			if c >= '0' && c <= '9' {
				n = n*10 + int(c-'0')
			}
		}
		out[i] = n
	}
	return out
}

// vgt reports whether a is strictly greater than b.
func vgt(a, b string) bool {
	pa := parseVer(a)
	pb := parseVer(b)
	for i := 0; i < 3; i++ {
		if pa[i] != pb[i] {
			return pa[i] > pb[i]
		}
	}
	return false
}

func vmaxOf(vs ...string) string {
	best := "v0.0.0"
	for _, v := range vs {
		if v != "" && vgt(v, best) {
			best = v
		}
	}
	return best
}

// floorOf is the highest of the base, the scenario lock entry, and the version
// carried for the module in the running session.
func floorOf(sc *scenario, sess map[string]string, m string) string {
	f := "v0.0.0"
	if v, ok := sc.lock[m]; ok {
		f = vmaxOf(f, v)
	}
	if v, ok := sess[m]; ok {
		f = vmaxOf(f, v)
	}
	return f
}

// expand is the monotone lower-bound fixed point. An edge declared by version
// uver of u is in force only once u is built and sel[u] has reached uver (the
// root's edges are always in force). Requirers in skip contribute no edges.
func expand(sc *scenario, sess map[string]string, skip map[string]bool) (map[string]string, map[string]bool) {
	sel := map[string]string{sc.root: floorOf(sc, sess, sc.root)}
	build := map[string]bool{sc.root: true}
	changed := true
	for changed {
		changed = false
		for u, edges := range sc.reqs {
			if !build[u] || skip[u] {
				continue
			}
			for _, e := range edges {
				if u != sc.root && vgt(e.uver, sel[u]) {
					continue
				}
				if !build[e.dep] {
					build[e.dep] = true
					sel[e.dep] = floorOf(sc, sess, e.dep)
					changed = true
				}
				if vgt(e.ver, sel[e.dep]) {
					sel[e.dep] = e.ver
					changed = true
				}
			}
		}
	}
	return sel, build
}

// ceilings computes the lowest in-force ceiling per module. A CAP declared by
// version uver of u limits dep to at most maxver, gated like a requirement and
// evaluated against the maximal (cap-free) demand.
func ceilings(sc *scenario, demand map[string]string, dbuild map[string]bool) map[string]string {
	ceil := map[string]string{}
	for u, cs := range sc.caps {
		if !dbuild[u] {
			continue
		}
		for _, c := range cs {
			if u != sc.root && vgt(c.uver, demand[u]) {
				continue
			}
			if cur, ok := ceil[c.dep]; !ok || vgt(cur, c.maxver) {
				ceil[c.dep] = c.maxver
			}
		}
	}
	return ceil
}

// inForceCeilings merges the local caps (gated on the maximal cap-free demand)
// with the carried scar ceilings (unconditional); the binding ceiling per
// module is the lowest of the two.
func inForceCeilings(sc *scenario, sess, scar map[string]string) (map[string]string, map[string]bool, map[string]string) {
	demand, dbuild := expand(sc, sess, nil)
	ceil := ceilings(sc, demand, dbuild)
	for m, c := range scar {
		if cur, ok := ceil[m]; !ok || vgt(cur, c) {
			ceil[m] = c
		}
	}
	return demand, dbuild, ceil
}

// step resolves one scenario against a session floor and scar table: expand to
// the maximal demand, judge each module against its binding ceiling, then
// retract conflicted providers so modules reachable only through them drop out.
// It also returns the binding-ceiling map used to update scars.
func step(sc *scenario, sess, scar map[string]string) (map[string]string, map[string]bool, map[string]bool, map[string]string) {
	demand, dbuild, ceil := inForceCeilings(sc, sess, scar)
	conflict := map[string]bool{}
	for m := range dbuild {
		if c, ok := ceil[m]; ok && vgt(demand[m], c) {
			conflict[m] = true
		}
	}
	sel, build := expand(sc, sess, conflict)
	live := map[string]bool{}
	for m := range conflict {
		if build[m] {
			live[m] = true
		}
	}
	return sel, build, live, ceil
}

func resolveStream(scs []*scenario) []map[string]string {
	sess := map[string]string{}
	scar := map[string]string{}
	out := make([]map[string]string, 0, len(scs))
	for _, sc := range scs {
		if sc.resetBefore {
			sess = map[string]string{}
			scar = map[string]string{}
		}
		sel, build, live, ceil := step(sc, sess, scar)
		res := map[string]string{}
		for m := range build {
			if live[m] {
				res[m] = "CONFLICT"
			} else {
				res[m] = sel[m]
			}
		}
		out = append(out, res)
		// Built, non-conflicted modules lift the monotone session floor.
		for m := range build {
			if live[m] {
				continue
			}
			if cur, ok := sess[m]; !ok || vgt(sel[m], cur) {
				sess[m] = sel[m]
			}
		}
		// Over-constrained modules deposit their binding ceiling as a scar that
		// only ratchets lower and re-imposes itself in every later scenario.
		for m := range live {
			c := ceil[m]
			if cur, ok := scar[m]; !ok || vgt(cur, c) {
				scar[m] = c
			}
		}
	}
	return out
}
EOF

make clean >/dev/null 2>&1 || true
make || exit 1
./resolve < data/examples/ex01.in || exit 1
