package main

import "fmt"

func combatPreview(g *Game, fleetID, target string) (ClashResult, error) {
	return resolveClash(cloneJSON(g), fleetID, target, false)
}

func simulateClash(g *Game, fleetID, target string) (*Game, ClashResult, error) {
	ng := cloneJSON(g)
	ng.graph = nil
	res, err := resolveClash(ng, fleetID, target, true)
	if err != nil {
		return nil, ClashResult{}, err
	}
	return ng, res, nil
}

func resolveClash(g *Game, fleetID, target string, mutate bool) (ClashResult, error) {
	atk := g.Fleets[fleetID]
	if atk == nil {
		return ClashResult{}, fmt.Errorf("attacker")
	}

	islandID := ""
	var def *FleetState
	fortOnly := false

	if f, ok := g.Fleets[target]; ok {
		islandID = f.Island
		def = f
		if stanceBetween(g.Diplomacy, atk.Kingdom, def.Kingdom) != "WAR" {
			return ClashResult{}, fmt.Errorf("not at war")
		}
	} else if isl, ok := g.Islands[target]; ok {
		islandID = isl.ID
		def = pickDefenderFleet(g, atk.Kingdom, islandID)
		if def == nil {
			fortOnly = true
			if isl.Owner != "" && stanceBetween(g.Diplomacy, atk.Kingdom, isl.Owner) != "WAR" {
				return ClashResult{}, fmt.Errorf("not at war with owner")
			}
		} else if stanceBetween(g.Diplomacy, atk.Kingdom, def.Kingdom) != "WAR" {
			return ClashResult{}, fmt.Errorf("not at war")
		}
	} else {
		return ClashResult{}, fmt.Errorf("target")
	}

	dist, _, err := shortestPath(g, atk.Island, islandID)
	if err != nil || dist != 1 {
		return ClashResult{}, fmt.Errorf("not adjacent")
	}

	aScore, dScore := computeScores(g, atk, def, islandID)
	res := ClashResult{
		AttackerID:    atk.ID,
		IslandID:      islandID,
		AttackerScore: aScore,
		DefenderScore: dScore,
	}
	if def != nil {
		res.DefenderID = def.ID
	}
	attackerWins := aScore > dScore
	if attackerWins {
		res.Winner = "attacker"
	} else {
		res.Winner = "defender"
	}
	if !mutate {
		return res, nil
	}

	if attackerWins {
		if fortOnly {
			atk.Readiness = max(0, atk.Readiness-8)
			transferOwnership(g, islandID, atk.Kingdom)
			res.OwnershipChanged = true
		} else {
			loss := 1 + (aScore-dScore)/15
			if loss > len(def.Hulls) {
				loss = len(def.Hulls)
			}
			res.DefenderHullsLost = loss
			def.Hulls = append([]string{}, def.Hulls[:len(def.Hulls)-loss]...)
			def.Readiness = max(0, def.Readiness-25)
			atk.Readiness = max(0, atk.Readiness-10)
			owner := g.Islands[islandID].Owner
			if len(def.Hulls) == 0 {
				delete(g.Fleets, def.ID)
			}
			if owner == "" || owner == def.Kingdom {
				transferOwnership(g, islandID, atk.Kingdom)
				res.OwnershipChanged = true
			}
		}
	} else {
		loss := 1 + (dScore-aScore)/20
		if loss > len(atk.Hulls) {
			loss = len(atk.Hulls)
		}
		res.AttackerHullsLost = loss
		atk.Hulls = append([]string{}, atk.Hulls[:len(atk.Hulls)-loss]...)
		atk.Readiness = max(0, atk.Readiness-25)
		if def != nil {
			def.Readiness = max(0, def.Readiness-10)
		}
		if len(atk.Hulls) == 0 {
			delete(g.Fleets, atk.ID)
		}
	}

	copied := cloneJSON(res)
	g.LastClash = &copied
	return res, nil
}

func transferOwnership(g *Game, islandID, newOwner string) {
	g.Islands[islandID].Owner = newOwner
	g.Islands[islandID].Fortification = max(0, g.Islands[islandID].Fortification-1)
}

func pickDefenderFleet(g *Game, attackerKingdom, islandID string) *FleetState {
	var best *FleetState
	bestDef := -1
	for _, f := range g.Fleets {
		if f.Island != islandID {
			continue
		}
		if stanceBetween(g.Diplomacy, attackerKingdom, f.Kingdom) != "WAR" {
			continue
		}
		_, d, _, _, _ := fleetRawAtkDef(f)
		if best == nil || d > bestDef || (d == bestDef && f.ID < best.ID) {
			best = f
			bestDef = d
		}
	}
	return best
}

func computeScores(g *Game, atk *FleetState, def *FleetState, islandID string) (aScore, dScore int) {
	rawAtk, _, _, _, _ := fleetRawAtkDef(atk)
	capAtk, _, _, _ := captainBonuses(g, atk)
	atkVal := rawAtk * (100 + capAtk) / 100
	atkVal = atkVal * atk.Readiness / 100
	_, _, atkPct, _, _ := kingdomTechBonuses(g.Kingdoms[atk.Kingdom])
	atkVal = atkVal * (100 + atkPct) / 100

	weather := g.Islands[islandID].Weather
	wAtk := weatherAtkMul[weather]
	wDef := weatherDefMul[weather]
	supAtk := 60
	if isSupplied(g, atk.ID) {
		supAtk = 100
	}
	aScore = atkVal * wAtk * supAtk / 10000

	defVal := 0
	supDef := 60
	if def != nil {
		_, rawDef, _, _, _ := fleetRawAtkDef(def)
		_, capDef, _, _ := captainBonuses(g, def)
		defVal = rawDef * (100 + capDef) / 100
		defVal = defVal * def.Readiness / 100
		_, _, _, defPct, _ := kingdomTechBonuses(g.Kingdoms[def.Kingdom])
		defVal = defVal * (100 + defPct) / 100
		if isSupplied(g, def.ID) {
			supDef = 100
		}
	} else {
		owner := g.Islands[islandID].Owner
		if owner == "" {
			supDef = 100
		} else {
			supDef = ownerSupplyMul(g, owner, islandID)
		}
	}
	fortBonus := 10 * g.Islands[islandID].Fortification
	dScore = defVal*wDef*supDef/10000 + fortBonus
	return aScore, dScore
}

func ownerSupplyMul(g *Game, owner, islandID string) int {
	ensureGraph(g)
	startOwner := g.Islands[islandID].Owner
	if startOwner != owner && stanceBetween(g.Diplomacy, owner, startOwner) != "ALLIED" {
		return 60
	}
	q := []string{islandID}
	seen := map[string]bool{islandID: true}
	for len(q) > 0 {
		u := q[0]
		q = q[1:]
		is := g.Islands[u]
		if is.Depot && is.Owner == owner {
			return 100
		}
		for _, v := range g.graph[u] {
			if seen[v] {
				continue
			}
			own := g.Islands[v].Owner
			if own == owner || stanceBetween(g.Diplomacy, owner, own) == "ALLIED" {
				seen[v] = true
				q = append(q, v)
			}
		}
	}
	return 60
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
