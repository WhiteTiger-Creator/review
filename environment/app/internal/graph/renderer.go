package graph

import (
	"fmt"
	"sort"
	"strings"
)

func RenderDOT(report map[string]any) (string, error) {
	nodes, _ := report["nodes"].([]any)
	edges, _ := report["edges"].([]any)
	var b strings.Builder
	b.WriteString("digraph TokenExposure {\n")
	b.WriteString("  graph [rankdir=LR, compound=true];\n")
	b.WriteString("  node [shape=box];\n")
	clusters := map[string][]map[string]any{}
	for _, raw := range nodes {
		n, _ := raw.(map[string]any)
		tenant := str(n["tenant_id"])
		clusters[tenant] = append(clusters[tenant], n)
	}
	tenants := make([]string, 0, len(clusters))
	for t := range clusters {
		tenants = append(tenants, t)
	}
	sort.Strings(tenants)
	for _, tenant := range tenants {
		b.WriteString(fmt.Sprintf("  subgraph cluster_%s {\n", sanitize(tenant)))
		b.WriteString(fmt.Sprintf("    label=\"%s\";\n", escape(tenant)))
		for _, n := range clusters[tenant] {
			id := str(n["node_id"])
			label := escape(str(n["label"]))
			class := escape(str(n["class"]))
			b.WriteString(fmt.Sprintf("    %s [label=\"%s\", class=\"%s\"];\n", id, label, class))
		}
		b.WriteString("  }\n")
	}
	sortedEdges := make([]map[string]any, 0, len(edges))
	for _, raw := range edges {
		e, _ := raw.(map[string]any)
		sortedEdges = append(sortedEdges, e)
	}
	sort.Slice(sortedEdges, func(i, j int) bool {
		return str(sortedEdges[i]["edge_id"]) < str(sortedEdges[j]["edge_id"])
	})
	for _, e := range sortedEdges {
		b.WriteString(fmt.Sprintf("  %s -> %s [label=\"%s\", class=\"%s\"];\n",
		str(e["source"]), str(e["target"]), escape(str(e["label"])), escape(str(e["class"]))))
	}
	b.WriteString("}\n")
	return b.String(), nil
}

func str(v any) string {
	if v == nil {
		return ""
	}
	return fmt.Sprintf("%v", v)
}
