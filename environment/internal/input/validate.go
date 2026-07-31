package input

import "racklight/drainwave/internal/model"

func Validate(inventory model.Inventory, policy model.Policy) error {
	nodes, err := validateInventory(inventory)
	if err != nil {
		return err
	}
	return validatePolicy(policy, nodes)
}
