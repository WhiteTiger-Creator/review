package pipeline

import (
	"github.com/local/etaengine/frontprep"
	"github.com/local/etaengine/types"
)

func prepRows(rows []types.RouteRow, caps *types.FieldCaps, mode string) ([][]float32, []float32) {
	mat := make([][]float32, len(rows))
	for i, r := range rows {
		mat[i] = append([]float32(nil), r.Features...)
	}
	scales := frontprep.OpA2(mat, caps, mode)
	return frontprep.ApplyScale(mat, scales), scales
}
