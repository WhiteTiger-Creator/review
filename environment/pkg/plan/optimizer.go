package plan

import (
	"fmt"
	"sort"
)

func chooseOptions(builder closureBuilder, ceiling int) (selection, error) {
	all := map[string]bool{}
	for _, option := range builder.view.options {
		all[option.ID] = true
	}
	potential, err := builder.closure(all)
	if err != nil {
		return selection{}, err
	}
	candidates := make([]candidateOption, 0, len(builder.view.options))
	for _, option := range builder.view.options {
		if potential[option.From] && builder.view.active[option.To] {
			candidates = append(candidates, option)
		}
	}
	if len(candidates) > 20 {
		return selection{}, fmt.Errorf("reachable optional edge count %d exceeds 20", len(candidates))
	}
	sort.Slice(candidates, func(i, j int) bool {
		if candidates[i].Priority != candidates[j].Priority {
			return candidates[i].Priority > candidates[j].Priority
		}
		return candidates[i].ID < candidates[j].ID
	})
	selectedIDs := map[string]bool{}
	selectedOptions := []candidateOption{}
	for _, option := range candidates {
		trial := cloneSet(selectedIDs)
		trial[option.ID] = true
		kept, err := builder.closure(trial)
		if err != nil {
			return selection{}, err
		}
		if !kept[option.From] || len(kept) > ceiling {
			continue
		}
		selectedIDs = trial
		selectedOptions = append(selectedOptions, option)
	}
	kept, err := builder.closure(selectedIDs)
	if err != nil {
		return selection{}, err
	}
	score := 0
	for _, option := range selectedOptions {
		score += option.Priority
	}
	sort.Slice(selectedOptions, func(i, j int) bool { return selectedOptions[i].ID < selectedOptions[j].ID })
	return selection{kept: kept, options: selectedOptions, score: score, budgetUsed: len(kept)}, nil
}

func cloneSet(values map[string]bool) map[string]bool {
	out := make(map[string]bool, len(values)+1)
	for key, value := range values {
		out[key] = value
	}
	return out
}
