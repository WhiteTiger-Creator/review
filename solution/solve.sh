#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/go/bin:/opt/verifier/bin:${PATH}"

cat > /app/environment/ld/tip.go <<'EOF'
package ld

import (
	"bufio"
	"encoding/json"
	"os"
)

const ledgerPath = "/app/environment/pack/ledger/waves.ndjson"

type waveRec struct {
	Gen  int  `json:"gen"`
	Tomb bool `json:"tomb"`
}

func tip_q(path string) (int, error) {
	f, err := os.Open(path)
	if err != nil {
		return 0, err
	}
	defer f.Close()
	tip := -1
	seen := 0
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Bytes()
		if len(line) == 0 {
			continue
		}
		var rec waveRec
		if err := json.Unmarshal(line, &rec); err != nil {
			return 0, err
		}
		seen++
		if rec.Tomb {
			continue
		}
		if rec.Gen < 0 {
			continue
		}
		if rec.Gen > tip {
			tip = rec.Gen
		}
	}
	if err := sc.Err(); err != nil {
		return 0, err
	}
	if seen == 0 || tip < 0 {
		return 0, nil
	}
	return tip, nil
}

func Run() (int, error) {
	return tip_q(ledgerPath)
}
EOF

cat > /app/environment/pol/pick.go <<'EOF'
package pol

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

const policyDir = "/app/environment/pack/policy"

type Overlay struct {
	Gen          int    `json:"gen"`
	ShadowRadius int    `json:"shadow_radius"`
	PolicyID     string `json:"policy_id"`
	Path         string `json:"-"`
}

var active Overlay

func pick_w(tipGen int) (Overlay, error) {
	path := filepath.Join(policyDir, fmt.Sprintf("ov_g%d.json", tipGen))
	return loadOverlay(path)
}

func loadOverlay(path string) (Overlay, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Overlay{}, err
	}
	var ov Overlay
	if err := json.Unmarshal(data, &ov); err != nil {
		return Overlay{}, err
	}
	ov.Path = path
	return ov, nil
}

func Run(tipGen int) (Overlay, error) {
	ov, err := pick_w(tipGen)
	if err != nil {
		return Overlay{}, err
	}
	active = ov
	return ov, nil
}

func ActiveRadius() int {
	if active.ShadowRadius <= 0 {
		return 1
	}
	return active.ShadowRadius
}

func ActiveGen() int {
	return active.Gen
}

func ActiveID() string {
	return active.PolicyID
}

func ActivePath() string {
	return active.Path
}

func InstallForProbe(ov Overlay) {
	active = ov
}
EOF

cat > /app/environment/k4/graph/rank_x.go <<'EOF'
package graph

import (
	"sort"

	"stormlab/pol"
)

func rank_x(arms *EdgeArms, sink *ShadowSink) error {
	if len(arms.Items) == 0 {
		return ChainErr{}
	}
	sink.Active = sink.Active[:0]
	sink.Suppressed = make(map[uint8]struct{})
	radius := pol.ActiveRadius()
	order := append([]EdgeArm(nil), arms.Items...)
	sort.Slice(order, func(i, j int) bool { return order[i].Seq < order[j].Seq })
	for _, arm := range order {
		if arm.Kind != ArmExclude || arm.ShadowLink == 0 {
			continue
		}
		link := arm.ShadowLink
		for _, other := range arms.Items {
			if other.Kind != ArmInclude {
				continue
			}
			if (other.Mask & arm.Mask) == 0 {
				continue
			}
			diff := int(other.ID)
			if diff > int(link) {
				diff -= int(link)
			} else {
				diff = int(link) - diff
			}
			if diff >= radius {
				sink.Suppressed[other.ID] = struct{}{}
			}
		}
	}
	for _, arm := range order {
		if arm.Kind == ArmInclude {
			if _, blocked := sink.Suppressed[arm.ID]; !blocked {
				sink.Active = append(sink.Active, arm.ID)
			}
		}
	}
	sink.Epoch++
	return nil
}

func Run(arms *EdgeArms, sink *ShadowSink) error {
	return rank_x(arms, sink)
}
EOF

cat > /app/environment/m2/limit/slot_y.go <<'EOF'
package limit

import "sync"

type cacheEntry struct {
	family      string
	policyGen   uint32
	cellLen     int
	eventLen    int
	shadowEpoch uint32
	eventSig    uint64
	hits        []uint32
}

var hitCache sync.Mutex
var cached *cacheEntry

func eventSignature(events *EventBatch) uint64 {
	var sig uint64
	for _, row := range events.Rows {
		sig = sig*131 + uint64(row.FieldByte)
	}
	return sig
}

func slot_y(windows *BurstGrid, events *EventBatch) error {
	if len(windows.Cells) == 0 {
		return TallyErr{}
	}
	sig := eventSignature(events)
	hitCache.Lock()
	defer hitCache.Unlock()
	if cached != nil &&
		cached.family == windows.Family &&
		cached.policyGen == windows.PolicyGen &&
		cached.cellLen == len(windows.Cells) &&
		cached.eventLen == len(events.Rows) &&
		cached.shadowEpoch == windows.ShadowEpoch &&
		cached.eventSig == sig {
		for i, cell := range windows.Cells {
			cell.Hits = cached.hits[i]
			windows.Cells[i] = cell
		}
		windows.CacheEpoch = windows.ShadowEpoch
		return nil
	}
	hits := make([]uint32, 0, len(windows.Cells))
	for i := range windows.Cells {
		windows.Cells[i].Hits = 0
		for _, row := range events.Rows {
			if (uint16(row.FieldByte) & windows.Cells[i].Mask) != 0 {
				windows.Cells[i].Hits++
			}
		}
		hits = append(hits, windows.Cells[i].Hits)
	}
	cached = &cacheEntry{
		family:      windows.Family,
		policyGen:   windows.PolicyGen,
		cellLen:     len(windows.Cells),
		eventLen:    len(events.Rows),
		shadowEpoch: windows.ShadowEpoch,
		eventSig:    sig,
		hits:        hits,
	}
	windows.CacheEpoch = windows.ShadowEpoch
	return nil
}

func Run(windows *BurstGrid, events *EventBatch) error {
	return slot_y(windows, events)
}
EOF

cat > /app/environment/p8/g9/fold_z.go <<'EOF'
package g9

import (
	"os"
	"path/filepath"
	"sort"
	"strconv"

	"stormlab/pol"
)

func fold_z(budget SlotBudget, grid *ScoreGrid, out *OrderSink) error {
	if len(grid.Scores) == 0 {
		return SeekErr{}
	}
	out.LaneOrder = out.LaneOrder[:0]
	take := int(budget.Slots)
	if take > len(grid.Scores) {
		take = len(grid.Scores)
	}
	anchor := readGenBoundAnchor()
	type row struct {
		id    uint8
		score uint32
		tie   uint8
	}
	scored := make([]row, len(grid.Scores))
	for i, s := range grid.Scores {
		scored[i] = row{id: s.ID, score: s.Score, tie: anchor[int(s.ID)%8]}
	}
	sort.Slice(scored, func(i, j int) bool {
		if scored[i].score != scored[j].score {
			return scored[i].score > scored[j].score
		}
		if scored[i].tie != scored[j].tie {
			return scored[i].tie > scored[j].tie
		}
		return scored[i].id < scored[j].id
	})
	for i := 0; i < take; i++ {
		out.LaneOrder = append(out.LaneOrder, int(scored[i].id))
	}
	out.Anchor = anchor
	out.Staging++
	return nil
}

func readGenBoundAnchor() [8]byte {
	gen := pol.ActiveGen()
	cp := filepath.Join("/app/environment/pack/checkpoints", "stg_g"+strconv.Itoa(gen)+".bin")
	if data, err := os.ReadFile(cp); err == nil && len(data) >= 8 {
		var out [8]byte
		copy(out[:], data[:8])
		return out
	}
	return ReadStagedAnchor()
}

func Run(budget SlotBudget, grid *ScoreGrid, out *OrderSink) error {
	return fold_z(budget, grid, out)
}
EOF

cd /app
python3 /app/environment/scripts/gen_fixtures.py
export GOCACHE=/tmp/tb-gocache
go clean -cache 2>/dev/null || true
bash /app/environment/scripts/build_all.sh
cd /app/environment
go build -a -o /app/environment/bin/wave_sched ./cmd/wave_sched
bash /app/environment/phase/rld_x2.sh --preserve-anchor
