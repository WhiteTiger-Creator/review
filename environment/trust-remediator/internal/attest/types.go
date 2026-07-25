package attest

type Distrust struct {
	ByFP   []string
	ByName []string
}

type Verdict struct {
	Leaf            string
	Decision        string
	Reason          string
	SelectedPath    []string
	PathsConsidered int
	ConstraintDepth *int
	TaintedMembers  []string
}

type ProvEntry struct {
	CertFP       string
	ServiceID    string
	AccessMinute string
	JoinKey      string
	JoinStatus   string
}

func VerdictMap(v Verdict) map[string]interface{} {
	return map[string]interface{}{
		"constraint_violation_depth": v.ConstraintDepth,
		"decision":                   v.Decision,
		"leaf":                       v.Leaf,
		"paths_considered":           v.PathsConsidered,
		"reason":                     v.Reason,
		"selected_path":              v.SelectedPath,
		"tainted_members":            v.TaintedMembers,
	}
}

func ProvMap(p ProvEntry) map[string]interface{} {
	return map[string]interface{}{
		"access_minute": p.AccessMinute,
		"cert_fp":       p.CertFP,
		"join_key":      p.JoinKey,
		"join_status":   p.JoinStatus,
		"service_id":    p.ServiceID,
	}
}

func VerdictSlice(items []Verdict) []map[string]interface{} {
	out := make([]map[string]interface{}, len(items))
	for i, v := range items {
		out[i] = VerdictMap(v)
	}
	return out
}

func ProvSlice(items []ProvEntry) []map[string]interface{} {
	out := make([]map[string]interface{}, len(items))
	for i, p := range items {
		out[i] = ProvMap(p)
	}
	return out
}
