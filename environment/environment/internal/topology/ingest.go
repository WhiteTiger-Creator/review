package topology

import (
	"encoding/xml"
	"fmt"
	"os"
	"sort"
	"strings"

	"migrator/internal/contracts"
)

type Node struct {
	ID         string
	Name       string
	Alias      string
	Deployable bool
	Retired    bool
}

type Edge struct {
	ID          string
	Source      string
	Target      string
	Environment string
	Method      string
	Path        string
	AuthzScope  string
	Denied      bool
}

type Graph struct {
	Nodes []Node
	Edges []Edge
}

func EdgeKey(e Edge) string {
	return fmt.Sprintf("%s|%s|%s|%s|%s|%s|%s", e.ID, e.Source, e.Target, e.Environment, e.Method, e.Path, e.AuthzScope)
}

type graphML struct {
	XMLName xml.Name `xml:"graphml"`
	Keys    []struct {
		ID       string `xml:"id,attr"`
		AttrName string `xml:"attr.name,attr"`
	} `xml:"key"`
	Graph struct {
		EdgeDefault string `xml:"edgedefault,attr"`
		Nodes       []struct {
			ID   string `xml:"id,attr"`
			Data []struct {
				Key   string `xml:"key,attr"`
				Value string `xml:",chardata"`
			} `xml:"data"`
		} `xml:"node"`
		Edges []struct {
			ID       string `xml:"id,attr"`
			Source   string `xml:"source,attr"`
			Target   string `xml:"target,attr"`
			Directed *bool  `xml:"directed,attr"`
			Data     []struct {
				Key   string `xml:"key,attr"`
				Value string `xml:",chardata"`
			} `xml:"data"`
		} `xml:"edge"`
	} `xml:"graph"`
}

func Load(path string, c *contracts.Contracts) (*Graph, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var doc graphML
	if err := xml.Unmarshal(raw, &doc); err != nil {
		return nil, err
	}

	graphDirected := !strings.EqualFold(doc.Graph.EdgeDefault, "undirected")
	nodes := make([]Node, 0, len(doc.Graph.Nodes))
	for _, rawNode := range doc.Graph.Nodes {
		node := Node{ID: rawNode.ID, Deployable: true, Name: rawNode.ID}
		for _, data := range rawNode.Data {
			attrName := data.Key
			applyNodeAttr(&node, attrName, strings.TrimSpace(data.Value))
		}
		if node.Name == "" {
			node.Name = node.ID
		}
		nodes = append(nodes, node)
	}

	edges := make([]Edge, 0, len(doc.Graph.Edges))
	for _, rawEdge := range doc.Graph.Edges {
		edge := Edge{ID: rawEdge.ID, Source: rawEdge.Source, Target: rawEdge.Target}
		for _, data := range rawEdge.Data {
			attrName := data.Key
			applyEdgeAttr(&edge, attrName, strings.TrimSpace(data.Value))
		}
		dir := graphDirected
		if rawEdge.Directed != nil {
			dir = *rawEdge.Directed
		}
		src, tgt := edge.Source, edge.Target
		if !dir && src > tgt {
			src, tgt = tgt, src
		}
		edge.Source, edge.Target = src, tgt
		if edge.Environment == "" {
			edge.Environment = "production"
		}
		if edge.Method == "" {
			edge.Method = "GET"
		}
		if edge.Path == "" {
			edge.Path = "/"
		}
		if edge.AuthzScope == "" {
			edge.AuthzScope = "default"
		}
		edges = append(edges, edge)
	}

	aliases := c.Aliases
	nodeByID := make(map[string]Node, len(nodes))
	for _, n := range nodes {
		n.Name = canonicalName(n.Name, aliases)
		if n.Alias != "" {
			n.Alias = canonicalName(n.Alias, aliases)
		}
		nodeByID[n.ID] = n
	}

	outEdges := make([]Edge, 0, len(edges))
	seen := map[string]struct{}{}
	for _, edge := range edges {
		srcNode, ok1 := nodeByID[edge.Source]
		tgtNode, ok2 := nodeByID[edge.Target]
		if !ok1 || !ok2 {
			continue
		}
		if srcNode.Retired || tgtNode.Retired || !srcNode.Deployable || !tgtNode.Deployable {
			continue
		}
		src := canonicalName(srcNode.Name, aliases)
		tgt := canonicalName(tgtNode.Name, aliases)
		collapseKey := src + "|" + tgt
		if _, dup := seen[collapseKey]; dup {
			continue
		}
		seen[collapseKey] = struct{}{}
		edge.Source = src
		edge.Target = tgt
		outEdges = append(outEdges, edge)
	}

	sort.Slice(outEdges, func(i, j int) bool {
		a, b := outEdges[i], outEdges[j]
		if a.Source != b.Source {
			return a.Source < b.Source
		}
		if a.Target != b.Target {
			return a.Target < b.Target
		}
		if a.Environment != b.Environment {
			return a.Environment < b.Environment
		}
		if a.Method != b.Method {
			return a.Method < b.Method
		}
		if a.Path != b.Path {
			return a.Path < b.Path
		}
		if a.AuthzScope != b.AuthzScope {
			return a.AuthzScope < b.AuthzScope
		}
		return a.ID < b.ID
	})
	sort.Slice(nodes, func(i, j int) bool { return nodes[i].ID < nodes[j].ID })
	return &Graph{Nodes: nodes, Edges: outEdges}, nil
}

func canonicalName(name string, aliases map[string]string) string {
	name = strings.TrimSpace(strings.ToLower(name))
	if c, ok := aliases[name]; ok {
		return c
	}
	return name
}

func applyNodeAttr(node *Node, attr, val string) {
	switch attr {
	case "name":
		node.Name = val
	case "alias":
		node.Alias = val
	case "deployable":
		node.Deployable = strings.EqualFold(val, "true")
	case "retired":
		node.Retired = strings.EqualFold(val, "true")
	}
}

func applyEdgeAttr(edge *Edge, attr, val string) {
	switch attr {
	case "environment":
		edge.Environment = val
	case "method":
		edge.Method = strings.ToUpper(val)
	case "path":
		edge.Path = val
	case "authz_scope":
		edge.AuthzScope = val
	case "denied":
		edge.Denied = strings.EqualFold(val, "true")
	}
}
