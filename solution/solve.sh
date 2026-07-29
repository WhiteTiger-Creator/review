#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/go/bin:/opt/verifier/bin:${PATH}"

cat > /app/environment/clk/bus.go <<'EOF'
package clk

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"

	"stormlab/ld"
)

const busPath = "/app/environment/pack/seed/.epoch_bus.json"
const stormGenPath = "/app/environment/pack/seed/.storm_gen"

type busDoc struct {
	Token    uint64 `json:"token"`
	BoundGen int    `json:"bound_gen"`
	StormOK  bool   `json:"storm_ok"`
	Rev      uint64 `json:"rev"`
}

var (
	mu     sync.Mutex
	loaded bool
	cache  busDoc
)

func bus_r() error {
	mu.Lock()
	defer mu.Unlock()
	data, err := os.ReadFile(busPath)
	if err != nil {
		return err
	}
	var doc busDoc
	if err := json.Unmarshal(data, &doc); err != nil {
		return err
	}
	cache = doc
	loaded = true
	return nil
}

func ensure() error {
	if loaded {
		return nil
	}
	return bus_r()
}

func bus_w() error {
	mu.Lock()
	defer mu.Unlock()
	data, err := json.Marshal(cache)
	if err != nil {
		return err
	}
	dir := filepath.Dir(busPath)
	tmp, err := os.CreateTemp(dir, ".epoch_bus.*.tmp")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		_ = os.Remove(tmpName)
		return err
	}
	if err := tmp.Close(); err != nil {
		_ = os.Remove(tmpName)
		return err
	}
	return os.Rename(tmpName, busPath)
}

func readStormZero() bool {
	raw, err := os.ReadFile(stormGenPath)
	if err != nil {
		return false
	}
	gen := -1
	_, _ = fmt.Sscanf(string(raw), "%d", &gen)
	return gen == 0
}

func bind_q(tipGen int) error {
	if err := ensure(); err != nil {
		return err
	}
	ok := readStormZero()
	mu.Lock()
	cache.BoundGen = tipGen
	cache.Token++
	cache.StormOK = ok
	cache.Rev++
	mu.Unlock()
	return bus_w()
}

func invalidate_k() error {
	if err := ensure(); err != nil {
		return err
	}
	mu.Lock()
	cache.Token++
	cache.Rev++
	mu.Unlock()
	return bus_w()
}

func restore_p() error {
	if err := ensure(); err != nil {
		return err
	}
	tip, err := ld.Run()
	if err != nil {
		return err
	}
	mu.Lock()
	cache.BoundGen = tip
	cache.StormOK = true
	cache.Token++
	cache.Rev++
	mu.Unlock()
	return bus_w()
}

func Token() uint64 {
	_ = ensure()
	mu.Lock()
	defer mu.Unlock()
	return cache.Token
}

func BoundGen() int {
	_ = ensure()
	mu.Lock()
	defer mu.Unlock()
	return cache.BoundGen
}

func StormOK() bool {
	_ = ensure()
	mu.Lock()
	defer mu.Unlock()
	return cache.StormOK
}

func Coherent(tip int) bool {
	_ = ensure()
	mu.Lock()
	bg := cache.BoundGen
	ok := cache.StormOK
	mu.Unlock()
	return bg == tip && ok && readStormZero()
}

func BindQ(tipGen int) error { return bind_q(tipGen) }
func InvalidateK() error    { return invalidate_k() }
func RestoreP() error       { return restore_p() }
EOF

cat > /app/environment/m2/limit/slot_y.go <<'EOF'
package limit

import (
	"sync"

	"stormlab/clk"
)

type cacheEntry struct {
	token       uint64
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
	tok := clk.Token()
	hitCache.Lock()
	defer hitCache.Unlock()
	if cached != nil &&
		cached.token == tok &&
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
		token:       tok,
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

# Insert tip-bus bind into ResolvePolicy (surgical; avoid whole-file rewrite).
python3 - <<'PY'
from pathlib import Path
path = Path("/app/environment/driver/engine.go")
text = path.read_text(encoding="utf-8")
needle = "\t_ = clk.StormOK()\n"
insert = (
    "\tif err = clk.BindQ(tip); err != nil {\n"
    "\t\treturn tip, ov, \"\", err\n"
    "\t}\n"
)
if needle not in text:
    raise SystemExit("ResolvePolicy storm stub missing")
if "clk.BindQ(tip)" not in text:
    text = text.replace(needle, insert, 1)
    path.write_text(text, encoding="utf-8")
PY

cd /app
python3 /app/environment/scripts/gen_fixtures.py
printf '%s\n' '{"token":0,"bound_gen":1,"storm_ok":true,"rev":1}' > /app/environment/pack/seed/.epoch_bus.json
export GOCACHE=/tmp/tb-gocache
go clean -cache 2>/dev/null || true
bash /app/environment/scripts/build_all.sh
cd /app/environment
go build -a -o /app/environment/bin/wave_sched ./cmd/wave_sched
go build -a -o /app/environment/bin/epochctl ./cmd/epochctl
bash /app/environment/phase/rld_x2.sh --preserve-anchor
