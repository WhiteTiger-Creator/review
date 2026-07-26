package main

import (
	"fmt"
	"sort"
	"strings"
)

func runDoctrine(g *Game, kingdom string) {
	// 1 clash
	fids := fleetIDsFor(g, kingdom)
	type cand struct{ fleet, island string }
	var clashes []cand
	for _, fid := range fids {
		f := g.Fleets[fid]
		if f == nil {
			continue
		}
		ensureGraph(g)
		for _, nid := range g.graph[f.Island] {
			is := g.Islands[nid]
			hostile := false
			if is.Owner != "" && stanceBetween(g.Diplomacy, kingdom, is.Owner) == "WAR" {
				hostile = true
			}
			for _, of := range g.Fleets {
				if of.Island == nid && stanceBetween(g.Diplomacy, kingdom, of.Kingdom) == "WAR" {
					hostile = true
				}
			}
			if !hostile {
				continue
			}
			// legality probe
			ng := cloneJSON(g)
			ng.graph = nil
			if _, err := resolveClash(ng, fid, nid, true); err == nil {
				clashes = append(clashes, cand{fid, nid})
			}
		}
	}
	if len(clashes) > 0 {
		sort.Slice(clashes, func(i, j int) bool {
			if clashes[i].fleet != clashes[j].fleet {
				return clashes[i].fleet < clashes[j].fleet
			}
			return clashes[i].island < clashes[j].island
		})
		_, _ = resolveClash(g, clashes[0].fleet, clashes[0].island, true)
		return
	}
	// 2 move one hop toward nearest unowned-by-self island
	type mcand struct {
		fleet, dest string
		dist        int
	}
	var moves []mcand
	for _, fid := range fids {
		f := g.Fleets[fid]
		if f == nil {
			continue
		}
		for _, iid := range islandIDs(g) {
			if g.Islands[iid].Owner == kingdom {
				continue
			}
			dist, path, err := shortestPath(g, f.Island, iid)
			if err != nil || dist < 1 {
				continue
			}
			hop := path[1]
			ng := cloneJSON(g)
			ng.graph = nil
			if msg := tryMove(ng, kingdom, fid, hop); msg == "" {
				moves = append(moves, mcand{fid, hop, dist})
			}
		}
	}
	if len(moves) > 0 {
		sort.Slice(moves, func(i, j int) bool {
			if moves[i].dist != moves[j].dist {
				return moves[i].dist < moves[j].dist
			}
			if moves[i].dest != moves[j].dest {
				return moves[i].dest < moves[j].dest
			}
			return moves[i].fleet < moves[j].fleet
		})
		_ = tryMove(g, kingdom, moves[0].fleet, moves[0].dest)
		return
	}
	// 3 research first affordable catalog tech
	for _, t := range techCatalog {
		if msg := tryResearch(g, kingdom, t.ID); msg == "" {
			return
		}
	}
}

func checkVictory(g *Game) {
	if g.State != "running" {
		return
	}
	if g.Turn > g.Scenario.MaxTurns {
		g.State = "lost"
		sb := scoreGame(g)
		g.ScoreBreakdown = &sb
		return
	}
	pIslands := countOwned(g, g.Player)
	pFleets := countFleets(g, g.Player)
	if pIslands == 0 && pFleets == 0 {
		g.State = "lost"
		sb := scoreGame(g)
		g.ScoreBreakdown = &sb
		return
	}
	won := false
	switch g.Scenario.Victory.Kind {
	case "islands":
		won = pIslands >= g.Scenario.Victory.Threshold
	case "crystal":
		won = g.Kingdoms[g.Player].Crystal >= g.Scenario.Victory.Threshold
	case "elimination":
		won = true
		for _, kid := range kingdomIDs(g) {
			if kid == g.Player {
				continue
			}
			if countOwned(g, kid) > 0 || countFleets(g, kid) > 0 {
				won = false
				break
			}
		}
	}
	if won {
		g.State = "won"
		sb := scoreGame(g)
		g.ScoreBreakdown = &sb
	}
}

func countOwned(g *Game, kingdom string) int {
	n := 0
	for _, is := range g.Islands {
		if is.Owner == kingdom {
			n++
		}
	}
	return n
}

func countFleets(g *Game, kingdom string) int {
	n := 0
	for _, f := range g.Fleets {
		if f.Kingdom == kingdom {
			n++
		}
	}
	return n
}

func scoreGame(g *Game) ScoreBreakdown {
	pIslands := countOwned(g, g.Player)
	pFleets := countFleets(g, g.Player)
	k := g.Kingdoms[g.Player]
	objective := 0
	if g.State == "won" {
		objective = 100
	}
	territory := 5 * pIslands
	resources := (k.Aetherium + k.Crystal + k.Timber + k.Fuel) / 10
	survival := 3 * pFleets
	for _, f := range g.Fleets {
		if f.Kingdom == g.Player {
			survival += f.Readiness / 10
		}
	}
	maxEnemy := 0
	defeated := 0
	for _, kid := range kingdomIDs(g) {
		if kid == g.Player {
			continue
		}
		owned := countOwned(g, kid)
		if owned > maxEnemy {
			maxEnemy = owned
		}
		if owned == 0 && countFleets(g, kid) == 0 {
			defeated++
		}
	}
	dominance := 4 * (pIslands - maxEnemy)
	mission := 0
	switch g.Scenario.Victory.Kind {
	case "islands":
		mission = 2 * pIslands
	case "crystal":
		mission = k.Crystal / 5
	case "elimination":
		mission = 10 * defeated
	}
	sb := ScoreBreakdown{
		Objective: objective, Territory: territory, Resources: resources,
		Survival: survival, Dominance: dominance, Violations: 0, Mission: mission,
	}
	sb.Total = sb.Objective + sb.Territory + sb.Resources + sb.Survival + sb.Dominance + sb.Violations + sb.Mission
	return sb
}

func validateGame(g *Game) (bool, []string) {
	v := make([]string, 0)
	for _, f := range g.Fleets {
		_, _, cap, _, _ := fleetRawAtkDef(f)
		if f.Fuel < 0 || f.Fuel > cap {
			v = append(v, "fuel:"+f.ID)
		}
		if f.Readiness < 0 || f.Readiness > 100 {
			v = append(v, "readiness:"+f.ID)
		}
		if _, ok := g.Kingdoms[f.Kingdom]; !ok {
			v = append(v, "fleet-kingdom:"+f.ID)
		}
		if _, ok := g.Islands[f.Island]; !ok {
			v = append(v, "fleet-island:"+f.ID)
		}
		for _, h := range f.Hulls {
			if _, ok := hullByID[h]; !ok {
				v = append(v, "hull:"+f.ID)
			}
		}
	}
	stack := map[string]map[string]int{}
	for _, f := range g.Fleets {
		if stack[f.Island] == nil {
			stack[f.Island] = map[string]int{}
		}
		stack[f.Island][f.Kingdom]++
		if stack[f.Island][f.Kingdom] > 3 {
			v = append(v, "stack:"+f.Island)
		}
	}
	for _, k := range g.Kingdoms {
		have := map[string]bool{}
		for _, t := range k.Researched {
			have[t] = true
			td, ok := techByID[t]
			if !ok {
				v = append(v, "tech:"+t)
				continue
			}
			if td.Prerequisite != "" && !have[td.Prerequisite] {
				// prereq must also be researched — check full set
			}
		}
		for _, t := range k.Researched {
			td := techByID[t]
			if td.Prerequisite != "" && !have[td.Prerequisite] {
				v = append(v, "prereq:"+k.ID+":"+t)
			}
		}
	}
	sort.Strings(v)
	return len(v) == 0, v
}

func renderGame(g *Game) string {
	k := g.Kingdoms[g.Player]
	res := "(none)"
	if len(k.Researched) > 0 {
		res = strings.Join(k.Researched, ",")
	}
	return fmt.Sprintf(
		"Turn %d [%s] Player=%s\nTreasury aetherium=%d crystal=%d timber=%d fuel=%d\nIslands owned=%d Fleets=%d\nResearched: %s\n",
		g.Turn, g.State, g.Player, k.Aetherium, k.Crystal, k.Timber, k.Fuel,
		countOwned(g, g.Player), countFleets(g, g.Player), res,
	)
}

func renderMap(g *Game) string {
	var b strings.Builder
	for _, iid := range islandIDs(g) {
		is := g.Islands[iid]
		fmt.Fprintf(&b, "%s owner=%s fort=%d weather=%s depot=%v\n", is.ID, is.Owner, is.Fortification, is.Weather, is.Depot)
	}
	return b.String()
}

func renderFleet(g *Game, id string) (string, error) {
	f := g.Fleets[id]
	if f == nil {
		return "Rejected command: fleet", nil
	}
	return fmt.Sprintf("%s kingdom=%s island=%s fuel=%d readiness=%d hulls=%s captain=%s\n",
		f.ID, f.Kingdom, f.Island, f.Fuel, f.Readiness, strings.Join(f.Hulls, ","), f.Captain), nil
}

func renderIsland(g *Game, id string) (string, error) {
	is := g.Islands[id]
	if is == nil {
		return "Rejected command: island", nil
	}
	return fmt.Sprintf("%s owner=%s fort=%d weather=%s depot=%v level=%d\n",
		is.ID, is.Owner, is.Fortification, is.Weather, is.Depot, is.Level), nil
}

func replayRun(scenario Scenario, commands []string) (*Game, []string, error) {
	g, err := createGame(scenario)
	if err != nil {
		return nil, nil, err
	}
	outputs := make([]string, 0, len(commands))
	for _, c := range commands {
		out, err := executeCommand(g, c)
		if err != nil {
			return nil, nil, err
		}
		outputs = append(outputs, out)
	}
	return g, outputs, nil
}
