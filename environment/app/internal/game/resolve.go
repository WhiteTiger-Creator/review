package game

import (
	"fmt"
	"sort"

	"tidefront.local/game/internal/forecast"
	"tidefront.local/game/internal/model"
	"tidefront.local/game/internal/timebridge"
)

// Adjudicate is intentionally incomplete in the starter tree. It applies moves
// sequentially and does not implement simultaneous occupancy dependencies.
func Adjudicate(match Match, bundle model.Bundle, catalog map[string]model.CatalogEntry, clock *timebridge.Table, threads int) (Result, error) {
	validated, err := Validate(match, bundle)
	if err != nil {
		return Result{}, err
	}
	engine := forecast.Engine{Bundle: bundle, Catalog: catalog, Clock: clock, Threads: threads}
	forecastRows, err := engine.Run(match.StartUTC, match.TurnSeconds, match.TurnCount)
	if err != nil {
		return Result{}, err
	}
	byStation := make(map[string][]model.Sample)
	for _, row := range forecastRows {
		byStation[row.ID] = row.Samples
	}
	positions := make(map[string]string)
	owners := make(map[string]string)
	scores := make(map[string]int)
	for _, fleet := range match.Fleets {
		positions[fleet.ID] = fleet.NodeID
	}
	for _, node := range match.Nodes {
		owners[node.ID] = node.InitialOwner
	}
	turns := make([]TurnResult, 0, match.TurnCount)
	for turn := 1; turn <= match.TurnCount; turn++ {
		fleetStates := make([]FleetState, 0, len(match.Fleets))
		for _, fleet := range match.Fleets {
			order, ok := validated.orders[turn][fleet.ID]
			state := FleetState{ID: fleet.ID, PlayerID: fleet.PlayerID, NodeID: positions[fleet.ID], Order: "hold", Status: "hold"}
			if ok && order.Kind == "move" && validated.adjacent[positions[fleet.ID]][order.TargetNodeID] {
				positions[fleet.ID] = order.TargetNodeID
				state.Order = "move"
				state.TargetNodeID = order.TargetNodeID
				state.NodeID = order.TargetNodeID
				state.Status = "moved"
			}
			owners[positions[fleet.ID]] = fleet.PlayerID
			fleetStates = append(fleetStates, state)
		}
		nodeStates := make([]NodeState, 0, len(match.Nodes))
		for _, node := range match.Nodes {
			samples, ok := byStation[node.StationID]
			if !ok || turn-1 >= len(samples) {
				return Result{}, fmt.Errorf("missing tide samples for station %s", node.StationID)
			}
			tide := samples[turn-1].HeightM
			nodeStates = append(nodeStates, NodeState{ID: node.ID, TideM: tide, EffectiveDepthM: node.BaseDepthM + tide, Owner: owners[node.ID]})
			if owners[node.ID] != "" {
				scores[owners[node.ID]] += node.Value
			}
		}
		scoreRows := scoreRows(match.Players, scores)
		turns = append(turns, TurnResult{Turn: turn, UTC: byStation[match.Nodes[0].StationID][turn-1].UTC, Nodes: nodeStates, Fleets: fleetStates, ScoreDelta: scoreRows, Scores: scoreRows})
	}
	result := Result{SchemaVersion: 1, Game: "tidefront-v1", MatchID: match.MatchID, Turns: turns}
	result.Final = makeFinal(match, positions, owners, scores)
	Finalize(&result)
	return result, nil
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
	if len(final.Scores) > 0 {
		final.Winner = final.Scores[0].PlayerID
	}
	return final
}
