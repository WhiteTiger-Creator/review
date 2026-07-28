package exposure

import (
	"os"
	"path/filepath"
	"sort"
	"strings"

	"trustremediator/internal/attest"
	"trustremediator/internal/authority"
	"trustremediator/internal/pki"
	"trustremediator/internal/provenance"
	"trustremediator/internal/truststore"
)

type Subject struct {
	Incident    string
	Name        string
	Disposition string
}

func Load(dataDir string) []Subject {
	raw, err := os.ReadFile(filepath.Join(dataDir, "exposure.tsv"))
	if err != nil {
		panic(err)
	}
	var subs []Subject
	for i, line := range strings.Split(strings.TrimRight(string(raw), "\n"), "\n") {
		if i == 0 {
			continue
		}
		cols := strings.Split(line, "\t")
		if len(cols) != 3 {
			panic("bad exposure row: " + line)
		}
		subs = append(subs, Subject{Incident: cols[0], Name: cols[1], Disposition: cols[2]})
	}
	return subs
}

// Select returns the smallest containment set, and among the smallest the one
// that comes first in common-name order.
func Select(dataDir string, eff attest.Distrust) []string {
	subs := Load(dataDir)
	paths := pki.AnchoredPaths(dataDir)

	post, _, err := truststore.Load(dataDir)
	if err != nil {
		panic(err)
	}
	standing := authority.Set(dataDir, post.ByName)
	for _, n := range eff.ByName {
		standing[n] = true
	}

	// A path only needs cutting, and only counts as a survivor, while it is live.
	live := map[string][][]string{}
	for _, s := range subs {
		for _, p := range paths[s.Name] {
			if !p.Sound {
				continue
			}
			tainted := false
			for _, m := range p.Members {
				if standing[m] {
					tainted = true
					break
				}
			}
			if !tainted {
				live[s.Name] = append(live[s.Name], p.Members)
			}
		}
	}

	var contain, preserve []string
	compromised := map[string]bool{}
	for _, cn := range provenance.CompromisedLeaves(dataDir) {
		compromised[cn] = true
	}
	for _, s := range subs {
		switch s.Disposition {
		case "contain":
			contain = append(contain, s.Name)
		case "preserve":
			if !compromised[s.Name] {
				preserve = append(preserve, s.Name)
			}
		}
	}
	for cn := range compromised {
		contain = append(contain, cn)
	}
	sort.Strings(contain)
	contain = dedupeSorted(contain)

	for _, name := range contain {
		if _, ok := live[name]; ok {
			continue
		}
		for _, p := range paths[name] {
			if !p.Sound {
				continue
			}
			tainted := false
			for _, m := range p.Members {
				if standing[m] {
					tainted = true
					break
				}
			}
			if !tainted {
				live[name] = append(live[name], p.Members)
			}
		}
	}

	candidates := authority.Names(dataDir)

	feasible := func(set []string) bool {
		cut := map[string]bool{}
		for _, s := range set {
			cut[s] = true
		}
		for _, name := range contain {
			for _, p := range live[name] {
				if !hits(cut, p) {
					return false
				}
			}
		}
		for _, name := range preserve {
			survived := false
			for _, p := range live[name] {
				if !hits(cut, p) {
					survived = true
					break
				}
			}
			if !survived {
				return false
			}
		}
		return true
	}

	// Smallest first, and within a size the first combination in name order,
	// which is what makes the answer unique.
	for size := 0; size <= len(candidates); size++ {
		var found []string
		combinations(candidates, size, func(set []string) bool {
			if feasible(set) {
				found = append([]string{}, set...)
				return true
			}
			return false
		})
		if found != nil {
			return found
		}
	}
	panic("no containment set satisfies the incident")
}

func hits(set map[string]bool, path []string) bool {
	for _, m := range path {
		if set[m] {
			return true
		}
	}
	return false
}

// combinations walks size-sized subsets in ascending index order, so the first
// one accepted by stop is the first in name order.
func combinations(items []string, size int, stop func([]string) bool) {
	cur := make([]string, size)
	var rec func(start, depth int) bool
	rec = func(start, depth int) bool {
		if depth == size {
			return stop(cur)
		}
		for i := start; i <= len(items)-(size-depth); i++ {
			cur[depth] = items[i]
			if rec(i+1, depth+1) {
				return true
			}
		}
		return false
	}
	rec(0, 0)
}

func dedupeSorted(items []string) []string {
	if len(items) == 0 {
		return items
	}
	sort.Strings(items)
	out := []string{items[0]}
	for _, it := range items[1:] {
		if it != out[len(out)-1] {
			out = append(out, it)
		}
	}
	return out
}
