package main

import (
	"fmt"

	"slate/internal/registry"
)

func cmdVersions(o *opts) int {
	if len(o.args) != 1 {
		return fail(exitUsage, "versions takes one package name")
	}
	idx, err := registry.Ingest(o.registryDir)
	if err != nil {
		return fail(exitInput, "%v", err)
	}
	releases := idx.Releases(o.args[0])
	if releases == nil {
		return fail(exitInput, "no such package %q in %s", o.args[0], o.registryDir)
	}
	for _, rel := range releases {
		if rel.Yanked {
			fmt.Printf("%s yanked\n", rel.Version)
			continue
		}
		fmt.Println(rel.Version)
	}
	return exitOK
}
