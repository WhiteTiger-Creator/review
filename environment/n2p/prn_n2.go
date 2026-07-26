package n2p

import "sort"

func PruneSelN2(reachable []string, optional map[string]bool, ceiling int, roots []string, edges map[string][]string, table map[string]string) ([]string, map[string]string) {
	sort.Strings(reachable)
	dropped := map[string]string{}
	out := append([]string{}, reachable...)
	if len(out) > ceiling {
		for _, pkg := range reachable {
			if optional[pkg] {
				dropped[pkg] = "budget_trim"
				out = remove(out, pkg)
			}
		}
	}
	sort.Strings(out)
	return out, dropped
}

func remove(items []string, target string) []string {
	out := make([]string, 0, len(items))
	for _, item := range items {
		if item != target {
			out = append(out, item)
		}
	}
	return out
}
