package planner

import (
	"sort"

	"racklight/drainwave/internal/model"
)

type context struct {
	targets      []string
	nodes        map[string]model.Node
	predecessors []uint16
	serviceTotal map[string]int
	policy       model.Policy
}

func newContext(inventory model.Inventory, policy model.Policy) context {
	nodes := make(map[string]model.Node, len(inventory.Nodes))
	serviceTotal := map[string]int{}
	for _, node := range inventory.Nodes {
		nodes[node.ID] = node
		for _, service := range node.Services {
			serviceTotal[service]++
		}
	}
	targets := append([]string(nil), policy.Targets...)
	sort.Strings(targets)
	positions := map[string]int{}
	for index, id := range targets {
		positions[id] = index
	}
	predecessors := make([]uint16, len(targets))
	for _, edge := range policy.Precedence {
		predecessors[positions[edge[1]]] |= uint16(1) << positions[edge[0]]
	}
	return context{targets: targets, nodes: nodes, predecessors: predecessors, serviceTotal: serviceTotal, policy: policy}
}
