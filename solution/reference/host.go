package main

import (
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

type record struct {
	addr  string
	iface string
}

type step struct {
	kind   string
	first  string
	second string
}

type host struct {
	name        string
	ifaceOrder  []string
	slot        map[string]string
	openUp      map[string]bool
	bondOrder   []string
	floor       map[string]int
	openRaised  map[string]bool
	declared    map[string][]string
	vlanOrder   []string
	parent      map[string]string
	tag         map[string]int
	vlanOpen    map[string]bool
	records     []record
	openClaimed map[record]bool
	steps       []step
	isIface     map[string]bool
	isBond      map[string]bool
}

func readRecords(path string, count int) [][]string {
	out := [][]string{}
	raw, err := os.ReadFile(path)
	if err != nil {
		return out
	}
	for _, text := range strings.Split(string(raw), "\n") {
		trimmed := strings.TrimSpace(text)
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}
		fields := strings.Split(trimmed, ":")
		for i := range fields {
			fields[i] = strings.TrimSpace(fields[i])
		}
		for len(fields) < count {
			fields = append(fields, "-")
		}
		out = append(out, fields[:count])
	}
	return out
}

func readSettings(path string) map[string]string {
	out := map[string]string{}
	raw, err := os.ReadFile(path)
	if err != nil {
		return out
	}
	for _, text := range strings.Split(string(raw), "\n") {
		trimmed := strings.TrimSpace(text)
		if trimmed == "" || strings.HasPrefix(trimmed, "#") {
			continue
		}
		name, value, found := strings.Cut(trimmed, "=")
		if !found {
			continue
		}
		out[strings.TrimSpace(name)] = strings.TrimSpace(value)
	}
	return out
}

func whole(text string) int {
	value, err := strconv.Atoi(text)
	if err != nil {
		return 0
	}
	return value
}

func loadHost(root string) *host {
	h := &host{
		slot:        map[string]string{},
		openUp:      map[string]bool{},
		floor:       map[string]int{},
		openRaised:  map[string]bool{},
		declared:    map[string][]string{},
		parent:      map[string]string{},
		tag:         map[string]int{},
		vlanOpen:    map[string]bool{},
		openClaimed: map[record]bool{},
		isIface:     map[string]bool{},
		isBond:      map[string]bool{},
	}
	h.name = readSettings(filepath.Join(root, "host.conf"))["host"]

	for _, fields := range readRecords(filepath.Join(root, "links", "interfaces.table"), 3) {
		h.ifaceOrder = append(h.ifaceOrder, fields[0])
		h.slot[fields[0]] = fields[1]
		h.openUp[fields[0]] = fields[2] == "up"
		h.isIface[fields[0]] = true
	}
	for _, fields := range readRecords(filepath.Join(root, "links", "bonds.table"), 3) {
		h.bondOrder = append(h.bondOrder, fields[0])
		h.floor[fields[0]] = whole(fields[1])
		h.openRaised[fields[0]] = fields[2] == "yes"
		h.isBond[fields[0]] = true
	}

	type placed struct {
		place  int
		member string
	}
	gathered := map[string][]placed{}
	for _, fields := range readRecords(filepath.Join(root, "links", "members.table"), 3) {
		gathered[fields[0]] = append(gathered[fields[0]], placed{whole(fields[2]), fields[1]})
	}
	for _, bond := range h.bondOrder {
		lines := gathered[bond]
		sort.SliceStable(lines, func(i, j int) bool { return lines[i].place < lines[j].place })
		members := []string{}
		for _, one := range lines {
			members = append(members, one.member)
		}
		h.declared[bond] = members
	}

	for _, fields := range readRecords(filepath.Join(root, "links", "vlans.table"), 4) {
		h.vlanOrder = append(h.vlanOrder, fields[0])
		h.parent[fields[0]] = fields[1]
		h.tag[fields[0]] = whole(fields[2])
		h.vlanOpen[fields[0]] = fields[3] == "yes"
	}
	for _, fields := range readRecords(filepath.Join(root, "links", "addresses.table"), 4) {
		one := record{fields[1], fields[2]}
		h.records = append(h.records, one)
		h.openClaimed[one] = fields[3] == "yes"
	}
	for _, fields := range readRecords(filepath.Join(root, "run", "link.log"), 4) {
		h.steps = append(h.steps, step{fields[1], fields[2], fields[3]})
	}
	return h
}
