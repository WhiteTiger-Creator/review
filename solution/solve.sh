#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ -d /app/task_file ]; then
  APP_DIR=/app
else
  APP_DIR="$(cd "$SCRIPT_DIR/../environment/task_file" && pwd)"
fi

cat > "$APP_DIR/main.go" <<'GO'
package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
)

type Requirement struct {
	Name         string   `json:"name"`
	Min          *string  `json:"min"`
	MinInclusive bool     `json:"min_inclusive"`
	Max          *string  `json:"max"`
	MaxInclusive bool     `json:"max_inclusive"`
	Features     []string `json:"features"`
	AllowYanked  bool     `json:"allow_yanked"`
}

type Package struct {
	Name      string        `json:"name"`
	Version   string        `json:"version"`
	Platforms []string      `json:"platforms"`
	Hash      string        `json:"hash"`
	Yanked    bool          `json:"yanked"`
	Features  []string      `json:"features"`
	Deps      []Requirement `json:"deps"`
	Provides  []Provide     `json:"provides"`
	Conflicts []Requirement `json:"conflicts"`
}

type Provide struct {
	Name    string `json:"name"`
	Version string `json:"version"`
}

type Request struct {
	Platform string        `json:"platform"`
	Roots    []Requirement `json:"roots"`
}

type Registry struct {
	Packages []Package `json:"packages"`
}

type LockPackage struct {
	Name    string `json:"name"`
	Version string `json:"version"`
	Hash    string `json:"hash"`
}

type Rejected struct {
	Name   string `json:"name"`
	Reason string `json:"reason"`
}

type Output struct {
	Status   string        `json:"status"`
	Packages []LockPackage `json:"packages"`
	Rejected []Rejected    `json:"rejected"`
}

func parseVersion(value string) [3]int {
	parts := strings.Split(value, ".")
	if len(parts) != 3 {
		return [3]int{}
	}
	var out [3]int
	for i, part := range parts {
		n, err := strconv.Atoi(part)
		if err != nil {
			return [3]int{}
		}
		out[i] = n
	}
	return out
}

func cmpVersion(a, b string) int {
	left := parseVersion(a)
	right := parseVersion(b)
	for i := 0; i < 3; i++ {
		if left[i] < right[i] {
			return -1
		}
		if left[i] > right[i] {
			return 1
		}
	}
	return 0
}

func inRange(version string, req Requirement) bool {
	if req.Min != nil {
		c := cmpVersion(version, *req.Min)
		if c < 0 || (c == 0 && !req.MinInclusive) {
			return false
		}
	}
	if req.Max != nil {
		c := cmpVersion(version, *req.Max)
		if c > 0 || (c == 0 && !req.MaxInclusive) {
			return false
		}
	}
	return true
}

func hashFor(name, version string) string {
	sum := sha256.Sum256([]byte(name + "@" + version))
	return hex.EncodeToString(sum[:])
}

func contains(list []string, value string) bool {
	for _, item := range list {
		if item == value {
			return true
		}
	}
	return false
}

func providedPairs(candidate Package) []Provide {
	pairs := []Provide{{Name: candidate.Name, Version: candidate.Version}}
	pairs = append(pairs, candidate.Provides...)
	return pairs
}

func matchingPair(candidate Package, name string) (Provide, bool) {
	for _, pair := range providedPairs(candidate) {
		if pair.Name == name {
			return pair, true
		}
	}
	return Provide{}, false
}

func matchesRequirement(candidate Package, req Requirement) bool {
	for _, pair := range providedPairs(candidate) {
		if pair.Name == req.Name && inRange(pair.Version, req) {
			return true
		}
	}
	return false
}

func usableForGroup(candidate Package, reqs []Requirement, platform string) bool {
	if len(reqs) == 0 {
		return false
	}
	if !contains(candidate.Platforms, platform) && !contains(candidate.Platforms, "any") {
		return false
	}
	if candidate.Hash != hashFor(candidate.Name, candidate.Version) {
		return false
	}
	featureSet := map[string]bool{}
	for _, req := range reqs {
		if !matchesRequirement(candidate, req) {
			return false
		}
		for _, feature := range req.Features {
			featureSet[feature] = true
		}
	}
	for feature := range featureSet {
		if !contains(candidate.Features, feature) {
			return false
		}
	}
	if candidate.Yanked {
		for _, req := range reqs {
			if !req.AllowYanked {
				return false
			}
		}
	}
	return true
}

func selectedCovers(chosen map[string]Package, name string, reqs []Requirement, platform string) bool {
	for _, candidate := range chosen {
		if _, ok := matchingPair(candidate, name); ok && usableForGroup(candidate, reqs, platform) {
			return true
		}
	}
	return false
}

func conflictsOK(chosen map[string]Package) bool {
	for leftName, left := range chosen {
		for rightName, right := range chosen {
			if leftName == rightName {
				continue
			}
			for _, req := range left.Conflicts {
				if matchesRequirement(right, req) {
					return false
				}
			}
		}
	}
	return true
}

func copyGroups(groups map[string][]Requirement) map[string][]Requirement {
	out := map[string][]Requirement{}
	for name, list := range groups {
		out[name] = append([]Requirement{}, list...)
	}
	return out
}

func copyChosen(chosen map[string]Package) map[string]Package {
	out := map[string]Package{}
	for name, candidate := range chosen {
		out[name] = candidate
	}
	return out
}

func sortedNames[T any](values map[string]T) []string {
	names := make([]string, 0, len(values))
	for name := range values {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

func rows(lock map[string]Package) []Package {
	names := sortedNames(lock)
	out := make([]Package, 0, len(names))
	for _, name := range names {
		out = append(out, lock[name])
	}
	return out
}

func better(left, right map[string]Package) bool {
	leftRows := rows(left)
	rightRows := rows(right)
	if len(leftRows) != len(rightRows) {
		return len(leftRows) < len(rightRows)
	}
	for i := range leftRows {
		lv := leftRows[i].Name + "@" + leftRows[i].Version
		rv := rightRows[i].Name + "@" + rightRows[i].Version
		if lv != rv {
			return lv > rv
		}
	}
	for i := range leftRows {
		if leftRows[i].Hash != rightRows[i].Hash {
			return leftRows[i].Hash < rightRows[i].Hash
		}
	}
	return false
}

func main() {
	if len(os.Args) != 4 {
		os.Exit(2)
	}
	var request Request
	var registry Registry
	reqRaw, err := os.ReadFile(os.Args[1])
	if err != nil {
		os.Exit(2)
	}
	regRaw, err := os.ReadFile(os.Args[2])
	if err != nil {
		os.Exit(2)
	}
	if json.Unmarshal(reqRaw, &request) != nil || json.Unmarshal(regRaw, &registry) != nil {
		os.Exit(2)
	}

	byCover := map[string][]Package{}
	for _, candidate := range registry.Packages {
		for _, pair := range providedPairs(candidate) {
			byCover[pair.Name] = append(byCover[pair.Name], candidate)
		}
	}
	groups := map[string][]Requirement{}
	for _, item := range request.Roots {
		groups[item.Name] = append(groups[item.Name], item)
	}
	locks := []map[string]Package{}
	var walk func(map[string][]Requirement, map[string]Package)
	walk = func(current map[string][]Requirement, chosen map[string]Package) {
		for name, items := range current {
			if candidate, ok := chosen[name]; ok && !usableForGroup(candidate, items, request.Platform) {
				return
			}
		}
		if !conflictsOK(chosen) {
			return
		}
		pending := []string{}
		for _, name := range sortedNames(current) {
			if !selectedCovers(chosen, name, current[name], request.Platform) {
				pending = append(pending, name)
			}
		}
		if len(pending) == 0 {
			locks = append(locks, copyChosen(chosen))
			return
		}
		name := pending[0]
		for _, candidate := range byCover[name] {
			if _, ok := chosen[candidate.Name]; ok {
				continue
			}
			if !usableForGroup(candidate, current[name], request.Platform) {
				continue
			}
			nextGroups := copyGroups(current)
			nextChosen := copyChosen(chosen)
			nextChosen[candidate.Name] = candidate
			for _, dep := range candidate.Deps {
				nextGroups[dep.Name] = append(nextGroups[dep.Name], dep)
			}
			walk(nextGroups, nextChosen)
		}
	}
	walk(groups, map[string]Package{})

	out := Output{Packages: []LockPackage{}, Rejected: []Rejected{}}
	if len(locks) == 0 {
		out.Status = "blocked"
		for _, item := range request.Roots {
			out.Rejected = append(out.Rejected, Rejected{Name: item.Name, Reason: "no_lock"})
		}
	} else {
		best := locks[0]
		for _, lock := range locks[1:] {
			if better(lock, best) {
				best = lock
			}
		}
		out.Status = "ok"
		for _, candidate := range rows(best) {
			out.Packages = append(out.Packages, LockPackage{Name: candidate.Name, Version: candidate.Version, Hash: candidate.Hash})
		}
	}
	raw, err := json.Marshal(out)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	if os.WriteFile(os.Args[3], raw, 0644) != nil {
		os.Exit(2)
	}
}
GO

gofmt -w "$APP_DIR/main.go"
(cd "$APP_DIR" && go run . "$APP_DIR/task_file/request.json" "$APP_DIR/task_file/registry.json" "$APP_DIR/task_file/lock.json")
