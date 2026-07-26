package plan

import (
	"bsplan/n2p"
	"bsplan/pkg/load"
)

func BuildScenario(g *load.Graph, sc load.Scenario, digestFn func([]string, []string, []string) string) Result {
	table := load.ReplaceTable(g)
	active := ActivePackages(g, sc.Tags)
	reachable := Reachable(g, active, sc.Roots, table)
	optional := load.OptionalMap(g)
	edges := load.EdgeMap(g)
	kept, dropped := n2p.PruneSelN2(reachable, optional, sc.Ceiling, sc.Roots, edges, table)
	droppedList := DropReasons(g, sc, kept, reachable, dropped)
	reachOK := ReachabilityOK(g, sc, kept, reachable, table)
	budgetOK := len(kept) <= sc.Ceiling
	return Result{
		Kept:        kept,
		Dropped:     dropped,
		ReachableOK: reachOK,
		BudgetOK:    budgetOK,
		BudgetUsed:  len(kept),
		PlanDigest:  digestFn(kept, droppedList, sc.Tags),
	}
}
