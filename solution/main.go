package main

import (
	"encoding/json"
	"flag"
	"net"
	"os"
	"sort"
)

type Rule struct {
	ID       string `json:"id"`
	Position int    `json:"position"`
	Source   string `json:"source"`
	Port     int    `json:"port"`
	Verdict  string `json:"verdict"`
}
type Set struct {
	Policy string `json:"policy"`
	Rules  []Rule `json:"rules"`
}
type Probe struct {
	Source string `json:"source"`
	Port   int    `json:"port"`
	Must   string `json:"must"`
}
type Op struct {
	Op      string `json:"op"`
	ID      string `json:"id,omitempty"`
	Verdict string `json:"verdict,omitempty"`
}

func read(p string, v any) {
	b, e := os.ReadFile(p)
	if e != nil || json.Unmarshal(b, v) != nil {
		panic("input")
	}
}
func key(o Op) string {
	if o.Op == "policy" {
		return "policy:" + o.Verdict
	}
	return o.Op + ":" + o.ID
}
func match(cidr, ip string) bool { _, n, _ := net.ParseCIDR(cidr); return n.Contains(net.ParseIP(ip)) }
func main() {
	cp := flag.String("current", "/app/task_file/current.json", "")
	dp := flag.String("desired", "/app/task_file/desired.json", "")
	pp := flag.String("probes", "/app/task_file/probes.json", "")
	out := flag.String("output", "/app/out/plan.json", "")
	flag.Parse()
	var c, d Set
	var ps []Probe
	read(*cp, &c)
	read(*dp, &d)
	read(*pp, &ps)
	cm := map[string]Rule{}
	dm := map[string]Rule{}
	for _, r := range c.Rules {
		cm[r.ID] = r
	}
	for _, r := range d.Rules {
		dm[r.ID] = r
	}
	var ops []Op
	for id, r := range cm {
		q, ok := dm[id]
		if !ok {
			ops = append(ops, Op{Op: "delete", ID: id})
		} else {
			a, _ := json.Marshal(r)
			b, _ := json.Marshal(q)
			if string(a) != string(b) {
				ops = append(ops, Op{Op: "replace", ID: id})
			}
		}
	}
	for id := range dm {
		if _, ok := cm[id]; !ok {
			ops = append(ops, Op{Op: "add", ID: id})
		}
	}
	if c.Policy != d.Policy {
		ops = append(ops, Op{Op: "policy", Verdict: d.Policy})
	}
	sort.Slice(ops, func(i, j int) bool { return key(ops[i]) < key(ops[j]) })

	safe := func(s Set) bool {
		sort.Slice(s.Rules, func(i, j int) bool {
			if s.Rules[i].Position == s.Rules[j].Position {
				return s.Rules[i].ID < s.Rules[j].ID
			}
			return s.Rules[i].Position < s.Rules[j].Position
		})
		for _, p := range ps {
			v := s.Policy
			for _, r := range s.Rules {
				if (r.Port == 0 || r.Port == p.Port) && match(r.Source, p.Source) {
					v = r.Verdict
					break
				}
			}
			if v != p.Must {
				return false
			}
		}
		return true
	}
	apply := func(s Set, o Op) Set {
		r := append([]Rule{}, s.Rules...)
		if o.Op == "policy" {
			s.Policy = o.Verdict
			return s
		}
		for i := 0; i < len(r); i++ {
			if r[i].ID == o.ID {
				r = append(r[:i], r[i+1:]...)
				break
			}
		}
		if o.Op == "add" || o.Op == "replace" {
			r = append(r, dm[o.ID])
		}
		s.Rules = r
		return s
	}

	best := []Op{}
	n := len(ops)
	if n <= 20 && safe(c) {
		full := (uint32(1) << n) - 1
		states := make([]Set, uint32(1)<<n)
		built := make([]bool, uint32(1)<<n)
		safeMemo := make([]int8, uint32(1)<<n)
		states[0] = c
		built[0] = true

		var state func(uint32) Set
		state = func(mask uint32) Set {
			if built[mask] {
				return states[mask]
			}
			for i := 0; i < n; i++ {
				bit := uint32(1) << i
				if mask&bit != 0 {
					s := state(mask ^ bit)
					states[mask] = apply(s, ops[i])
					built[mask] = true
					return states[mask]
				}
			}
			panic("state")
		}
		isSafe := func(mask uint32) bool {
			if safeMemo[mask] == 0 {
				if safe(state(mask)) {
					safeMemo[mask] = 1
				} else {
					safeMemo[mask] = -1
				}
			}
			return safeMemo[mask] == 1
		}

		maxPeak := len(c.Rules)
		for _, o := range ops {
			if o.Op == "add" {
				maxPeak++
			}
		}
		for peak := len(c.Rules); peak <= maxPeak && len(best) == 0 && n != 0; peak++ {
			memo := make([]int8, uint32(1)<<n)
			var reachable func(uint32) bool
			reachable = func(mask uint32) bool {
				if mask == full {
					return true
				}
				if memo[mask] != 0 {
					return memo[mask] == 1
				}
				memo[mask] = -1
				for i := 0; i < n; i++ {
					bit := uint32(1) << i
					if mask&bit != 0 {
						continue
					}
					next := mask | bit
					if len(state(next).Rules) <= peak && isSafe(next) && reachable(next) {
						memo[mask] = 1
						return true
					}
				}
				return false
			}
			if !reachable(0) {
				continue
			}
			mask := uint32(0)
			for mask != full {
				for i, o := range ops {
					bit := uint32(1) << i
					if mask&bit != 0 {
						continue
					}
					next := mask | bit
					if len(state(next).Rules) <= peak && isSafe(next) && reachable(next) {
						best = append(best, o)
						mask = next
						break
					}
				}
			}
		}
	}
	os.MkdirAll(dir(*out), 0755)
	b, _ := json.Marshal(map[string]any{"operations": best})
	os.WriteFile(*out, append(b, '\n'), 0644)
}
func dir(s string) string {
	p := "."
	for i := len(s) - 1; i >= 0; i-- {
		if s[i] == '/' {
			p = s[:i]
			break
		}
	}
	return p
}
