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
	if match.MatchID == "" || match.StartUTC == "" {
		return nil, fmt.Errorf("match_id and start_utc are required")
	}
	if match.TurnCount < 1 || match.TurnCount > 1000 {
		return nil, fmt.Errorf("turn_count must be between 1 and 1000")
	}
	if match.TurnSeconds < 1 || match.TurnSeconds > 86400 {
		return nil, fmt.Errorf("turn_seconds must be between 1 and 86400")
	}
	if len(match.Players) < 2 {
		return nil, fmt.Errorf("at least two players are required")
	}
	players := make(map[string]Player, len(match.Players))
	for _, player := range match.Players {
		if player.ID == "" || player.Initiative < 0 {
			return nil, fmt.Errorf("invalid player")
		}
		if _, exists := players[player.ID]; exists {
			return nil, fmt.Errorf("duplicate player id %s", player.ID)
		}
		players[player.ID] = player
	}
	stationID := make(map[string]bool, len(bundle.Stations))
	for _, station := range bundle.Stations {
		stationID[station.ID] = true
	}
	if len(match.Nodes) == 0 {
		return nil, fmt.Errorf("at least one node is required")
	}
	nodes := make(map[string]Node, len(match.Nodes))
	for _, node := range match.Nodes {
		if node.ID == "" || node.StationID == "" || !finite(node.BaseDepthM) || node.Value < 0 || node.Value > 1000000 {
			return nil, fmt.Errorf("invalid node")
		}
		if _, exists := nodes[node.ID]; exists {
			return nil, fmt.Errorf("duplicate node id %s", node.ID)
		}
		if !stationID[node.StationID] {
			return nil, fmt.Errorf("node %s references unknown station %s", node.ID, node.StationID)
		}
		if node.InitialOwner != "" {
			if _, ok := players[node.InitialOwner]; !ok {
				return nil, fmt.Errorf("node %s references unknown owner %s", node.ID, node.InitialOwner)
			}
		}
		nodes[node.ID] = node
	}
	adjacent := make(map[string]map[string]bool, len(nodes))
	for id := range nodes {
		adjacent[id] = make(map[string]bool)
	}
	seenEdges := make(map[string]bool)
	for _, edge := range match.Edges {
		if edge.A == edge.B {
			return nil, fmt.Errorf("self edge %s is invalid", edge.A)
		}
		if _, ok := nodes[edge.A]; !ok {
			return nil, fmt.Errorf("edge references unknown node %s", edge.A)
		}
		if _, ok := nodes[edge.B]; !ok {
			return nil, fmt.Errorf("edge references unknown node %s", edge.B)
		}
		a, b := edge.A, edge.B
		if b < a {
			a, b = b, a
		}
		key := a + "\x00" + b
		if seenEdges[key] {
			return nil, fmt.Errorf("duplicate undirected edge %s-%s", a, b)
		}
		seenEdges[key] = true
		adjacent[edge.A][edge.B] = true
		adjacent[edge.B][edge.A] = true
	}
	if len(match.Fleets) == 0 {
		return nil, fmt.Errorf("at least one fleet is required")
	}
	fleets := make(map[string]Fleet, len(match.Fleets))
	occupied := make(map[string]string)
	for _, fleet := range match.Fleets {
		if fleet.ID == "" || !finite(fleet.DraftM) || fleet.DraftM < 0 {
			return nil, fmt.Errorf("invalid fleet")
		}
		if _, exists := fleets[fleet.ID]; exists {
			return nil, fmt.Errorf("duplicate fleet id %s", fleet.ID)
		}
		if _, ok := players[fleet.PlayerID]; !ok {
			return nil, fmt.Errorf("fleet %s references unknown player %s", fleet.ID, fleet.PlayerID)
		}
		if _, ok := nodes[fleet.NodeID]; !ok {
			return nil, fmt.Errorf("fleet %s references unknown node %s", fleet.ID, fleet.NodeID)
		}
		if other, exists := occupied[fleet.NodeID]; exists {
			return nil, fmt.Errorf("fleets %s and %s share initial node %s", other, fleet.ID, fleet.NodeID)
		}
		occupied[fleet.NodeID] = fleet.ID
		fleets[fleet.ID] = fleet
	}
	orders := make(map[int]map[string]Order)
	for _, order := range match.Orders {
		if order.Turn < 1 || order.Turn > match.TurnCount {
			return nil, fmt.Errorf("order turn is outside the match")
		}
		if _, ok := fleets[order.FleetID]; !ok {
			return nil, fmt.Errorf("order references unknown fleet %s", order.FleetID)
		}
		if order.Kind != "hold" && order.Kind != "move" {
			return nil, fmt.Errorf("unknown order kind %s", order.Kind)
		}
		if order.Kind == "hold" && order.TargetNodeID != "" {
			return nil, fmt.Errorf("hold order cannot have target_node_id")
		}
		if order.Kind == "move" {
			if order.TargetNodeID == "" {
				return nil, fmt.Errorf("move order requires target_node_id")
			}
			if _, ok := nodes[order.TargetNodeID]; !ok {
				return nil, fmt.Errorf("move order references unknown target %s", order.TargetNodeID)
			}
		}
		if orders[order.Turn] == nil {
			orders[order.Turn] = make(map[string]Order)
		}
		if _, exists := orders[order.Turn][order.FleetID]; exists {
			return nil, fmt.Errorf("duplicate order for fleet %s on turn %d", order.FleetID, order.Turn)
		}
		orders[order.Turn][order.FleetID] = order
	}
	return &validatedMatch{players: players, nodes: nodes, fleets: fleets, adjacent: adjacent, orders: orders, stationID: stationID}, nil
}
