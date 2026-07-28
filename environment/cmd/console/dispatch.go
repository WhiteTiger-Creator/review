package main

import (
	"fmt"
	"os"
	"sort"
	"strings"
)

// Exit codes shared by every subcommand.
const (
	exitOK      = 0
	exitUsage   = 2
	exitConflict = 3
	exitInput   = 4
)

// opts carries the parsed command line: directory overrides, boolean flags and
// the positional arguments left over.
type opts struct {
	registryDir  string
	manifestsDir string
	outDir       string
	flags        map[string]bool
	args         []string
}

var valueFlags = map[string]bool{"registry": true, "manifests": true, "out": true}

type command struct {
	name  string
	run   func(o *opts) int
	brief string
}

// commands is filled in init so the table's function values do not form a
// package-variable initialization cycle with fail/usage.
var commands []command

func init() {
	commands = []command{
		{"show", cmdShow, "print one package with its releases and edges"},
		{"versions", cmdVersions, "list the versions of a package, newest first"},
		{"manifest", cmdManifest, "print a parsed project manifest as JSON"},
		{"audit", cmdAudit, "report registry totals and the legacy closure estimate"},
		{"version", cmdVersion, "print the tool version and resolver constants"},
	}
}

func run(argv []string) int {
	o, err := parseArgs(argv)
	if err != nil {
		return fail(exitUsage, "%v", err)
	}
	if len(o.args) == 0 || o.flags["help"] {
		usage()
		if len(o.args) == 0 {
			return exitUsage
		}
		return exitOK
	}
	name := o.args[0]
	o.args = o.args[1:]
	for _, c := range commands {
		if c.name == name {
			return c.run(o)
		}
	}
	return fail(exitUsage, "unknown subcommand %q", name)
}

func parseArgs(argv []string) (*opts, error) {
	o := &opts{
		registryDir:  "/app/registry",
		manifestsDir: "/app/manifests",
		outDir:       "/app/out",
		flags:        map[string]bool{},
	}
	for i := 0; i < len(argv); i++ {
		arg := argv[i]
		if !strings.HasPrefix(arg, "--") {
			o.args = append(o.args, arg)
			continue
		}
		key := strings.TrimPrefix(arg, "--")
		value := ""
		hasValue := false
		if eq := strings.IndexByte(key, '='); eq >= 0 {
			key, value, hasValue = key[:eq], key[eq+1:], true
		}
		if valueFlags[key] {
			if !hasValue {
				if i+1 >= len(argv) {
					return nil, fmt.Errorf("--%s needs a directory", key)
				}
				i++
				value = argv[i]
			}
			switch key {
			case "registry":
				o.registryDir = value
			case "manifests":
				o.manifestsDir = value
			case "out":
				o.outDir = value
			}
			continue
		}
		if hasValue {
			return nil, fmt.Errorf("--%s does not take a value", key)
		}
		o.flags[key] = true
	}
	return o, nil
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage: slate <subcommand> [args] [--registry DIR] [--manifests DIR] [--out DIR]")
	names := make([]string, 0, len(commands))
	for _, c := range commands {
		names = append(names, fmt.Sprintf("  %-9s %s", c.name, c.brief))
	}
	sort.Strings(names)
	for _, line := range names {
		fmt.Fprintln(os.Stderr, line)
	}
}

// fail prints the one-line slate: error. A command-line mistake (exit 2) also
// gets the usage block, since the caller needs to see the subcommand list; a
// resolution or input failure does not.
func fail(code int, format string, args ...interface{}) int {
	fmt.Fprintf(os.Stderr, "slate: "+format+"\n", args...)
	if code == exitUsage {
		usage()
	}
	return code
}
