package graph

import (
	"fmt"
	"strings"
)

func ValidateConsistency(report map[string]any, dot string) error {
	nodes, _ := report["nodes"].([]any)
	edges, _ := report["edges"].([]any)
	for _, raw := range nodes {
		n, _ := raw.(map[string]any)
		id := fmt.Sprintf("%v", n["node_id"])
		if !strings.Contains(dot, id) {
			return fmt.Errorf("dot missing node %s", id)
		}
	}
	for _, raw := range edges {
		e, _ := raw.(map[string]any)
		src := fmt.Sprintf("%v", e["source"])
		dst := fmt.Sprintf("%v", e["target"])
		if !strings.Contains(dot, src+" -> "+dst) {
			return fmt.Errorf("dot missing edge %s -> %s", src, dst)
		}
	}
	return nil
}
