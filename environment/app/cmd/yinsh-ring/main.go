package main

import (
	"flag"
	"fmt"
	"os"

	"yinshring/internal/season"
	"yinshring/internal/victory"
	"yinshring/internal/board"
	"yinshring/internal/scoring"
	"yinshring/internal/slide"
)

func main() {
	scenariosDir := flag.String("scenarios", "/app/scenarios", "championship scenario directory")
	configDir := flag.String("config", "/app/config", "rules config directory")
	outDir := flag.String("out", "/app/output", "report output directory")
	flag.Parse()

	cfg, err := season.LoadRules(*configDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "config: %v\n", err)
		os.Exit(1)
	}
	scenarios, err := board.LoadScenarios(*scenariosDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "scenarios: %v\n", err)
		os.Exit(1)
	}

	var matches []scoring.MatchRow
	for _, sc := range scenarios {
		res := slide.ApplyMoves(sc, cfg)
		out := victory.Decide(
			res.RingsRemovedA, res.RingsRemovedB,
			res.FlipsA, res.FlipsB,
			res.RowsClearedA, res.RowsClearedB,
			len(res.RingsA), len(res.RingsB),
			cfg,
		)
		matches = append(matches, scoring.BuildMatch(sc.MatchID, sc.PlayerA, sc.PlayerB, out, cfg))
	}

	if err := scoring.WriteReport(*outDir, cfg, matches); err != nil {
		fmt.Fprintf(os.Stderr, "report: %v\n", err)
		os.Exit(1)
	}
}
