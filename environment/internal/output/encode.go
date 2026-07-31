package output

import (
	"encoding/json"

	"racklight/drainwave/internal/model"
)

func Encode(report model.Report) ([]byte, error) {
	data, err := json.Marshal(report)
	if err != nil {
		return nil, err
	}
	return append(data, '\n'), nil
}
