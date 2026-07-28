package plan

import (
	"fmt"
	"sort"
	"strings"

	"bsplan/pkg/load"
	"bsplan/pkg/replace"
	"bsplan/pkg/tags"
)

func BuildScenario(graph *load.Graph, scenario load.Scenario, inputDigest string) (ScenarioPlan, error) {
	if strings.TrimSpace(scenario.ScenarioID) == "" {
		return ScenarioPlan{}, fmt.Errorf("scenario_id is empty")
	}
	if len(scenario.Roots) == 0 {
		return ScenarioPlan{}, fmt.Errorf("scenario %s has no roots", scenario.ScenarioID)
	}
	if scenario.Ceiling <= 0 {
		return ScenarioPlan{}, fmt.Errorf("scenario %s has non-positive ceiling", scenario.ScenarioID)
	}
	tagSet, err := tags.Parse(scenario.Tags)
	if err != nil {
		return ScenarioPlan{}, fmt.Errorf("scenario %s: %w", scenario.ScenarioID, err)
	}
	resolver, err := replace.New(graph.Replaces)
	if err != nil {
		return ScenarioPlan{}, err
	}
	view, err := makeView(graph, scenario, tagSet, resolver)
	if err != nil {
		return ScenarioPlan{}, err
	}
	builder := closureBuilder{view: view, resolver: resolver}
	mandatory, err := builder.closure(map[string]bool{})
	if err != nil {
		return ScenarioPlan{}, err
	}
	if len(mandatory) > scenario.Ceiling {
		return ScenarioPlan{}, fmt.Errorf("scenario %s mandatory closure uses %d packages above ceiling %d", scenario.ScenarioID, len(mandatory), scenario.Ceiling)
	}
	chosen, err := chooseOptions(builder, scenario.Ceiling)
	if err != nil {
		return ScenarioPlan{}, err
	}
	allSelected := map[string]bool{}
	for _, option := range view.options {
		allSelected[option.ID] = true
	}
	potential, err := builder.closure(allSelected)
	if err != nil {
		return ScenarioPlan{}, err
	}
	kept := sortedKeys(chosen.kept)
	dropped := make([]string, 0, len(view.byPath)-len(kept))
	reasons := map[string]string{}
	for path := range view.byPath {
		if chosen.kept[path] {
			continue
		}
		dropped = append(dropped, path)
		switch {
		case view.retired[path]:
			reasons[path] = "retired"
		case !view.active[path]:
			reasons[path] = "tag_excluded"
		case potential[path]:
			reasons[path] = "budget_trim"
		default:
			reasons[path] = "unreachable"
		}
	}
	sort.Strings(dropped)
	selected := make([]SelectedOption, 0, len(chosen.options))
	for _, option := range chosen.options {
		selected = append(selected, SelectedOption{From: option.From, To: option.To, Priority: option.Priority})
	}
	sort.Slice(selected, func(i, j int) bool {
		return selected[i].From+"->"+selected[i].To < selected[j].From+"->"+selected[j].To
	})
	plan := ScenarioPlan{
		ScenarioID:      scenario.ScenarioID,
		Tags:            append([]string{}, scenario.Tags...),
		Roots:           append([]string{}, scenario.Roots...),
		ResolvedRoots:   append([]string{}, view.resolvedRoots...),
		Ceiling:         scenario.Ceiling,
		Kept:            kept,
		Dropped:         dropped,
		DropReasons:     reasons,
		SelectedOptions: selected,
		OptionScore:     chosen.score,
		BudgetUsed:      len(kept),
		RootsReachable:  rootsReachable(view.resolvedRoots, chosen.kept),
		WithinBudget:    len(kept) <= scenario.Ceiling,
		InputDigest:     inputDigest,
	}
	plan.PlanDigest = ComputePlanDigest(plan)
	return plan, nil
}

func makeView(graph *load.Graph, scenario load.Scenario, tagSet tags.Set, resolver replace.Resolver) (graphView, error) {
	view := graphView{
		byPath:  map[string]load.Package{},
		active:  map[string]bool{},
		retired: map[string]bool{},
	}
	for _, path := range graph.Retired {
		view.retired[path] = true
	}
	for _, pkg := range graph.Packages {
		view.byPath[pkg.ImportPath] = pkg
		if view.retired[pkg.ImportPath] {
			continue
		}
		matched, err := tagSet.Matches(pkg.TagSets)
		if err != nil {
			return graphView{}, fmt.Errorf("package %s: %w", pkg.ImportPath, err)
		}
		if matched {
			view.active[pkg.ImportPath] = true
		}
	}
	for _, root := range scenario.Roots {
		resolved, err := resolver.Resolve(root)
		if err != nil {
			return graphView{}, err
		}
		if _, ok := view.byPath[resolved]; !ok {
			return graphView{}, fmt.Errorf("scenario %s root %q resolves to missing package %q", scenario.ScenarioID, root, resolved)
		}
		if !view.active[resolved] {
			return graphView{}, fmt.Errorf("scenario %s root %q resolves to inactive package %q", scenario.ScenarioID, root, resolved)
		}
		view.resolvedRoots = append(view.resolvedRoots, resolved)
	}
	sort.Strings(view.resolvedRoots)
	seenOptions := map[string]bool{}
	for _, pkg := range graph.Packages {
		if !view.active[pkg.ImportPath] {
			continue
		}
		for _, imp := range pkg.Imports {
			if strings.TrimSpace(imp.Path) == "" {
				return graphView{}, fmt.Errorf("package %s has empty import path", pkg.ImportPath)
			}
			if imp.Optional {
				if imp.Priority < 1 || imp.Priority > 1000 {
					return graphView{}, fmt.Errorf("optional import %s from %s has invalid priority", imp.Path, pkg.ImportPath)
				}
			} else if imp.Priority != 0 {
				return graphView{}, fmt.Errorf("required import %s from %s must have priority 0", imp.Path, pkg.ImportPath)
			}
			target, err := resolver.Resolve(imp.Path)
			if err != nil {
				return graphView{}, err
			}
			if _, ok := view.byPath[target]; !ok {
				return graphView{}, fmt.Errorf("package %s imports missing target %q", pkg.ImportPath, target)
			}
			if !imp.Optional || !view.active[target] {
				continue
			}
			id := pkg.ImportPath + "->" + target
			if seenOptions[id] {
				return graphView{}, fmt.Errorf("duplicate optional edge %q", id)
			}
			seenOptions[id] = true
			view.options = append(view.options, candidateOption{ID: id, From: pkg.ImportPath, To: target, Priority: imp.Priority})
		}
	}
	sort.Slice(view.options, func(i, j int) bool { return view.options[i].ID < view.options[j].ID })
	return view, nil
}

func rootsReachable(roots []string, kept map[string]bool) bool {
	for _, root := range roots {
		if !kept[root] {
			return false
		}
	}
	return true
}
