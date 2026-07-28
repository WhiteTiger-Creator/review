package config

import "tidefront.local/game/internal/model"

type Effective struct{ DatumM, Scale, PhaseOffsetDeg float64 }

func choose(station, region, global *float64, def float64) float64 {
	if station != nil {
		return *station
	}
	if region != nil {
		return *region
	}
	if global != nil {
		return *global
	}
	return def
}

func Resolve(bundle model.Bundle, station model.Station) Effective {
	var region model.Overrides
	if station.Region != "" && bundle.Regions != nil {
		region = bundle.Regions[station.Region]
	}
	return Effective{
		DatumM:         choose(station.Overrides.DatumM, region.DatumM, bundle.Global.DatumM, 0),
		Scale:          choose(station.Overrides.Scale, region.Scale, bundle.Global.Scale, 1),
		PhaseOffsetDeg: choose(station.Overrides.PhaseOffsetDeg, region.PhaseOffsetDeg, bundle.Global.PhaseOffsetDeg, 0),
	}
}
