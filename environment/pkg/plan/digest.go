package plan

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
	"strconv"
	"strings"
)

func ComputePlanDigest(value ScenarioPlan) string {
	lines := []string{
		"scenario_id=" + value.ScenarioID,
		"input_digest=" + value.InputDigest,
		"tags=" + strings.Join(value.Tags, "\x1f"),
		"roots=" + strings.Join(value.Roots, "\x1f"),
		"resolved_roots=" + strings.Join(value.ResolvedRoots, "\x1f"),
		"ceiling=" + strconv.Itoa(value.Ceiling),
		"kept=" + strings.Join(value.Kept, "\x1f"),
	}
	for _, path := range value.Dropped {
		lines = append(lines, "drop="+path+":"+value.DropReasons[path])
	}
	options := append([]SelectedOption{}, value.SelectedOptions...)
	sort.Slice(options, func(i, j int) bool {
		left := options[i].From + "->" + options[i].To
		right := options[j].From + "->" + options[j].To
		return left < right
	})
	for _, option := range options {
		lines = append(lines, fmt.Sprintf("option=%s->%s@%d", option.From, option.To, option.Priority))
	}
	lines = append(lines,
		"option_score="+strconv.Itoa(value.OptionScore),
		"budget_used="+strconv.Itoa(value.BudgetUsed),
		"roots_reachable="+strconv.FormatBool(value.RootsReachable),
		"within_budget="+strconv.FormatBool(value.WithinBudget),
	)
	hash := sha256.Sum256([]byte(strings.Join(lines, "\n")))
	return hex.EncodeToString(hash[:])
}
