#!/bin/bash
set -euo pipefail
cd /app/environment

cat > w3j/append.go <<'EOF'
package w3j

import (
	"encoding/json"
	"os"
	"sort"
	"strings"
)

func preferFrame(prev, next Frame) bool {
	if next.Seq != prev.Seq {
		return next.Seq > prev.Seq
	}
	return next.Epoch > prev.Epoch
}

func normalizeArm(fr *Frame, arm byte) {
	switch arm {
	case 'a':
		if fr.PreTok == "" {
			fr.PreTok = "allow"
		}
	case 'b':
		if fr.PreTok != "allow" {
			fr.Lo = StripPreToken(fr.Lo)
			fr.Hi = StripPreToken(fr.Hi)
		}
	}
}

func ingestLine(raw map[string]any, arm byte, epoch uint64) Frame {
	fr := Frame{ArmTag: arm, Epoch: epoch}
	if v, ok := raw["pkg"].(string); ok {
		fr.Pkg = v
	}
	if v, ok := raw["dep"].(string); ok {
		fr.Dep = v
	}
	if v, ok := raw["lo"].(string); ok {
		fr.Lo = v
	}
	if v, ok := raw["hi"].(string); ok {
		fr.Hi = v
	}
	if v, ok := raw["pre_tok"].(string); ok {
		fr.PreTok = v
	}
	if v, ok := raw["lift"].(bool); ok {
		fr.Lift = v
	}
	if v, ok := raw["act_tok"].(string); ok {
		fr.ActTok = v
	}
	if v, ok := raw["seq"].(float64); ok {
		fr.Seq = int(v)
	}
	normalizeArm(&fr, arm)
	fr.CRC = SealCRC(fr)
	return fr
}

func fn_w3(lines []RawLine, walPath string) ([]Frame, error) {
	var epoch uint64
	type key struct {
		pkg, dep string
		arm      byte
	}
	best := map[key]Frame{}
	for _, ln := range lines {
		raw, err := ParseLoose(ln.Bytes)
		if err != nil {
			return nil, err
		}
		epoch++
		fr := ingestLine(raw, ln.ArmTag, epoch)
		k := key{fr.Pkg, fr.Dep, fr.ArmTag}
		if prev, ok := best[k]; !ok || preferFrame(prev, fr) {
			best[k] = fr
		}
	}

	if b, err := os.ReadFile(walPath); err == nil {
		for _, line := range strings.Split(string(b), "\n") {
			line = strings.TrimSpace(line)
			if line == "" {
				continue
			}
			var fr Frame
			if json.Unmarshal([]byte(line), &fr) != nil {
				continue
			}
			if fr.CRC != SealCRC(fr) {
				continue
			}
			k := key{fr.Pkg, fr.Dep, fr.ArmTag}
			if prev, ok := best[k]; !ok || preferFrame(prev, fr) {
				best[k] = fr
			}
		}
	}

	out := []Frame{}
	for _, fr := range best {
		out = append(out, fr)
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].Pkg != out[j].Pkg {
			return out[i].Pkg < out[j].Pkg
		}
		if out[i].Dep != out[j].Dep {
			return out[i].Dep < out[j].Dep
		}
		if out[i].ArmTag != out[j].ArmTag {
			return out[i].ArmTag < out[j].ArmTag
		}
		return out[i].Seq < out[j].Seq
	})
	if err := writeWAL(walPath, out); err != nil {
		return nil, err
	}
	return out, nil
}

func FnW3(lines []RawLine, walPath string) ([]Frame, error) {
	return fn_w3(lines, walPath)
}
EOF

cat > x8c/lookup.go <<'EOF'
package x8c

func optionalAllowed(e Edge, toggles map[string]bool) bool {
	if !e.Optional {
		return true
	}
	return toggles[e.ActKey] && e.ActPresent
}

func filterEdges(graph GraphView, toggles map[string]bool) []Edge {
	var kept []Edge
	for _, e := range graph.Edges {
		if optionalAllowed(e, toggles) {
			kept = append(kept, e)
		}
	}
	return kept
}

func cacheKey(mat Material) string {
	fp := FingerprintFrames(mat.Frames)
	return HashBytes(mat.SeedJSON, mat.ActJSON, []byte(fp), []byte(mat.PeerFinger))
}

func fn_x8(graph GraphView, toggles map[string]bool, mat Material, cacheDir string) (Decision, error) {
	kept := filterEdges(graph, toggles)
	key := cacheKey(mat)
	storedPeer, rows, ok, err := ReadCacheBlob(cacheDir, key)
	if err != nil {
		return Decision{}, err
	}
	if ok && storedPeer == mat.PeerFinger {
		return Decision{Hit: true, KeyHex: key, RowsRaw: rows, Edges: kept}, nil
	}
	return Decision{Hit: false, KeyHex: key, Edges: kept}, nil
}

func FnX8(graph GraphView, toggles map[string]bool, mat Material, cacheDir string) (Decision, error) {
	return fn_x8(graph, toggles, mat, cacheDir)
}

func PutCache(cacheDir, keyHex string, blob []byte) error {
	return putCache(cacheDir, keyHex, blob)
}
EOF

cat > y4f/reduce.go <<'EOF'
package y4f

import (
	"sort"

	"depctrl/w3j"
)

func intersectBounds(group []w3j.Frame) (lo, hi, preTok string, lift bool) {
	lo = group[0].Lo
	hi = group[0].Hi
	preTok = ""
	lift = false
	for _, r := range group {
		if cmpVer(r.Lo, lo) > 0 {
			lo = r.Lo
		}
		if cmpVer(r.Hi, hi) < 0 {
			hi = r.Hi
		}
		if r.PreTok == "allow" {
			preTok = "allow"
		}
		if r.Lift {
			lift = true
		}
	}
	return lo, hi, preTok, lift
}

func applyPeerCeiling(hi string, lift bool, peer string, ok bool) string {
	if !ok || !lift {
		return hi
	}
	if cmpVer(peer, hi) < 0 {
		return peer
	}
	return hi
}

func emitRow(pkg, dep, lo, hi, preTok string, lift bool) RowOut {
	if preTok == "" {
		hi = StripPreToken(hi)
		lo = StripPreToken(lo)
	}
	return RowOut{
		Pkg: pkg, Dep: dep, Lo: lo, Hi: hi, PreTok: preTok, Lift: lift,
		RowDigest: RowDigest(pkg, dep, lo, hi, preTok, lift),
	}
}

func fn_y4(frames []w3j.Frame, allowed map[string]bool, probe ProbeView) ([]RowOut, error) {
	type key struct{ pkg, dep string }
	buckets := map[key][]w3j.Frame{}
	for _, fr := range frames {
		k := key{fr.Pkg, fr.Dep}
		if len(allowed) > 0 && !allowed[fr.Pkg+"\x00"+fr.Dep] {
			continue
		}
		buckets[k] = append(buckets[k], fr)
	}
	keys := []key{}
	for k := range buckets {
		keys = append(keys, k)
	}
	sort.Slice(keys, func(i, j int) bool {
		if keys[i].pkg != keys[j].pkg {
			return keys[i].pkg < keys[j].pkg
		}
		return keys[i].dep < keys[j].dep
	})
	var out []RowOut
	for _, k := range keys {
		lo, hi, preTok, lift := intersectBounds(buckets[k])
		pkey := k.pkg + "\x00" + k.dep
		peer, ok := probe.PeerHi[pkey]
		hi = applyPeerCeiling(hi, lift, peer, ok)
		out = append(out, emitRow(k.pkg, k.dep, lo, hi, preTok, lift))
	}
	return out, nil
}

func FnY4(frames []w3j.Frame, allowed map[string]bool, probe ProbeView) ([]RowOut, error) {
	return fn_y4(frames, allowed, probe)
}
EOF

export GOPROXY=off GOSUMDB=off GOTELEMETRY=off GOTOOLCHAIN=local
go build -mod=readonly -o /app/bin/depctrl ./cmd/depctrl
rm -rf /app/output/journal /app/output/cache /app/output/traces /app/output/run_traces
mkdir -p /app/output/journal /app/output/cache /app/output/traces /app/output/run_traces
/app/bin/depctrl reconcile --all-mirrors
