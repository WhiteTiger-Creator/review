package main

import (
	"fmt"

	"slate/internal/registry"
)

func cmdShow(o *opts) int {
	if len(o.args) != 1 {
		return fail(exitUsage, "show takes one package name")
	}
	idx, err := registry.Ingest(o.registryDir)
	if err != nil {
		return fail(exitInput, "%v", err)
	}
	name := o.args[0]
	pkg := idx.Package(name)
	if pkg == nil {
		return fail(exitInput, "no such package %q in %s", name, o.registryDir)
	}
	fmt.Printf("package %s releases=%d\n", pkg.Name, len(pkg.Releases))
	for _, rel := range pkg.Releases {
		fmt.Printf("release %s yanked=%t\n", rel.Version, rel.Yanked)
		for _, req := range rel.Requires {
			fmt.Printf("  requires %s %s\n", req.Name, req.Range)
		}
		for _, feat := range rel.FeatureNames() {
			for _, req := range rel.Features[feat] {
				fmt.Printf("  feature %s requires %s %s\n", feat, req.Name, req.Range)
			}
		}
	}
	return exitOK
}
