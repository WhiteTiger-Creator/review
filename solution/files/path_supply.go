package main

import (
	"fmt"
	"sort"
)

func buildGraph(s Scenario) map[string][]string {
	g := map[string][]string{}
	for _, is := range s.Islands {
		g[is.ID] = nil
	}
	for _, e := range s.Edges {
		g[e.A] = append(g[e.A], e.B)
		g[e.B] = append(g[e.B], e.A)
	}
	for id := range g {
		sort.Strings(g[id])
	}
	return g
}

func ensureGraph(g *Game) {
	if g.graph == nil {
		g.graph = buildGraph(g.Scenario)
	}
}

func shortestPath(g *Game, from, to string) (dist int, path []string, err error) {
	ensureGraph(g)
	if _, ok := g.Islands[from]; !ok {
		return 0, nil, fmt.Errorf("from")
	}
	if _, ok := g.Islands[to]; !ok {
		return 0, nil, fmt.Errorf("to")
	}
	if from == to {
		return 0, []string{from}, nil
	}

	// BFS layers; track all parents at best distance for lex reconstruction.
	bestDist := map[string]int{from: 0}
	parents := map[string][]string{}
	q := []string{from}
	for len(q) > 0 {
		u := q[0]
		q = q[1:]
		du := bestDist[u]
		for _, v := range g.graph[u] {
			nd := du + 1
			bd, seen := bestDist[v]
			if !seen {
				bestDist[v] = nd
				parents[v] = []string{u}
				q = append(q, v)
			} else if nd == bd {
				parents[v] = append(parents[v], u)
			}
		}
	}
	if _, ok := bestDist[to]; !ok {
		return 0, nil, fmt.Errorf("unreachable")
	}
	// Reconstruct all min paths via DFS and pick lex-smallest.
	var paths [][]string
	var dfs func(cur string, acc []string)
	dfs = func(cur string, acc []string) {
		if cur == from {
			p := append([]string{from}, reverseCopy(acc)...)
			paths = append(paths, p)
			return
		}
		for _, p := range parents[cur] {
			dfs(p, append(acc, cur))
		}
	}
	dfs(to, nil)
	best := paths[0]
	for _, p := range paths[1:] {
		if pathLess(p, best) {
			best = p
		}
	}
	return bestDist[to], best, nil
}

func reverseCopy(a []string) []string {
	out := make([]string, len(a))
	for i := range a {
		out[i] = a[len(a)-1-i]
	}
	return out
}

func pathLess(a, b []string) bool {
	n := len(a)
	if len(b) < n {
		n = len(b)
	}
	for i := 0; i < n; i++ {
		if a[i] != b[i] {
			return a[i] < b[i]
		}
	}
	return len(a) < len(b)
}

func edgeCost(g *Game, destIsland string) int {
	mul := weatherMoveMul[g.Islands[destIsland].Weather]
	return (mul + 99) / 100
}

func pathRawCost(g *Game, path []string) int {
	sum := 0
	for i := 1; i < len(path); i++ {
		sum += edgeCost(g, path[i])
	}
	return sum
}

func kingdomTechBonuses(k *KingdomState) (rangeBonus, fuelDisc, atkPct, defPct int, crown bool) {
	have := map[string]bool{}
	for _, t := range k.Researched {
		have[t] = true
	}
	for _, t := range techCatalog {
		if !have[t.ID] {
			continue
		}
		rangeBonus += t.RangeBonus
		fuelDisc += t.FuelDiscountPct
		atkPct += t.AtkPct
		defPct += t.DefPct
		if t.CrownDocks {
			crown = true
		}
	}
	return
}

func captainBonuses(g *Game, f *FleetState) (atkPct, defPct, rangeBonus, fuelDisc int) {
	if f.Captain == "" {
		return
	}
	c := g.Captains[f.Captain]
	if c == nil {
		return
	}
	atkPct = 2 * c.Command
	defPct = 2 * c.Command
	if c.Logistics >= 3 {
		rangeBonus = 1
	}
	fuelDisc = 5 * c.Logistics
	return
}

func fleetRawAtkDef(f *FleetState) (atk, def, fuelCap, baseRange, upkeep int) {
	baseRange = 99
	for _, h := range f.Hulls {
		hd := hullByID[h]
		atk += hd.Atk
		def += hd.Def
		fuelCap += hd.FuelCap
		upkeep += hd.Upkeep
		if hd.BaseRange < baseRange {
			baseRange = hd.BaseRange
		}
	}
	if len(f.Hulls) == 0 {
		baseRange = 0
	}
	return
}

func effectiveRange(g *Game, f *FleetState) int {
	_, _, _, base, _ := fleetRawAtkDef(f)
	_, _, br, _ := captainBonuses(g, f)
	tr, _, _, _, _ := kingdomTechBonuses(g.Kingdoms[f.Kingdom])
	return base + br + tr
}

func pathFuelCost(g *Game, fleetID, to string) (raw, paid int, path []string, err error) {
	f := g.Fleets[fleetID]
	if f == nil {
		return 0, 0, nil, fmt.Errorf("fleet")
	}
	_, path, err = shortestPath(g, f.Island, to)
	if err != nil {
		return 0, 0, nil, err
	}
	raw = pathRawCost(g, path)
	_, _, _, fuelDiscCap := captainBonuses(g, f)
	_, fuelDiscTech, _, _, _ := kingdomTechBonuses(g.Kingdoms[f.Kingdom])
	discount := fuelDiscCap + fuelDiscTech
	if raw == 0 {
		return 0, 0, path, nil
	}
	paid = raw * (100 - discount) / 100
	if paid < 1 {
		paid = 1
	}
	return raw, paid, path, nil
}

func isSupplied(g *Game, fleetID string) bool {
	f := g.Fleets[fleetID]
	if f == nil {
		return false
	}
	ensureGraph(g)
	startOwner := g.Islands[f.Island].Owner
	if startOwner != f.Kingdom && stanceBetween(g.Diplomacy, f.Kingdom, startOwner) != "ALLIED" {
		return false
	}
	q := []string{f.Island}
	seen := map[string]bool{f.Island: true}
	for len(q) > 0 {
		u := q[0]
		q = q[1:]
		is := g.Islands[u]
		if is.Depot && is.Owner == f.Kingdom {
			return true
		}
		for _, v := range g.graph[u] {
			if seen[v] {
				continue
			}
			own := g.Islands[v].Owner
			if own == f.Kingdom || stanceBetween(g.Diplomacy, f.Kingdom, own) == "ALLIED" {
				seen[v] = true
				q = append(q, v)
			}
		}
	}
	return false
}
