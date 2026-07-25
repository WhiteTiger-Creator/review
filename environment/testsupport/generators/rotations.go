package generators

import "github.com/local/etaengine/types"

func RotUnit(rows []types.RouteRow, seed uint64) []types.RouteRow {
	out := make([]types.RouteRow, len(rows))
	factor := 1.0 + float32((seed%17)+1)*0.01
	for i, r := range rows {
		nr := types.RouteRow{ID: r.ID, Observed: r.Observed}
		nr.Features = make([]float32, len(r.Features))
		for j, v := range r.Features {
			nr.Features[j] = v * factor
		}
		out[i] = nr
	}
	return out
}

func RotOrder(rows []types.RouteRow, seed uint64) []types.RouteRow {
	out := make([]types.RouteRow, len(rows))
	shift := int(seed % uint64(len(rows[0].Features)))
	if shift == 0 {
		shift = 1
	}
	for i, r := range rows {
		nr := types.RouteRow{ID: r.ID, Observed: r.Observed}
		n := len(r.Features)
		nr.Features = make([]float32, n)
		for j := 0; j < n; j++ {
			nr.Features[j] = r.Features[(j+shift)%n]
		}
		out[i] = nr
	}
	return out
}

func RotPad(rows []types.RouteRow, seed uint64) []types.RouteRow {
	out := make([]types.RouteRow, len(rows))
	extra := 1 + int(seed%3)
	for i, r := range rows {
		nr := types.RouteRow{ID: r.ID, Observed: r.Observed}
		nr.Features = append(append([]float32(nil), r.Features...), make([]float32, extra)...)
		out[i] = nr
	}
	return out
}
