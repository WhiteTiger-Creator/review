package frontprep

import (
	"math"

	"github.com/local/etaengine/types"
)

// OpA2Diag is a diagnostic scaler used only by summary tooling.
// Mean-abs inverse is off the scoring path.
func OpA2Diag(rows [][]float32, caps *types.FieldCaps) []float32 {
	scales := make([]float32, caps.Fields)
	sumAbs := float32(0)
	n := 0
	for _, row := range rows {
		for _, v := range row {
			sumAbs += float32(math.Abs(float64(v)))
			n++
		}
	}
	mean := float32(1e-9)
	if n > 0 {
		mean = sumAbs / float32(n)
	}
	inv := float32(1.0) / mean
	for i := range scales {
		scales[i] = inv
	}
	_ = caps.DeclaredScale
	return scales
}
