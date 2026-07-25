package game

import (
	"fmt"
	"math"
	"sort"

	"tidefront.local/game/internal/forecast"
	"tidefront.local/game/internal/model"
	"tidefront.local/game/internal/timebridge"
)

type intent struct {
	fleet  Fleet
	order  Order
	source string
	target string
	status string
}

func round6(value float64) float64 {
	value = math.RoundToEven(value*1_000_000) / 1_000_000
	if value == 0 {
		return 0
	}
	return value
}

func Adjudicate(match Match, bundle model.Bundle, catalog map[string]model.CatalogEntry, clock *timebridge.Table, threads int) (Result, error) {
	if threads < 1 {
		return Result{}, fmt.Errorf("threads must be positive")
	}
	validated, err := Validate(match, bundle)
	if err != nil {
		return Result{}, err
	}
	engine := forecast.Engine{Bundle: bundle, Catalog: catalog, Clock: clock, Threads: threads}
	forecastRows, err := engine.Run(match.StartUTC, match.TurnSeconds, match.TurnCount)
	if err != nil {
		return Result{}, err
	}
	byStation := make(map[string][]model.Sample, len(forecastRows))
	for _, row := range forecastRows {
		byStation[row.ID] = row.Samples
	}
	positions := make(map[string]string, len(match.Fleets))
	owners := make(map[string]string, len(match.Nodes))
	scores := make(map[string]int, len(match.Players))
	for _, player := range match.Players {
		scores[player.ID] = 0
	}
	for _, fleet := range match.Fleets {
		positions[fleet.ID] = fleet.NodeID
	}
	for _, node := range match.Nodes {
		owners[node.ID] = node.InitialOwner
	}
	turns := make([]TurnResult, 0, match.TurnCount)
	for turn := 1; turn <= match.TurnCount; turn++ {
		depths := make(map[string]float64, len(match.Nodes))
		tides := make(map[string]float64, len(match.Nodes))
		utc := ""
		for _, node := range match.Nodes {
			samples, ok := byStation[node.StationID]
			if !ok || turn-1 >= len(samples) {
				return Result{}, fmt.Errorf("missing tide samples for station %s", node.StationID)
			}
			if utc == "" {
				utc = samples[turn-1].UTC
			} else if utc != samples[turn-1].UTC {
				return Result{}, fmt.Errorf("station clocks disagree on turn %d", turn)
			}
			tide := round6(samples[turn-1].HeightM)
			tides[node.ID] = tide
			depths[node.ID] = round6(node.BaseDepthM + tide)
		}

		intents := make(map[string]*intent, len(match.Fleets))
		contenders := make(map[string][]*intent)
		for _, fleet := range match.Fleets {
			order, ok := validated.orders[turn][fleet.ID]
			if !ok {
				order = Order{Turn: turn, FleetID: fleet.ID, Kind: "hold"}
			}
			current := positions[fleet.ID]
			entry := &intent{fleet: fleet, order: order, source: current, target: current, status: "hold"}
			if order.Kind == "move" {
				entry.target = order.TargetNodeID
				switch {
				case order.TargetNodeID == current:
					entry.status = "blocked-edge"
				case !validated.adjacent[current][order.TargetNodeID]:
					entry.status = "blocked-edge"
				case fleet.DraftM > depths[current] || fleet.DraftM > depths[order.TargetNodeID]:
					entry.status = "blocked-depth"
				default:
					entry.status = "candidate"
					contenders[order.TargetNodeID] = append(contenders[order.TargetNodeID], entry)
				}
			}
			intents[fleet.ID] = entry
		}

		selected := make(map[string]*intent)
		for _, group := range contenders {
			sort.Slice(group, func(i, j int) bool {
				left := validated.players[group[i].fleet.PlayerID]
				right := validated.players[group[j].fleet.PlayerID]
				if left.Initiative != right.Initiative {
					return left.Initiative > right.Initiative
				}
				if left.ID != right.ID {
					return left.ID < right.ID
				}
				return group[i].fleet.ID < group[j].fleet.ID
			})
			winner := group[0]
			selected[winner.fleet.ID] = winner
			for _, loser := range group[1:] {
				loser.status = "blocked-contest"
			}
		}

		occupant := make(map[string]string, len(match.Fleets))
		for _, fleet := range match.Fleets {
			occupant[positions[fleet.ID]] = fleet.ID
		}
		moveOK := resolveDependencies(selected, occupant)
		for fleetID, entry := range selected {
			if moveOK[fleetID] {
				entry.status = "moved"
			} else {
				entry.status = "blocked-occupied"
			}
		}

		newPositions := make(map[string]string, len(positions))
		for id, node := range positions {
			newPositions[id] = node
		}
		for fleetID, entry := range selected {
			if moveOK[fleetID] {
				newPositions[fleetID] = entry.target
			}
		}
		positions = newPositions

		fleetIDs := make([]string, 0, len(match.Fleets))
		for _, fleet := range match.Fleets {
			fleetIDs = append(fleetIDs, fleet.ID)
		}
		sort.Strings(fleetIDs)
		for _, fleetID := range fleetIDs {
			owners[positions[fleetID]] = validated.fleets[fleetID].PlayerID
		}

		delta := make(map[string]int, len(match.Players))
		for _, node := range match.Nodes {
			if owner := owners[node.ID]; owner != "" {
				delta[owner] += node.Value
			}
		}
		for _, player := range match.Players {
			scores[player.ID] += delta[player.ID]
		}

		nodeRows := make([]NodeState, 0, len(match.Nodes))
		for _, node := range match.Nodes {
			nodeRows = append(nodeRows, NodeState{ID: node.ID, TideM: tides[node.ID], EffectiveDepthM: depths[node.ID], Owner: owners[node.ID]})
		}
		fleetRows := make([]FleetState, 0, len(match.Fleets))
		for _, fleet := range match.Fleets {
			entry := intents[fleet.ID]
			row := FleetState{ID: fleet.ID, PlayerID: fleet.PlayerID, NodeID: positions[fleet.ID], Order: entry.order.Kind, Status: entry.status}
			if entry.order.Kind == "move" {
				row.TargetNodeID = entry.order.TargetNodeID
			}
			fleetRows = append(fleetRows, row)
		}
		turns = append(turns, TurnResult{
			Turn:       turn,
			UTC:        utc,
			Nodes:      nodeRows,
			Fleets:     fleetRows,
			ScoreDelta: scoreRows(match.Players, delta),
			Scores:     scoreRows(match.Players, scores),
		})
	}
	result := Result{SchemaVersion: 1, Game: "tidefront-v1", MatchID: match.MatchID, Turns: turns}
	result.Final = makeFinal(match, positions, owners, scores)
	Finalize(&result)
	return result, nil
}

func resolveDependencies(selected map[string]*intent, occupant map[string]string) map[string]bool {
	result := make(map[string]bool, len(selected))
	state := make(map[string]int, len(selected))
	stack := make([]string, 0, len(selected))
	index := make(map[string]int)
	var visit func(string) bool
	visit = func(fleetID string) bool {
		if value, known := result[fleetID]; known {
			return value
		}
		if state[fleetID] == 1 {
			start := index[fleetID]
			for _, member := range stack[start:] {
				result[member] = true
			}
			return true
		}
		state[fleetID] = 1
		index[fleetID] = len(stack)
		stack = append(stack, fleetID)
		entry := selected[fleetID]
		other, occupied := occupant[entry.target]
		ok := false
		switch {
		case !occupied:
			ok = true
		case selected[other] == nil:
			ok = false
		default:
			ok = visit(other)
		}
		if _, cycleMember := result[fleetID]; !cycleMember {
			result[fleetID] = ok
		}
		stack = stack[:len(stack)-1]
		delete(index, fleetID)
		state[fleetID] = 2
		return result[fleetID]
	}
	ids := make([]string, 0, len(selected))
	for id := range selected {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	for _, id := range ids {
		visit(id)
	}
	return result
}

func scoreRows(players []Player, values map[string]int) []Score {
	rows := make([]Score, 0, len(players))
	for _, player := range players {
		rows = append(rows, Score{PlayerID: player.ID, Points: values[player.ID]})
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].PlayerID < rows[j].PlayerID })
	return rows
}

func makeFinal(match Match, positions map[string]string, owners map[string]string, scores map[string]int) FinalState {
	final := FinalState{Scores: scoreRows(match.Players, scores)}
	for _, node := range match.Nodes {
		final.Nodes = append(final.Nodes, FinalNode{ID: node.ID, Owner: owners[node.ID]})
	}
	for _, fleet := range match.Fleets {
		final.Fleets = append(final.Fleets, FinalFleet{ID: fleet.ID, PlayerID: fleet.PlayerID, NodeID: positions[fleet.ID]})
	}
	players := append([]Player(nil), match.Players...)
	sort.Slice(players, func(i, j int) bool {
		leftScore, rightScore := scores[players[i].ID], scores[players[j].ID]
		if leftScore != rightScore {
			return leftScore > rightScore
		}
		if players[i].Initiative != players[j].Initiative {
			return players[i].Initiative > players[j].Initiative
		}
		return players[i].ID < players[j].ID
	})
	final.Winner = players[0].ID
	return final
}
