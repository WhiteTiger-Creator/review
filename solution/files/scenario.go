package main

import (
	"fmt"
	"regexp"
	"sort"
)

var idRe = regexp.MustCompile(`^[A-Za-z0-9_-]+$`)

func validateScenario(input Scenario) (Scenario, error) {
	s := cloneJSON(input)
	if !idRe.MatchString(s.ID) {
		return Scenario{}, fmt.Errorf("invalid id")
	}
	if s.Name == "" {
		return Scenario{}, fmt.Errorf("empty name")
	}
	if s.MaxTurns < 5 || s.MaxTurns > 60 {
		return Scenario{}, fmt.Errorf("max_turns out of range")
	}
	if s.Victory.Kind != "islands" && s.Victory.Kind != "crystal" && s.Victory.Kind != "elimination" {
		return Scenario{}, fmt.Errorf("bad victory kind")
	}
	if s.Victory.Threshold < 1 || s.Victory.Threshold > 1000 {
		return Scenario{}, fmt.Errorf("bad victory threshold")
	}
	if len(s.Kingdoms) < 2 || len(s.Kingdoms) > 6 {
		return Scenario{}, fmt.Errorf("kingdom count")
	}
	if len(s.Islands) < 3 || len(s.Islands) > 20 {
		return Scenario{}, fmt.Errorf("island count")
	}
	if len(s.Edges) < 2 || len(s.Edges) > 60 {
		return Scenario{}, fmt.Errorf("edge count")
	}
	if len(s.Fleets) < 1 || len(s.Fleets) > 20 {
		return Scenario{}, fmt.Errorf("fleet count")
	}
	if len(s.Captains) > 20 {
		return Scenario{}, fmt.Errorf("captain count")
	}
	if len(s.Diplomacy) > 20 {
		return Scenario{}, fmt.Errorf("diplomacy count")
	}
	if len(s.WeatherSchedule) != s.MaxTurns {
		return Scenario{}, fmt.Errorf("weather_schedule length")
	}

	kingdoms := map[string]KingdomSpec{}
	for _, k := range s.Kingdoms {
		if !idRe.MatchString(k.ID) {
			return Scenario{}, fmt.Errorf("bad kingdom id")
		}
		if k.Name == "" {
			return Scenario{}, fmt.Errorf("empty kingdom name")
		}
		if _, ok := kingdoms[k.ID]; ok {
			return Scenario{}, fmt.Errorf("dup kingdom")
		}
		for _, v := range []int{k.Aetherium, k.Crystal, k.Timber, k.Fuel} {
			if v < 0 || v > 10000 {
				return Scenario{}, fmt.Errorf("treasury bounds")
			}
		}
		seenTech := map[string]bool{}
		for _, t := range k.Researched {
			if _, ok := techByID[t]; !ok {
				return Scenario{}, fmt.Errorf("unknown tech")
			}
			if seenTech[t] {
				return Scenario{}, fmt.Errorf("dup tech")
			}
			seenTech[t] = true
		}
		// prerequisite closure
		for _, t := range k.Researched {
			pr := techByID[t].Prerequisite
			if pr != "" && !seenTech[pr] {
				return Scenario{}, fmt.Errorf("tech prereq missing")
			}
		}
		kingdoms[k.ID] = k
	}
	if _, ok := kingdoms[s.PlayerKingdom]; !ok {
		return Scenario{}, fmt.Errorf("player missing")
	}

	islands := map[string]IslandSpec{}
	for _, is := range s.Islands {
		if !idRe.MatchString(is.ID) {
			return Scenario{}, fmt.Errorf("bad island id")
		}
		if is.Name == "" {
			return Scenario{}, fmt.Errorf("empty island name")
		}
		if _, ok := islands[is.ID]; ok {
			return Scenario{}, fmt.Errorf("dup island")
		}
		if is.Owner != "" {
			if _, ok := kingdoms[is.Owner]; !ok {
				return Scenario{}, fmt.Errorf("island owner")
			}
		}
		if is.Fortification < 0 || is.Fortification > 5 {
			return Scenario{}, fmt.Errorf("fort")
		}
		if is.Level < 1 || is.Level > 5 {
			return Scenario{}, fmt.Errorf("level")
		}
		for _, y := range []int{is.AetheriumYield, is.CrystalYield, is.TimberYield} {
			if y < 0 || y > 20 {
				return Scenario{}, fmt.Errorf("yield")
			}
		}
		islands[is.ID] = is
	}

	edgeSeen := map[string]bool{}
	graph := map[string]map[string]bool{}
	for id := range islands {
		graph[id] = map[string]bool{}
	}
	for _, e := range s.Edges {
		if e.A == e.B {
			return Scenario{}, fmt.Errorf("loop edge")
		}
		if _, ok := islands[e.A]; !ok {
			return Scenario{}, fmt.Errorf("edge a")
		}
		if _, ok := islands[e.B]; !ok {
			return Scenario{}, fmt.Errorf("edge b")
		}
		k := pairKey(e.A, e.B)
		if edgeSeen[k] {
			return Scenario{}, fmt.Errorf("dup edge")
		}
		edgeSeen[k] = true
		graph[e.A][e.B] = true
		graph[e.B][e.A] = true
	}
	// connectivity BFS
	start := s.Islands[0].ID
	seen := map[string]bool{start: true}
	q := []string{start}
	for len(q) > 0 {
		u := q[0]
		q = q[1:]
		for v := range graph[u] {
			if !seen[v] {
				seen[v] = true
				q = append(q, v)
			}
		}
	}
	if len(seen) != len(islands) {
		return Scenario{}, fmt.Errorf("graph disconnected")
	}

	captains := map[string]CaptainSpec{}
	for _, c := range s.Captains {
		if !idRe.MatchString(c.ID) {
			return Scenario{}, fmt.Errorf("bad captain id")
		}
		if _, ok := captains[c.ID]; ok {
			return Scenario{}, fmt.Errorf("dup captain")
		}
		if _, ok := kingdoms[c.Kingdom]; !ok {
			return Scenario{}, fmt.Errorf("captain kingdom")
		}
		if c.Command < 0 || c.Command > 5 || c.Logistics < 0 || c.Logistics > 5 {
			return Scenario{}, fmt.Errorf("captain stats")
		}
		captains[c.ID] = c
	}

	dipSeen := map[string]bool{}
	dip := map[string]string{}
	for _, d := range s.Diplomacy {
		if d.KingdomA == d.KingdomB {
			return Scenario{}, fmt.Errorf("self diplomacy")
		}
		if _, ok := kingdoms[d.KingdomA]; !ok {
			return Scenario{}, fmt.Errorf("dip a")
		}
		if _, ok := kingdoms[d.KingdomB]; !ok {
			return Scenario{}, fmt.Errorf("dip b")
		}
		if !legalStances[d.Stance] {
			return Scenario{}, fmt.Errorf("stance")
		}
		k := pairKey(d.KingdomA, d.KingdomB)
		if dipSeen[k] {
			return Scenario{}, fmt.Errorf("dup dip")
		}
		dipSeen[k] = true
		dip[k] = d.Stance
	}

	fleets := map[string]FleetSpec{}
	captainUse := map[string]string{}
	stack := map[string]map[string]int{} // island -> kingdom -> count
	occupiers := map[string]map[string]bool{}
	for _, f := range s.Fleets {
		if !idRe.MatchString(f.ID) {
			return Scenario{}, fmt.Errorf("bad fleet id")
		}
		if _, ok := fleets[f.ID]; ok {
			return Scenario{}, fmt.Errorf("dup fleet")
		}
		if _, ok := kingdoms[f.Kingdom]; !ok {
			return Scenario{}, fmt.Errorf("fleet kingdom")
		}
		if _, ok := islands[f.Island]; !ok {
			return Scenario{}, fmt.Errorf("fleet island")
		}
		if len(f.Hulls) < 1 || len(f.Hulls) > 8 {
			return Scenario{}, fmt.Errorf("hulls len")
		}
		cap := 0
		for _, h := range f.Hulls {
			hd, ok := hullByID[h]
			if !ok {
				return Scenario{}, fmt.Errorf("hull")
			}
			cap += hd.FuelCap
		}
		if f.Fuel < 0 || f.Fuel > cap {
			return Scenario{}, fmt.Errorf("fuel")
		}
		if f.Readiness < 0 || f.Readiness > 100 {
			return Scenario{}, fmt.Errorf("readiness")
		}
		if f.Captain != "" {
			c, ok := captains[f.Captain]
			if !ok || c.Kingdom != f.Kingdom {
				return Scenario{}, fmt.Errorf("captain assign")
			}
			if other, used := captainUse[f.Captain]; used && other != f.ID {
				return Scenario{}, fmt.Errorf("captain multi")
			}
			captainUse[f.Captain] = f.ID
		}
		if stack[f.Island] == nil {
			stack[f.Island] = map[string]int{}
		}
		stack[f.Island][f.Kingdom]++
		if stack[f.Island][f.Kingdom] > 3 {
			return Scenario{}, fmt.Errorf("stack")
		}
		if occupiers[f.Island] == nil {
			occupiers[f.Island] = map[string]bool{}
		}
		occupiers[f.Island][f.Kingdom] = true
		fleets[f.ID] = f
	}
	for island, ks := range occupiers {
		ids := make([]string, 0, len(ks))
		for k := range ks {
			ids = append(ids, k)
		}
		sort.Strings(ids)
		for i := 0; i < len(ids); i++ {
			for j := i + 1; j < len(ids); j++ {
				if stanceBetween(dip, ids[i], ids[j]) == "WAR" {
					return Scenario{}, fmt.Errorf("war co-occupation on %s", island)
				}
			}
		}
	}

	for i, m := range s.WeatherSchedule {
		if len(m) != len(islands) {
			return Scenario{}, fmt.Errorf("weather keys %d", i)
		}
		for id := range islands {
			w, ok := m[id]
			if !ok {
				return Scenario{}, fmt.Errorf("weather missing island")
			}
			if _, ok := weatherMoveMul[w]; !ok {
				return Scenario{}, fmt.Errorf("bad weather")
			}
		}
		for id := range m {
			if _, ok := islands[id]; !ok {
				return Scenario{}, fmt.Errorf("extra weather key")
			}
		}
	}
	return s, nil
}

func stanceBetween(dip map[string]string, a, b string) string {
	if a == b {
		return "PEACE"
	}
	if s, ok := dip[pairKey(a, b)]; ok {
		return s
	}
	return "PEACE"
}
