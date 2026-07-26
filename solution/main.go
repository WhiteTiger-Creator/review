package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"trustloom/internal/als"
	"trustloom/internal/data"
	"trustloom/internal/folds"
	"trustloom/internal/rank"
)

func main() {
	interactions := flag.String("interactions", "", "interactions csv")
	queries := flag.String("queries", "", "queries csv")
	holdout := flag.String("holdout", "", "holdout csv")
	outDir := flag.String("out", "", "output directory")
	flag.Parse()
	if *interactions == "" || *queries == "" || *holdout == "" || *outDir == "" {
		fmt.Fprintln(os.Stderr, "usage: trustloom --interactions --queries --holdout --out")
		os.Exit(1)
	}
	cat, err := data.LoadInteractions(*interactions)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	model := als.Fit(cat)
	q, err := data.LoadPairs(*queries)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	h, err := data.LoadHoldout(*holdout)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := os.MkdirAll(*outDir, 0o755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	type uf struct {
		ID      int       `json:"id"`
		Factors []float64 `json:"factors"`
	}
	usersOut := make([]uf, len(cat.Users))
	for i, id := range cat.Users {
		usersOut[i] = uf{ID: id, Factors: model.X[i]}
	}
	itemsOut := make([]uf, len(cat.Items))
	for i, id := range cat.Items {
		itemsOut[i] = uf{ID: id, Factors: model.Y[i]}
	}
	modelDoc := map[string]any{
		"algorithm":  "tl-als-conf-1",
		"factors":    als.Factors,
		"lambda":     als.Lambda,
		"alpha":      als.Alpha,
		"iterations": als.Iters,
		"users":      usersOut,
		"items":      itemsOut,
	}
	mustWrite(filepath.Join(*outDir, "model.json"), modelDoc)

	type sc struct {
		UserID int     `json:"user_id"`
		ItemID int     `json:"item_id"`
		Score  float64 `json:"score"`
	}
	scores := make([]sc, len(q))
	for i, p := range q {
		scores[i] = sc{UserID: p[0], ItemID: p[1], Score: model.Score(cat, p[0], p[1])}
	}
	mustWrite(filepath.Join(*outDir, "scores.json"), map[string]any{"scores": scores})

	met := rank.Evaluate(model, cat, h)
	mustWrite(filepath.Join(*outDir, "metrics.json"), map[string]any{
		"precision_at_k": met.PrecisionAtK,
		"map_at_k":       met.MAPAtK,
		"ndcg_at_k":      met.NDCGAtK,
		"k":              rank.K,
		"eligible_users": met.EligibleUsers,
	})

	mustWrite(filepath.Join(*outDir, "diagnostics.json"), map[string]any{
		"r_star":          model.RStar,
		"n_users":         len(cat.Users),
		"n_items":         len(cat.Items),
		"n_pairs":         cat.NPairs,
		"fade":            als.Fade,
		"lambda_schedule": model.Schedule,
		"mean_abs_score":  model.MeanAbsScore(cat),
	})

	foldRes := folds.Evaluate(cat)
	mustWrite(filepath.Join(*outDir, "folds.json"), map[string]any{
		"k":     folds.FoldK,
		"folds": foldRes,
	})
}

func mustWrite(path string, v any) {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	b = append(b, '\n')
	if err := os.WriteFile(path, b, 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
