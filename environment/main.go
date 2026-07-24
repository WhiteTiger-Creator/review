package main

import (
	"bufio"
	"fmt"
	"os"
	"sort"
	"strings"
)

type reqEdge struct {
	uver string
	dep  string
	ver  string
}

type capEdge struct {
	uver   string
	dep    string
	maxver string
}

type scenario struct {
	sid         string
	root        string
	reqs        map[string][]reqEdge
	caps        map[string][]capEdge
	index       map[string][]string
	lock        map[string]string
	queries     []string
	resetBefore bool
}

func newScenario() *scenario {
	return &scenario{
		reqs:  map[string][]reqEdge{},
		caps:  map[string][]capEdge{},
		index: map[string][]string{},
		lock:  map[string]string{},
	}
}

func uniqueSorted(xs []string) []string {
	seen := map[string]bool{}
	var out []string
	for _, x := range xs {
		if !seen[x] {
			seen[x] = true
			out = append(out, x)
		}
	}
	sort.Strings(out)
	return out
}

// readStream parses the whole of stdin into scenarios in order. A RESET line
// between scenarios marks the following scenario's resetBefore flag.
func readStream(r *bufio.Scanner) []*scenario {
	var scs []*scenario
	var sc *scenario
	active := false
	resetPending := false
	for r.Scan() {
		f := strings.Fields(r.Text())
		if len(f) == 0 {
			continue
		}
		switch f[0] {
		case "RESET":
			resetPending = true
		case "SCENARIO":
			sc = newScenario()
			if len(f) > 1 {
				sc.sid = f[1]
			}
			sc.resetBefore = resetPending
			resetPending = false
			active = true
		case "ROOT":
			if active && len(f) > 1 {
				sc.root = f[1]
			}
		case "REQ":
			if active && len(f) > 4 {
				sc.reqs[f[1]] = append(sc.reqs[f[1]], reqEdge{uver: f[2], dep: f[3], ver: f[4]})
			}
		case "CAP":
			if active && len(f) > 4 {
				sc.caps[f[1]] = append(sc.caps[f[1]], capEdge{uver: f[2], dep: f[3], maxver: f[4]})
			}
		case "INDEX":
			if active && len(f) > 2 {
				sc.index[f[1]] = append(sc.index[f[1]], f[2:]...)
			}
		case "LOCK":
			if active && len(f) > 2 {
				sc.lock[f[1]] = f[2]
			}
		case "QUERY":
			if active && len(f) > 1 {
				sc.queries = append(sc.queries, f[1])
			}
		case "ENDSCENARIO":
			if active {
				scs = append(scs, sc)
			}
			active = false
		}
	}
	return scs
}

func main() {
	in := bufio.NewScanner(os.Stdin)
	in.Buffer(make([]byte, 1024*1024), 1024*1024)
	out := bufio.NewWriter(os.Stdout)
	defer out.Flush()

	scs := readStream(in)
	sels := resolveStream(scs)
	for i, sc := range scs {
		var sel map[string]string
		if i < len(sels) {
			sel = sels[i]
		}
		for _, m := range uniqueSorted(sc.queries) {
			v, ok := sel[m]
			if !ok || v == "" {
				v = "NONE"
			}
			fmt.Fprintf(out, "%s|%s|%s\n", sc.sid, m, v)
		}
	}
}
