package cli

import (
	"beaconaudit/internal/config"
	"beaconaudit/internal/model"
)

func loadCase(path string) (model.Case, error) {
	var item model.Case
	if err := config.Load(path, &item); err != nil {
		return item, err
	}
	if err := config.ValidateCase(item); err != nil {
		return item, err
	}
	return item, nil
}
