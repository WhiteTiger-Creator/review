#!/bin/bash
set -euo pipefail
cd /app
mkdir -p internal/reclaim
cat > internal/reclaim/reclaim.go <<'GOEOF'
// Package reclaim implements the snapshot reclaim supervisor described in
// /app/PROTOCOL.md: it decides which snapshots a pool keeps, how many blocks the
// released set frees, and how far down the reclaim ladder the pool has to go.
package reclaim

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"
)

// Tiers are listed in the order the keep counts are spent, which is also the
// order retention classes are tried and the order the ladder relaxes.
var Tiers = [4]string{"hourly", "daily", "weekly", "monthly"}

const layout = "2006-01-02T15:04:05Z"

type Snapshot struct {
	ID        string `json:"id"`
	Taken     string `json:"taken"`
	HoldUntil string `json:"hold_until"`
	Clone     bool   `json:"clone"`
}

type Extent struct {
	Blocks int  `json:"blocks"`
	First  int  `json:"first"`
	Last   int  `json:"last"`
	Live   bool `json:"live"`
}

type Keep struct {
	Hourly  *int `json:"hourly"`
	Daily   *int `json:"daily"`
	Weekly  *int `json:"weekly"`
	Monthly *int `json:"monthly"`
}

type Pool struct {
	Name      string     `json:"pool"`
	Now       string     `json:"now"`
	Keep      *Keep      `json:"keep"`
	Target    *int       `json:"target_blocks"`
	Snapshots []Snapshot `json:"snapshots"`
	Extents   []Extent   `json:"extents"`
}

type KeepOut struct {
	Hourly  int `json:"hourly"`
	Daily   int `json:"daily"`
	Weekly  int `json:"weekly"`
	Monthly int `json:"monthly"`
}

type RetainedRow struct {
	ID    string `json:"id"`
	Class string `json:"class"`
}

type PoolRow struct {
	Pool      string        `json:"pool"`
	Passes    int           `json:"passes"`
	KeepFinal KeepOut       `json:"keep_final"`
	Retained  []RetainedRow `json:"retained"`
	Pruned    []string      `json:"pruned"`
	Freed     int           `json:"freed_blocks"`
	Shortfall int           `json:"shortfall"`
	Digest    string        `json:"digest"`
}

type Report struct {
	Pools  []PoolRow `json:"pools"`
	Digest string    `json:"digest"`
}

func parseTS(value string) (time.Time, error) {
	if len(value) != 20 {
		return time.Time{}, fmt.Errorf("bad timestamp %q", value)
	}
	moment, err := time.Parse(layout, value)
	if err != nil {
		return time.Time{}, fmt.Errorf("bad timestamp %q", value)
	}
	if moment.Format(layout) != value {
		return time.Time{}, fmt.Errorf("bad timestamp %q", value)
	}
	return moment, nil
}

// periodKey is the period a snapshot falls in for one tier.
func periodKey(tier, taken string) (string, error) {
	switch tier {
	case "hourly":
		return taken[:13], nil
	case "daily":
		return taken[:10], nil
	case "monthly":
		return taken[:7], nil
	}
	moment, err := parseTS(taken)
	if err != nil {
		return "", err
	}
	back := (int(moment.Weekday()) + 6) % 7 // Monday starts the week
	return moment.AddDate(0, 0, -back).Format("2006-01-02"), nil
}

func validate(pool Pool) error {
	if pool.Name == "" {
		return fmt.Errorf("pool name missing")
	}
	if _, err := parseTS(pool.Now); err != nil {
		return err
	}
	if len(pool.Snapshots) == 0 {
		return fmt.Errorf("pool %q has no snapshots", pool.Name)
	}
	if pool.Keep == nil || pool.Keep.Hourly == nil || pool.Keep.Daily == nil ||
		pool.Keep.Weekly == nil || pool.Keep.Monthly == nil {
		return fmt.Errorf("pool %q keep incomplete", pool.Name)
	}
	for _, count := range []int{*pool.Keep.Hourly, *pool.Keep.Daily, *pool.Keep.Weekly, *pool.Keep.Monthly} {
		if count < 0 {
			return fmt.Errorf("pool %q keep negative", pool.Name)
		}
	}
	if pool.Target == nil || *pool.Target < 0 {
		return fmt.Errorf("pool %q target_blocks invalid", pool.Name)
	}
	seen := map[string]bool{}
	var previous time.Time
	for index, snap := range pool.Snapshots {
		if snap.ID == "" {
			return fmt.Errorf("pool %q snapshot with empty id", pool.Name)
		}
		if seen[snap.ID] {
			return fmt.Errorf("pool %q duplicate snapshot id %q", pool.Name, snap.ID)
		}
		seen[snap.ID] = true
		taken, err := parseTS(snap.Taken)
		if err != nil {
			return err
		}
		if index > 0 && !taken.After(previous) {
			return fmt.Errorf("pool %q snapshots not strictly increasing", pool.Name)
		}
		previous = taken
		if snap.HoldUntil != "" {
			if _, err := parseTS(snap.HoldUntil); err != nil {
				return err
			}
		}
	}
	for _, extent := range pool.Extents {
		if extent.Blocks <= 0 {
			return fmt.Errorf("pool %q extent blocks invalid", pool.Name)
		}
		if extent.First < 0 || extent.Last < 0 ||
			extent.First >= len(pool.Snapshots) || extent.Last >= len(pool.Snapshots) {
			return fmt.Errorf("pool %q extent index out of range", pool.Name)
		}
		if extent.First > extent.Last {
			return fmt.Errorf("pool %q extent first after last", pool.Name)
		}
	}
	return nil
}

// anchors are the snapshots kept regardless of the tier counts.
func anchors(pool Pool) (map[int]string, error) {
	now, err := parseTS(pool.Now)
	if err != nil {
		return nil, err
	}
	out := map[int]string{}
	for index, snap := range pool.Snapshots {
		if snap.HoldUntil != "" {
			until, err := parseTS(snap.HoldUntil)
			if err != nil {
				return nil, err
			}
			if until.After(now) {
				out[index] = "hold"
				continue
			}
		}
		if snap.Clone {
			out[index] = "clone"
		}
	}
	return out, nil
}

// representatives maps each period key of a tier to the lowest snapshot index in
// it, which is the first snapshot taken in that period.
func representatives(pool Pool, tier string) (map[string]int, error) {
	out := map[string]int{}
	for index, snap := range pool.Snapshots {
		key, err := periodKey(tier, snap.Taken)
		if err != nil {
			return nil, err
		}
		if _, ok := out[key]; !ok {
			out[key] = index
		}
	}
	return out, nil
}

// retainedSet spends each tier's keep counts over its periods, newest first. An
// anchor is already kept, so its period costs the tier nothing.
func retainedSet(pool Pool, keep [4]int, anchor map[int]string) (map[int]string, error) {
	out := map[int]string{}
	for index, class := range anchor {
		out[index] = class
	}
	for slot, tier := range Tiers {
		remaining := keep[slot]
		if remaining <= 0 {
			continue
		}
		reps, err := representatives(pool, tier)
		if err != nil {
			return nil, err
		}
		keys := make([]string, 0, len(reps))
		for key := range reps {
			keys = append(keys, key)
		}
		sort.Sort(sort.Reverse(sort.StringSlice(keys)))
		for _, key := range keys {
			index := reps[key]
			if _, isAnchor := anchor[index]; isAnchor {
				continue
			}
			if _, already := out[index]; !already {
				out[index] = tier
			}
			remaining--
			if remaining == 0 {
				break
			}
		}
	}
	return out, nil
}

// freedBlocks sums the extents nothing is left holding: an extent survives
// unless it is off the live filesystem and every snapshot in its span went.
func freedBlocks(pool Pool, retained map[int]string) int {
	total := 0
	for _, extent := range pool.Extents {
		if extent.Live {
			continue
		}
		held := false
		for index := extent.First; index <= extent.Last; index++ {
			if _, ok := retained[index]; ok {
				held = true
				break
			}
		}
		if !held {
			total += extent.Blocks
		}
	}
	return total
}

// relax subtracts one from the first tier still above zero.
func relax(keep [4]int) ([4]int, bool) {
	for slot := range keep {
		if keep[slot] > 0 {
			keep[slot]--
			return keep, true
		}
	}
	return keep, false
}

func planPool(pool Pool) (PoolRow, error) {
	if err := validate(pool); err != nil {
		return PoolRow{}, err
	}
	anchor, err := anchors(pool)
	if err != nil {
		return PoolRow{}, err
	}
	keep := [4]int{*pool.Keep.Hourly, *pool.Keep.Daily, *pool.Keep.Weekly, *pool.Keep.Monthly}
	passes, freed := 0, 0
	var retained map[int]string
	for {
		retained, err = retainedSet(pool, keep, anchor)
		if err != nil {
			return PoolRow{}, err
		}
		// Every step recomputes the whole surviving set, so the freed total
		// describes the set the run ends on rather than a running sum.
		freed = freedBlocks(pool, retained)
		if freed >= *pool.Target {
			break
		}
		next, ok := relax(keep)
		if !ok {
			break
		}
		keep = next
		passes++
	}
	row := PoolRow{
		Pool:      pool.Name,
		Passes:    passes,
		KeepFinal: KeepOut{Hourly: keep[0], Daily: keep[1], Weekly: keep[2], Monthly: keep[3]},
		Retained:  []RetainedRow{},
		Pruned:    []string{},
		Freed:     freed,
	}
	for index, snap := range pool.Snapshots {
		if class, ok := retained[index]; ok {
			row.Retained = append(row.Retained, RetainedRow{ID: snap.ID, Class: class})
		} else {
			row.Pruned = append(row.Pruned, snap.ID)
		}
	}
	if *pool.Target > freed {
		row.Shortfall = *pool.Target - freed
	}
	row.Digest = poolDigest(row)
	return row, nil
}

func poolDigest(row PoolRow) string {
	retained := make([]string, 0, len(row.Retained))
	for _, item := range row.Retained {
		retained = append(retained, item.ID+":"+item.Class)
	}
	lines := []string{
		row.Pool,
		strconv.Itoa(row.Passes),
		fmt.Sprintf("%d,%d,%d,%d", row.KeepFinal.Hourly, row.KeepFinal.Daily,
			row.KeepFinal.Weekly, row.KeepFinal.Monthly),
		strings.Join(retained, ";"),
		strings.Join(row.Pruned, ";"),
		strconv.Itoa(row.Freed),
		strconv.Itoa(row.Shortfall),
	}
	sum := sha256.Sum256([]byte(strings.Join(lines, "\n") + "\n"))
	return hex.EncodeToString(sum[:])
}

func Plan(pools []Pool) (Report, error) {
	seen := map[string]bool{}
	rows := make([]PoolRow, 0, len(pools))
	for _, pool := range pools {
		if seen[pool.Name] {
			return Report{}, fmt.Errorf("duplicate pool name %q", pool.Name)
		}
		seen[pool.Name] = true
		row, err := planPool(pool)
		if err != nil {
			return Report{}, err
		}
		rows = append(rows, row)
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].Pool < rows[j].Pool })
	var payload strings.Builder
	for _, row := range rows {
		payload.WriteString(row.Pool + " " + row.Digest + "\n")
	}
	sum := sha256.Sum256([]byte(payload.String()))
	return Report{Pools: rows, Digest: hex.EncodeToString(sum[:])}, nil
}
GOEOF
cat > cmd/reclaim/main.go <<'GOEOF'
package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"reclaim/internal/reclaim"
)

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(args []string) error {
	if len(args) == 0 || args[0] != "plan" {
		return fmt.Errorf("usage: reclaim plan --pools PATH --out PATH")
	}
	fs := flag.NewFlagSet("plan", flag.ContinueOnError)
	var poolsPath, out string
	fs.StringVar(&poolsPath, "pools", "", "pool records JSONL")
	fs.StringVar(&out, "out", "", "output JSON")
	if err := fs.Parse(args[1:]); err != nil {
		return err
	}
	if fs.NArg() != 0 || poolsPath == "" || out == "" {
		return fmt.Errorf("both --pools and --out are required")
	}
	pools, err := loadPools(poolsPath)
	if err != nil {
		return fmt.Errorf("load pools: %w", err)
	}
	report, err := reclaim.Plan(pools)
	if err != nil {
		return err
	}
	return writeAtomic(out, report)
}

func loadPools(path string) ([]reclaim.Pool, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	pools := []reclaim.Pool{}
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 64*1024), 8*1024*1024)
	line := 0
	for sc.Scan() {
		line++
		raw := sc.Bytes()
		if len(bytes.TrimSpace(raw)) == 0 {
			return nil, fmt.Errorf("blank pool line %d", line)
		}
		var pool reclaim.Pool
		if err := json.Unmarshal(raw, &pool); err != nil {
			return nil, fmt.Errorf("invalid pool line %d: %w", line, err)
		}
		pools = append(pools, pool)
	}
	if err := sc.Err(); err != nil {
		return nil, err
	}
	if len(pools) == 0 {
		return nil, fmt.Errorf("no pool records")
	}
	return pools, nil
}

func writeAtomic(path string, report reclaim.Report) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	tmp, err := os.CreateTemp(filepath.Dir(path), ".reclaim-out-*")
	if err != nil {
		return err
	}
	name := tmp.Name()
	defer os.Remove(name)
	if _, err := tmp.Write(b); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Sync(); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	return os.Rename(name, path)
}
GOEOF
gofmt -w cmd internal
go build -o /app/reclaim ./cmd/reclaim
