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
	sort.Slice(candidates, func(i, j int) bool { return candidates[i].ID < candidates[j].ID })
	if len(candidates) > 20 {
		return selection{}, fmt.Errorf("reachable optional edge count %d exceeds 20", len(candidates))
	}
	best := selection{}
	haveBest := false
	limit := 1 << len(candidates)
	for mask := 0; mask < limit; mask++ {
		selectedIDs := map[string]bool{}
		options := make([]candidateOption, 0, len(candidates))
		score := 0
		for index, option := range candidates {
			if mask&(1<<index) == 0 {
				continue
			}
			selectedIDs[option.ID] = true
			options = append(options, option)
			score += option.Priority
		}
		kept, err := builder.closure(selectedIDs)
		if err != nil {
			return selection{}, err
		}
		if len(kept) > ceiling {
			continue
		}
		valid := true
		for _, option := range options {
			if !kept[option.From] {
				valid = false
				break
			}
		}
		if !valid {
			continue
		}
		candidate := selection{kept: kept, options: options, score: score, budgetUsed: len(kept)}
		if !haveBest || better(candidate, best) {
			best = candidate
			haveBest = true
		}
	}
	if !haveBest {
		return selection{}, fmt.Errorf("no valid option selection")
	}
	return best, nil
}

func better(left, right selection) bool {
	if left.score != right.score {
		return left.score > right.score
	}
	if left.budgetUsed != right.budgetUsed {
		return left.budgetUsed > right.budgetUsed
	}
	leftIDs := optionIDs(left.options)
	rightIDs := optionIDs(right.options)
	for index := 0; index < len(leftIDs) && index < len(rightIDs); index++ {
		if leftIDs[index] != rightIDs[index] {
			return leftIDs[index] < rightIDs[index]
		}
	}
	return len(leftIDs) < len(rightIDs)
}

func optionIDs(options []candidateOption) []string {
	ids := make([]string, 0, len(options))
	for _, option := range options {
		ids = append(ids, option.ID)
	}
	sort.Strings(ids)
	return ids
}
