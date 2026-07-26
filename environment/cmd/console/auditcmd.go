package main

import (
	"fmt"

	"slate/internal/legacy"
	"slate/internal/manifest"
	"slate/internal/registry"
)

func cmdAudit(o *opts) int {
	if len(o.args) > 1 {
		return fail(exitUsage, "audit takes at most one project name")
	}
	idx, err := registry.Ingest(o.registryDir)
	if err != nil {
		return fail(exitInput, "%v", err)
	}
	if len(o.args) == 0 {
		packages, releases, yanked := idx.Counts()
		fmt.Printf("audit packages=%d releases=%d yanked=%d\n", packages, releases, yanked)
		return exitOK
	}
	m, err := manifest.Load(o.manifestsDir, o.args[0])
	if err != nil {
		return fail(exitInput, "%v", err)
	}
	roots := make([]string, 0, len(m.Requires))
	for _, req := range m.Requires {
		roots = append(roots, req.Name)
	}
	flat := legacy.FlatClosure(idx, roots)
	fmt.Printf("audit %s roots=%d flat_estimate=%d\n", m.Project, len(roots), len(flat))
	if o.flags["flat"] {
		for _, name := range flat {
			fmt.Printf("flat %s\n", name)
		}
	}
	return exitOK
}
