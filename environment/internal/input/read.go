package input

import (
	"os"

	"racklight/drainwave/internal/model"
)

func Load(inventoryPath, policyPath string) (model.Inventory, model.Policy, error, bool) {
	var inventory model.Inventory
	var policy model.Policy
	inventoryBytes, err := os.ReadFile(inventoryPath)
	if err != nil {
		return inventory, policy, err, true
	}
	policyBytes, err := os.ReadFile(policyPath)
	if err != nil {
		return inventory, policy, err, true
	}
	if err := decodeStrict(inventoryBytes, &inventory); err != nil {
		return inventory, policy, err, false
	}
	if err := decodeStrict(policyBytes, &policy); err != nil {
		return inventory, policy, err, false
	}
	if err := Validate(inventory, policy); err != nil {
		return inventory, policy, err, false
	}
	return inventory, policy, nil, false
}
