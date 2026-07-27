package main

import (
	"flag"
	"fmt"
	"os"

	"yinshring/internal/c3n"
	"yinshring/internal/d9g"
	"yinshring/internal/h7b"
	"yinshring/internal/q6p"
	"yinshring/internal/u2m"
)

func main() {
	scenariosDir := flag.String("scenarios", "/app/scenarios", "championship scenario directory")
	configDir := flag.String("config", "/app/config", "rules config directory")
	outDir := flag.String("out", "/app/output", "report output directory")
	flag.Parse()

	rules, err := c3n.LoadRules(*configDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "config: %v\n", err)
		os.Exit(1)
	}
	scenarios, err := h7b.LoadScenarios(*scenariosDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "scenarios: %v\n", err)
		os.Exit(1)
	}

	var matches []q6p.MatchRow
	for _, sc := range scenarios {
		res := u2m.ApplyMoves(sc, rules)
		out := d9g.Decide(
			res.RingsRemovedA, res.RingsRemovedB,
			res.FlipsA, res.FlipsB,
			res.RowsClearedA, res.RowsClearedB,
			len(res.RingsA), len(res.RingsB),
			rules,
		)
		matches = append(matches, q6p.BuildMatch(sc.MatchID, sc.PlayerA, sc.PlayerB, out, rules))
	}

	if err := q6p.WriteReport(*outDir, rules, matches); err != nil {
		fmt.Fprintf(os.Stderr, "report: %v\n", err)
		os.Exit(1)
	}
}
