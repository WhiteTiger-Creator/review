package registry

import "sort"

// Index is the ingested registry: every package file keyed by package name,
// each with its releases already sorted newest first.
type Index struct {
	packages map[string]*Package
	dir      string
}

// Dir reports the directory this index was ingested from.
func (i *Index) Dir() string { return i.dir }

// Names lists every package name in ascending order.
func (i *Index) Names() []string {
	names := make([]string, 0, len(i.packages))
	for name := range i.packages {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

// Package returns the package metadata, or nil when the registry has no such
// package.
func (i *Index) Package(name string) *Package { return i.packages[name] }

// Releases returns the releases of a package newest first. The slice is the
// index's own storage: callers must not reorder it.
func (i *Index) Releases(name string) []Release {
	pkg := i.packages[name]
	if pkg == nil {
		return nil
	}
	return pkg.Releases
}

// Release returns one exact version of a package, or nil when absent.
func (i *Index) Release(name, version string) *Release {
	pkg := i.packages[name]
	if pkg == nil {
		return nil
	}
	for k := range pkg.Releases {
		if pkg.Releases[k].Version == version {
			return &pkg.Releases[k]
		}
	}
	return nil
}

// Counts reports how many packages, releases and yanked releases the index
// holds.
func (i *Index) Counts() (packages, releases, yanked int) {
	packages = len(i.packages)
	for _, pkg := range i.packages {
		for _, rel := range pkg.Releases {
			releases++
			if rel.Yanked {
				yanked++
			}
		}
	}
	return packages, releases, yanked
}
