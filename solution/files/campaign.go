package main

import (
	"fmt"
	"sort"
	"strings"
)

func createGame(scenario Scenario) (*Game, error) {
	s, err := validateScenario(scenario)
	if err != nil {
		return nil, err
	}
	g := &Game{
		Scenario:  s,
		State:     "running",
		Turn:      1,
		Player:    s.PlayerKingdom,
		Kingdoms:  map[string]*KingdomState{},
		Islands:   map[string]*IslandState{},
		Fleets:    map[string]*FleetState{},
		Captains:  map[string]*CaptainState{},
		Diplomacy: map[string]string{},
		History:   []string{},
	}
	for _, k := range s.Kingdoms {
		g.Kingdoms[k.ID] = &KingdomState{
			ID: k.ID, Name: k.Name,
			Aetherium: k.Aetherium, Crystal: k.Crystal, Timber: k.Timber, Fuel: k.Fuel,
			Researched: append([]string{}, k.Researched...),
		}
	}
	weather0 := s.WeatherSchedule[0]
	for _, is := range s.Islands {
		g.Islands[is.ID] = &IslandState{
			ID: is.ID, Name: is.Name, Owner: is.Owner, Fortification: is.Fortification,
			Depot: is.Depot, Level: is.Level,
			AetheriumYield: is.AetheriumYield, CrystalYield: is.CrystalYield, TimberYield: is.TimberYield,
			Weather: weather0[is.ID],
		}
	}
	for _, c := range s.Captains {
		g.Captains[c.ID] = &CaptainState{ID: c.ID, Kingdom: c.Kingdom, Command: c.Command, Logistics: c.Logistics}
	}
	for _, f := range s.Fleets {
		g.Fleets[f.ID] = &FleetState{
			ID: f.ID, Kingdom: f.Kingdom, Island: f.Island,
			Hulls: append([]string{}, f.Hulls...), Fuel: f.Fuel, Readiness: f.Readiness, Captain: f.Captain,
		}
	}
	for _, d := range s.Diplomacy {
		g.Diplomacy[pairKey(d.KingdomA, d.KingdomB)] = d.Stance
	}
	g.graph = buildGraph(s)
	return g, nil
}

func executeCommand(g *Game, line string) (output string, err error) {
	// err only for API-level failure; rejected commands return output prefix and nil err
	trimmed := strings.TrimSpace(line)
	if trimmed == "" {
		return "Rejected command: empty", nil
	}
	parts := strings.Fields(trimmed)
	verb := strings.ToUpper(parts[0])
	args := parts[1:]
	normalized := verb
	if len(args) > 0 {
		normalized += " " + strings.Join(args, " ")
	}

	info := map[string]bool{"MAP": true, "STATUS": true, "FLEET": true, "ISLAND": true, "EXIT": true}
	if g.State != "running" && !info[verb] && verb != "REBOOT" {
		return "Rejected command: campaign finished", nil
	}

	switch verb {
	case "STATUS":
		return renderGame(g), nil
	case "MAP":
		return renderMap(g), nil
	case "FLEET":
		if len(args) != 1 {
			return "Rejected command: usage", nil
		}
		return renderFleet(g, args[0])
	case "ISLAND":
		if len(args) != 1 {
			return "Rejected command: usage", nil
		}
		return renderIsland(g, args[0])
	case "EXIT":
		return "Exiting", nil
	case "REBOOT":
		ng, e := createGame(g.Scenario)
		if e != nil {
			return "", e
		}
		*g = *ng
		return "Rebooted", nil
	case "MOVE":
		if len(args) != 2 {
			return "Rejected command: usage", nil
		}
		if msg := tryMove(g, g.Player, args[0], args[1]); msg != "" {
			return "Rejected command: " + msg, nil
		}
		g.History = append(g.History, normalized)
		return "Moved", nil
	case "REFUEL":
		if len(args) != 1 {
			return "Rejected command: usage", nil
		}
		if msg := tryRefuel(g, g.Player, args[0]); msg != "" {
			return "Rejected command: " + msg, nil
		}
		g.History = append(g.History, normalized)
		return "Refueled", nil
	case "CLASH":
		if len(args) != 2 {
			return "Rejected command: usage", nil
		}
		if msg := tryClash(g, g.Player, args[0], args[1]); msg != "" {
			return "Rejected command: " + msg, nil
		}
		g.History = append(g.History, normalized)
		return "Clash resolved", nil
	case "RESEARCH":
		if len(args) != 1 {
			return "Rejected command: usage", nil
		}
		if msg := tryResearch(g, g.Player, args[0]); msg != "" {
			return "Rejected command: " + msg, nil
		}
		g.History = append(g.History, normalized)
		return "Researched", nil
	case "TREATY":
		if len(args) != 2 {
			return "Rejected command: usage", nil
		}
		if msg := tryTreaty(g, g.Player, args[0], strings.ToUpper(args[1])); msg != "" {
			return "Rejected command: " + msg, nil
		}
		// normalize stance to uppercase in history
		normalized = "TREATY " + args[0] + " " + strings.ToUpper(args[1])
		g.History = append(g.History, normalized)
		return "Treaty updated", nil
	case "FORTIFY":
		if len(args) != 1 {
			return "Rejected command: usage", nil
		}
		if msg := tryFortify(g, g.Player, args[0]); msg != "" {
			return "Rejected command: " + msg, nil
		}
		g.History = append(g.History, normalized)
		return "Fortified", nil
	case "ENDTURN":
		if len(args) != 0 {
			return "Rejected command: usage", nil
		}
		endTurn(g)
		g.History = append(g.History, "ENDTURN")
		return fmt.Sprintf("Turn advanced to %d [%s]", g.Turn, g.State), nil
	default:
		return "Rejected command: unknown", nil
	}
}

func tryMove(g *Game, kingdom, fleetID, dest string) string {
	f := g.Fleets[fleetID]
	if f == nil || f.Kingdom != kingdom {
		return "fleet"
	}
	if _, ok := g.Islands[dest]; !ok {
		return "island"
	}
	if f.Island == dest {
		return "same island"
	}
	dist, path, err := shortestPath(g, f.Island, dest)
	if err != nil {
		return "path"
	}
	if dist > effectiveRange(g, f) {
		return "range"
	}
	raw, paid, _, err := pathFuelCost(g, fleetID, dest)
	if err != nil {
		return "fuel calc"
	}
	_ = raw
	if f.Fuel < paid {
		return "fuel"
	}
	owner := g.Islands[dest].Owner
	if owner != "" && stanceBetween(g.Diplomacy, kingdom, owner) == "WAR" {
		return "war territory"
	}
	// stacking
	count := 0
	for _, of := range g.Fleets {
		if of.Island == dest && of.Kingdom == kingdom {
			count++
		}
	}
	if count >= 3 {
		return "stack"
	}
	// war co-occupation check
	for _, of := range g.Fleets {
		if of.Island == dest && stanceBetween(g.Diplomacy, kingdom, of.Kingdom) == "WAR" {
			return "war co-occupation"
		}
	}
	_ = path
	f.Fuel -= paid
	f.Island = dest
	f.Readiness = max(0, f.Readiness-5*dist)
	return ""
}

func tryRefuel(g *Game, kingdom, fleetID string) string {
	f := g.Fleets[fleetID]
	if f == nil || f.Kingdom != kingdom {
		return "fleet"
	}
	is := g.Islands[f.Island]
	if is.Owner != kingdom || !is.Depot {
		return "depot"
	}
	_, _, cap, _, _ := fleetRawAtkDef(f)
	missing := cap - f.Fuel
	if missing < 0 {
		missing = 0
	}
	k := g.Kingdoms[kingdom]
	if k.Fuel < missing {
		return "treasury fuel"
	}
	k.Fuel -= missing
	f.Fuel = cap
	f.Readiness = 100
	return ""
}

func tryClash(g *Game, kingdom, fleetID, target string) string {
	f := g.Fleets[fleetID]
	if f == nil || f.Kingdom != kingdom {
		return "fleet"
	}
	_, err := resolveClash(g, fleetID, target, true)
	if err != nil {
		return err.Error()
	}
	return ""
}

func tryResearch(g *Game, kingdom, tech string) string {
	td, ok := techByID[tech]
	if !ok {
		return "tech"
	}
	k := g.Kingdoms[kingdom]
	for _, t := range k.Researched {
		if t == tech {
			return "already"
		}
	}
	if td.Prerequisite != "" {
		have := false
		for _, t := range k.Researched {
			if t == td.Prerequisite {
				have = true
				break
			}
		}
		if !have {
			return "prereq"
		}
	}
	if k.Aetherium < td.CostAetherium || k.Crystal < td.CostCrystal {
		return "cost"
	}
	k.Aetherium -= td.CostAetherium
	k.Crystal -= td.CostCrystal
	k.Researched = append(k.Researched, tech)
	return ""
}

func tryTreaty(g *Game, player, other, stance string) string {
	if other == player {
		return "self"
	}
	if _, ok := g.Kingdoms[other]; !ok {
		return "kingdom"
	}
	if !legalStances[stance] {
		return "stance"
	}
	cur := stanceBetween(g.Diplomacy, player, other)
	if cur == stance {
		return "noop"
	}
	allowed := map[string]map[string]bool{
		"PEACE":   {"ALLIED": true, "EMBARGO": true, "WAR": true},
		"ALLIED":  {"PEACE": true, "EMBARGO": true},
		"EMBARGO": {"PEACE": true, "WAR": true},
		"WAR":     {"PEACE": true, "EMBARGO": true},
	}
	if !allowed[cur][stance] {
		return "transition"
	}
	g.Diplomacy[pairKey(player, other)] = stance
	return ""
}

func tryFortify(g *Game, kingdom, islandID string) string {
	is := g.Islands[islandID]
	if is == nil || is.Owner != kingdom {
		return "island"
	}
	if is.Fortification >= 5 {
		return "max"
	}
	k := g.Kingdoms[kingdom]
	if k.Timber < 8 {
		return "timber"
	}
	k.Timber -= 8
	is.Fortification++
	return ""
}

func endTurn(g *Game) {
	// 1 upkeep
	kids := kingdomIDs(g)
	for _, kid := range kids {
		fids := fleetIDsFor(g, kid)
		for _, fid := range fids {
			f := g.Fleets[fid]
			if f == nil {
				continue
			}
			_, _, _, _, upkeep := fleetRawAtkDef(f)
			k := g.Kingdoms[kid]
			if k.Aetherium >= upkeep {
				k.Aetherium -= upkeep
				if isSupplied(g, fid) {
					f.Readiness = min(100, f.Readiness+2)
				}
			} else {
				f.Readiness = max(0, f.Readiness-15)
			}
			if !isSupplied(g, fid) {
				f.Readiness = max(0, f.Readiness-10)
			}
		}
	}
	// 2 economy
	iids := islandIDs(g)
	for _, iid := range iids {
		is := g.Islands[iid]
		if is.Owner == "" {
			continue
		}
		k := g.Kingdoms[is.Owner]
		k.Aetherium += is.AetheriumYield
		k.Crystal += is.CrystalYield
		k.Timber += is.TimberYield
		if is.Depot {
			k.Fuel += 3 + is.Level
		}
	}
	// 3 CROWN_DOCKS
	for _, kid := range kids {
		_, _, _, _, crown := kingdomTechBonuses(g.Kingdoms[kid])
		if !crown {
			continue
		}
		for _, iid := range iids {
			is := g.Islands[iid]
			if is.Owner == kid && is.Depot {
				g.Kingdoms[kid].Fuel += 2
			}
		}
	}
	// 4 NPC doctrine
	for _, kid := range kids {
		if kid == g.Player {
			continue
		}
		runDoctrine(g, kid)
	}
	// 5 weather advance
	g.Turn++
	idx := g.Turn - 1
	if idx >= len(g.Scenario.WeatherSchedule) {
		idx = len(g.Scenario.WeatherSchedule) - 1
	}
	sched := g.Scenario.WeatherSchedule[idx]
	for _, iid := range iids {
		g.Islands[iid].Weather = sched[iid]
	}
	// 6 victory
	checkVictory(g)
}

func kingdomIDs(g *Game) []string {
	out := make([]string, 0, len(g.Kingdoms))
	for id := range g.Kingdoms {
		out = append(out, id)
	}
	sort.Strings(out)
	return out
}

func islandIDs(g *Game) []string {
	out := make([]string, 0, len(g.Islands))
	for id := range g.Islands {
		out = append(out, id)
	}
	sort.Strings(out)
	return out
}

func fleetIDsFor(g *Game, kingdom string) []string {
	out := []string{}
	for id, f := range g.Fleets {
		if f.Kingdom == kingdom {
			out = append(out, id)
		}
	}
	sort.Strings(out)
	return out
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
