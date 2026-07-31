package input

import (
	"errors"

	"racklight/drainwave/internal/model"
)

func validateInventory(inventory model.Inventory) (map[string]model.Node, error) {
	if len(inventory.Nodes) == 0 || len(inventory.Nodes) > 256 {
		return nil, errors.New("invalid inventory size")
	}
	nodes := make(map[string]model.Node, len(inventory.Nodes))
	for _, node := range inventory.Nodes {
		if node.ID == "" || node.Zone == "" || node.Rack == "" || node.Power <= 0 || node.Power > maxContractInteger || len(node.Services) == 0 || len(node.Services) > 32 {
			return nil, errors.New("invalid node")
		}
		if _, exists := nodes[node.ID]; exists {
			return nil, errors.New("duplicate node")
		}
		services := map[string]bool{}
		for _, service := range node.Services {
			if !addUnique(services, service) {
				return nil, errors.New("invalid service")
			}
		}
		nodes[node.ID] = node
	}
	return nodes, nil
}
