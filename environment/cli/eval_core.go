package cli

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/local/etaengine/kernels/onnx_subset"
	"github.com/local/etaengine/model"
	"github.com/local/etaengine/pipeline"
	"github.com/local/etaengine/report"
	"github.com/local/etaengine/scoring"
	"github.com/local/etaengine/testsupport/generators"
	"github.com/local/etaengine/types"
)

func runEval(root, fixture, family string, seed uint64, settings types.InferSettings, gen uint64, modelID string) (types.OutDoc, error) {
	m, err := model.LoadManifest(filepath.Join(root, "assets", "manifest.json"))
	if err != nil {
		return types.OutDoc{}, err
	}
	rows, err := loadRows(filepath.Join(root, "testsupport", "fixtures", fixture+".json"))
	if err != nil {
		return types.OutDoc{}, err
	}
	switch family {
	case "unit":
		rows = generators.RotUnit(rows, seed)
	case "order":
		rows = generators.RotOrder(rows, seed)
	case "pad":
		rows = generators.RotPad(rows, seed)
	}
	w := loadWeights(filepath.Join(root, "assets", "weights.json"))
	eng := pipeline.NewEngine(m, w, settings)
	scores := eng.ScoreBatch(rows)
	runs := make([]types.RunRec, len(rows))
	for i, r := range rows {
		pred := scores[i]
		runs[i] = types.RunRec{
			InstanceID: fmt.Sprintf("%s_%s_%d", fixture, family, i),
			Family:     family,
			Seed:       seed,
			Score:      pred,
			Observed:   r.Observed,
			Delta:      scoring.Residual(pred, r.Observed),
			Profile:    profileForFamily(family),
			Generation: gen,
		}
	}
	return report.BuildD0(runs, gen, modelID), nil
}

func writeDoc(path string, doc types.OutDoc) error {
	b, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, b, 0o644)
}

func loadRows(path string) ([]types.RouteRow, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var rows []types.RouteRow
	return rows, json.Unmarshal(b, &rows)
}

func loadWeights(path string) onnx_subset.Weights {
	b, err := os.ReadFile(path)
	if err != nil {
		return onnx_subset.Weights{W: []float32{0.1, 0.2, 0.15, 0.05, 0.11, 0.09, 0.07, 0.13}, B: []float32{0.02}}
	}
	var w onnx_subset.Weights
	_ = json.Unmarshal(b, &w)
	return w
}

func profileForFamily(f string) string {
	switch f {
	case "unit":
		return "alpha"
	case "order":
		return "beta"
	case "pad":
		return "gamma"
	default:
		return "base"
	}
}
