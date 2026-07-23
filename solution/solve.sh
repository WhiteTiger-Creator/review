#!/bin/bash
set -euo pipefail

cd /app/environment

python3 - <<'PY'
from pathlib import Path

root = Path("/app/environment")

# A: matrix tags use i (not i+1) and mix width 37 (not 31)
build = root / "m3/n1/build_t.go"
text = build.read_text()
text = text.replace("uint32(i+1)", "uint32(i)", 1)
text = text.replace("rk*31", "rk*37", 1)
build.write_text(text)

# ranking must mix slot indices with LMul
(root / "m3/n1/rank_h.go").write_text(r'''package n1

// HMul and LMul are binder knobs set by the package facade before ranking.
var HMul uint32 = 65521
var LMul uint32 = 127

func scoreAt(hints []uint32, layerIx []uint16, i int) uint32 {
	return hints[i]*HMul + uint32(layerIx[i])*LMul
}

func lessOrder(scores []uint32, a, b int) bool {
	if scores[a] != scores[b] {
		return scores[a] > scores[b]
	}
	return a < b
}

// fn_h7 produces a ranking vector from schedule hints and slot indices.
func fn_h7(hints []uint32, layerIx []uint16) []uint32 {
	n := len(hints)
	if len(layerIx) < n {
		n = len(layerIx)
	}
	scores := []uint32{}
	order := []int{}
	for i := 0; i < n; i++ {
		scores = append(scores, scoreAt(hints, layerIx, i))
		order = append(order, i)
	}
	for i := 1; i < n; i++ {
		j := i
		for j > 0 {
			left, right := order[j-1], order[j]
			if !lessOrder(scores, left, right) {
				order[j-1], order[j] = order[j], order[j-1]
				j--
				continue
			}
			break
		}
	}
	ranks := []uint32{}
	for i := 0; i < n; i++ {
		ranks = append(ranks, 0)
	}
	for pos, idx := range order {
		ranks[idx] = uint32(pos)
	}
	return ranks
}

// ApplyRank sets binders then invokes fn_h7.
func ApplyRank(hints []uint32, layerIx []uint16, hintMul, laneMul uint32) []uint32 {
	HMul = hintMul
	LMul = laneMul
	return fn_h7(hints, layerIx)
}
''')

# B: joint use vs reclaim-adjusted effective capacity
(root / "p9/q2/fold_u.go").write_text(r'''package q2

// EdgeCap holds nominal capacity and reclaim for one adjacent-pair edge.
type EdgeCap struct {
	Key     string
	Cap     float64
	Reclaim float64
}

// Assign is one use contribution on an edge.
type Assign struct {
	Key string
	Use float64
}

// MassLedger accumulates joint uses and residuals per edge.
type MassLedger struct {
	Caps  map[string]EdgeCap
	Uses  map[string]float64
	Res   map[string]float64
	Order []string
}

func effectiveCap(cap EdgeCap) float64 {
	return cap.Cap - cap.Reclaim
}

func accumulateUses(ledgers *MassLedger, assigns []Assign) {
	for _, a := range assigns {
		ledgers.Uses[a.Key] += a.Use
	}
}

func countViolations(ledgers *MassLedger, eps float64) int {
	viol := 0
	for _, k := range ledgers.Order {
		cap := ledgers.Caps[k]
		eff := effectiveCap(cap)
		use := ledgers.Uses[k]
		ledgers.Res[k] = use - eff
		if use > eff+eps {
			viol++
		}
	}
	return viol
}

// fn_p9 folds assignment residuals into mass ledgers under epsilon.
func fn_p9(ledgers *MassLedger, assigns []Assign, eps float64) int {
	if ledgers.Uses == nil {
		ledgers.Uses = map[string]float64{}
	}
	if ledgers.Res == nil {
		ledgers.Res = map[string]float64{}
	}
	accumulateUses(ledgers, assigns)
	return countViolations(ledgers, eps)
}

// ApplyFold invokes fn_p9 after clearing use maps.
func ApplyFold(ledgers *MassLedger, assigns []Assign, eps float64) int {
	ledgers.Uses = map[string]float64{}
	ledgers.Res = map[string]float64{}
	return fn_p9(ledgers, assigns, eps)
}

// UtilMax returns max joint_use/eff across edges.
func UtilMax(ledgers *MassLedger) float64 {
	max := 0.0
	for _, k := range ledgers.Order {
		cap := ledgers.Caps[k]
		eff := effectiveCap(cap)
		if eff < 1e-12 {
			eff = 1e-12
		}
		u := ledgers.Uses[k] / eff
		if u > max {
			max = u
		}
	}
	return max
}
''')

# C: independent seal ignores green gauges; always policy payload
(root / "r5/s4/zip_v.go").write_text(r'''package s4

import (
	"crypto/sha256"
	"encoding/hex"
)

// StageRow is one early gauge row.
type StageRow struct {
	Mark int
}

// SealRecord holds independent seal material.
type SealRecord struct {
	Hex string
}

// JFrag holds the stitched journal binder for the active seal call.
var JFrag []byte

func journalPrefix() []byte {
	sumJ := sha256.Sum256(JFrag)
	return sumJ[:8]
}

func sealPayload(witness []byte) []byte {
	payload := append([]byte("seal/t1:"), witness...)
	payload = append(payload, journalPrefix()...)
	return payload
}

// fn_r5 seals stages against witness bytes for independent replay.
func fn_r5(stages []StageRow, witness []byte) SealRecord {
	for range stages {
		// Stage marks are early gauges only; independent replay ignores them.
	}
	sum := sha256.Sum256(sealPayload(witness))
	return SealRecord{Hex: hex.EncodeToString(sum[:])}
}

// ApplyZip binds journal material then invokes fn_r5.
func ApplyZip(stages []StageRow, witness []byte, journal []byte) SealRecord {
	JFrag = append([]byte(nil), journal...)
	return fn_r5(stages, witness)
}
''')

# D: success concatenates journals; partial keeps gen and prior blob
(root / "r5/s4/xfer_w.go").write_text(r'''package s4

// AlgebraState is the running closed-algebra journal and generation.
type AlgebraState struct {
	Gen     uint32
	Journal []byte
	ArmBlob []byte
	Partial int
}

func cloneBytes(src []byte) []byte {
	return append([]byte(nil), src...)
}

func nextGen(prev uint32) uint32 {
	return prev + 1
}

func rollbackPartial(prev *AlgebraState) AlgebraState {
	out := AlgebraState{}
	out.Gen = nextGen(prev.Gen)
	out.Journal = cloneBytes(prev.Journal)
	out.ArmBlob = cloneBytes(prev.ArmBlob)
	out.Partial = 1
	return out
}

func commitArm(prev *AlgebraState, next *AlgebraState) AlgebraState {
	out := AlgebraState{}
	out.Gen = nextGen(prev.Gen)
	out.Journal = append(cloneBytes(prev.Journal), next.ArmBlob...)
	out.ArmBlob = cloneBytes(next.ArmBlob)
	out.Partial = 0
	return out
}

// fn_w2 stitches fixture algebra state with rollback of partial seals.
func fn_w2(prev *AlgebraState, next *AlgebraState) AlgebraState {
	if next.Partial != 0 {
		return rollbackPartial(prev)
	}
	return commitArm(prev, next)
}

// ApplyXfer invokes fn_w2.
func ApplyXfer(prev *AlgebraState, next *AlgebraState) AlgebraState {
	return fn_w2(prev, next)
}
''')
PY

bash tools/build.sh
mkdir -p /app/output/stage
./tools/hv7 --corpus /app/environment/data/pack_c --out /app/output/invariant_bundle.yaml
