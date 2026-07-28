package plan

import (
	"fmt"
	"sort"

	"bsplan/pkg/replace"
)

type closureBuilder struct {
	view     graphView
	resolver replace.Resolver
}

func (b closureBuilder) closure(selected map[string]bool) (map[string]bool, error) {
	kept := map[string]bool{}
	visiting := map[string]bool{}
	var walk func(string) error
	walk = func(path string) error {
		resolved, err := b.resolver.Resolve(path)
		if err != nil {
			return err
		}
		if !b.view.active[resolved] {
			return fmt.Errorf("required package %q is not active", resolved)
		}
		if kept[resolved] {
			return nil
		}
		if visiting[resolved] {
			return nil
		}
		pkg, ok := b.view.byPath[resolved]
		if !ok {
			return fmt.Errorf("missing package %q", resolved)
		}
		visiting[resolved] = true
		kept[resolved] = true
		for _, imp := range pkg.Imports {
			target, err := b.resolver.Resolve(imp.Path)
			if err != nil {
				return err
			}
			if _, exists := b.view.byPath[target]; !exists {
				return fmt.Errorf("package %q imports missing target %q", resolved, target)
			}
			if !b.view.active[target] {
				continue
			}
			if imp.Optional {
				id := resolved + "->" + target
				if !selected[id] {
					continue
				}
			}
			if err := walk(target); err != nil {
				return err
			}
		}
		visiting[resolved] = false
		return nil
	}
	for _, root := range b.view.resolvedRoots {
		if err := walk(root); err != nil {
			return nil, err
		}
	}
	return kept, nil
}

func sortedKeys(values map[string]bool) []string {
	out := make([]string, 0, len(values))
	for key, present := range values {
		if present {
			out = append(out, key)
		}
	}
	sort.Strings(out)
	return out
}
