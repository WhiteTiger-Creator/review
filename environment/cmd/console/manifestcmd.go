package main

import (
	"fmt"
	"os"

	"slate/internal/canon"
	"slate/internal/exportstage"
	"slate/internal/manifest"
)

func cmdManifest(o *opts) int {
	if len(o.args) != 1 {
		return fail(exitUsage, "manifest takes one project name")
	}
	m, err := manifest.Load(o.manifestsDir, o.args[0])
	if err != nil {
		return fail(exitInput, "%v", err)
	}
	if o.flags["export"] {
		path, err := exportstage.WriteManifest(o.outDir, m)
		if err != nil {
			return fail(exitInput, "%v", err)
		}
		fmt.Printf("exported %s\n", path)
		return exitOK
	}
	data, err := canon.Marshal(exportstage.Doc(m))
	if err != nil {
		return fail(exitInput, "%v", err)
	}
	os.Stdout.Write(data)
	return exitOK
}
