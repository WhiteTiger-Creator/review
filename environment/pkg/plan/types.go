package plan

import "bsplan/pkg/load"

type SelectedOption struct {
	From     string `json:"from"`
	To       string `json:"to"`
	Priority int    `json:"priority"`
}

type ScenarioPlan struct {
	ScenarioID      string            `json:"scenario_id"`
	Tags            []string          `json:"tags"`
	Roots           []string          `json:"roots"`
	ResolvedRoots   []string          `json:"resolved_roots"`
	Ceiling         int               `json:"ceiling"`
	Kept            []string          `json:"kept"`
	Dropped         []string          `json:"dropped"`
	DropReasons     map[string]string `json:"drop_reasons"`
	SelectedOptions []SelectedOption  `json:"selected_options"`
	OptionScore     int               `json:"option_score"`
	BudgetUsed      int               `json:"budget_used"`
	RootsReachable  bool              `json:"roots_reachable"`
	WithinBudget    bool              `json:"within_budget"`
	InputDigest     string            `json:"input_digest"`
	PlanDigest      string            `json:"plan_digest"`
}

type candidateOption struct {
	ID       string
	From     string
	To       string
	Priority int
}

type graphView struct {
	byPath        map[string]load.Package
	active        map[string]bool
	retired       map[string]bool
	resolvedRoots []string
	options       []candidateOption
}

type selection struct {
	kept       map[string]bool
	options    []candidateOption
	score      int
	budgetUsed int
}
