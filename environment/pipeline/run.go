package pipeline

import (
	"github.com/local/etaengine/frontprep"
	"github.com/local/etaengine/kernels/onnx_subset"
	"github.com/local/etaengine/model"
	"github.com/local/etaengine/types"
)

type Engine struct {
	Manifest *model.Manifest
	Weights  onnx_subset.Weights
	Settings types.InferSettings
}

func NewEngine(m *model.Manifest, w onnx_subset.Weights, s types.InferSettings) *Engine {
	return &Engine{Manifest: m, Weights: w, Settings: s}
}

func mixHeadLane(pred, lane float32, s types.InferSettings) float32 {
	gw := s.GraphWeight
	lw := s.LaneWeight
	if gw == 0 && lw == 0 {
		gw, lw = 0.005, 0.995
	}
	return pred*gw + lane*lw
}

func (e *Engine) ScoreBatch(rows []types.RouteRow) []float32 {
	caps := model.CapsFromManifest(e.Manifest)
	mat := make([][]float32, len(rows))
	for i, r := range rows {
		mat[i] = append([]float32(nil), r.Features...)
	}
	mode := e.Settings.ScaleMode
	if mode == "" {
		mode = "peak"
	}
	scales := frontprep.OpA2(mat, &caps, mode)
	scaled := frontprep.ApplyScale(mat, scales)
	scores := make([]float32, len(rows))
	for i, row := range scaled {
		pred := onnx_subset.Forward(e.Weights, row)
		lane := foldRow(row, caps.SparseSlots)
		mix := mixHeadLane(pred, lane, e.Settings)
		gateScale := scales[0]
		if gateScale == 0 && len(scales) > 1 {
			gateScale = scales[1]
		}
		mix = limitRow(mix, gateScale, len(row))
		scores[i] = mix
	}
	return scores
}
