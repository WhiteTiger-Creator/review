package game

import (
	"fmt"
	"math"

	"tidefront.local/game/internal/model"
)

type validatedMatch struct {
	players   map[string]Player
	nodes     map[string]Node
	fleets    map[string]Fleet
	adjacent  map[string]map[string]bool
	orders    map[int]map[string]Order
	stationID map[string]bool
}

func finite(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0)
}

func Validate(match Match, bundle model.Bundle) (*validatedMatch, error) {
	if match.SchemaVersion != 1 {
		return nil, fmt.Errorf("match schema_version must be 1")
	}
	if match.MatchID == "" || match.TurnCount <= 0 || match.TurnSeconds <= 0 {
		return nil, fmt.Errorf("invalid match header")
	}
	players := make(map[string]Player)
	for _, player := range match.Players {
		players[player.ID] = player
	}
	nodes := make(map[string]Node)
	for _, node := range match.Nodes {
		nodes[node.ID] = node
	}
	fleets := make(map[string]Fleet)
	for _, fleet := range match.Fleets {
		fleets[fleet.ID] = fleet
	}
	adjacent := make(map[string]map[string]bool)
	for _, edge := range match.Edges {
		if adjacent[edge.A] == nil {
			adjacent[edge.A] = make(map[string]bool)
		}
		if adjacent[edge.B] == nil {
			adjacent[edge.B] = make(map[string]bool)
		}
		adjacent[edge.A][edge.B] = true
		adjacent[edge.B][edge.A] = true
	}
	orders := make(map[int]map[string]Order)
	for _, order := range match.Orders {
		if orders[order.Turn] == nil {
			orders[order.Turn] = make(map[string]Order)
		}
		orders[order.Turn][order.FleetID] = order
	}
	stationID := make(map[string]bool)
	for _, station := range bundle.Stations {
		stationID[station.ID] = true
	}
	return &validatedMatch{players: players, nodes: nodes, fleets: fleets, adjacent: adjacent, orders: orders, stationID: stationID}, nil
}
