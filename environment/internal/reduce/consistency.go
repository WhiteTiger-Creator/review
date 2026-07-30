package reduce

func DedupeFindings(findings []map[string]any) []map[string]any {
	seen := map[string]bool{}
	out := make([]map[string]any, 0, len(findings))
	for _, f := range findings {
		id, _ := f["finding_id"].(string)
		if id == "" || seen[id] {
			continue
		}
		seen[id] = true
		out = append(out, f)
	}
	return out
}
