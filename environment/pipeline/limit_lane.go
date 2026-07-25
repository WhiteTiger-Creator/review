package pipeline

import "github.com/local/etaengine/scoring"

func limitRow(mix float32, scale float32, span int) float32 {
	lim := scoring.LimitFromScale(scale)
	return scoring.GateC1(mix, lim, span)
}
