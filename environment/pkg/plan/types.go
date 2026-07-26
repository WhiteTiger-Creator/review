package plan

type Result struct {
	Kept        []string
	Dropped     map[string]string
	ReachableOK bool
	BudgetOK    bool
	BudgetUsed  int
	PlanDigest  string
}
