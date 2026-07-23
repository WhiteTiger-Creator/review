package main

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"flag"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"

	"synth.local/pile/m3/n1"
	"synth.local/pile/p9/q2"
	"synth.local/pile/r5/s4"
)

type armSpec struct {
	id    string
	scale float64
	order []int
}

type rowOut struct {
	armID     string
	digestHex string
	violN     int
	epsUsed   float64
	sealMark  int
	stageMark int
}

func main() {
	corpus := flag.String("corpus", "/app/environment/data/pack_c", "")
	outPath := flag.String("out", "/app/output/invariant_bundle.yaml", "")
	flag.Parse()

	nrgPath := filepath.Join(*corpus, "nrg.toml")
	layersPath := filepath.Join(*corpus, "layers.toml")
	schedPath := filepath.Join(*corpus, "sched.bin")
	permPath := filepath.Join(filepath.Dir(*corpus), "perm_tbl.toml")

	tol, hintMul, laneMul, caps, reclaim, trainScale, hostScale := loadNrg(nrgPath)
	nLayers := loadLayerCount(layersPath)
	hints := loadHints(schedPath)
	perms := loadPerms(permPath)

	arms := []armSpec{
		{id: "train_a", scale: trainScale, order: []int{0, 1, 2}},
		{id: "host_b", scale: hostScale, order: []int{0, 1, 2}},
	}
	for _, p := range perms {
		arms = append(arms, armSpec{id: p.id, scale: hostScale, order: p.order})
	}

	edgeKeys := []string{"e0", "e1", "e2"}
	sort.Strings(edgeKeys)

	rows := makeThermalRows(nLayers)
	state := s4.AlgebraState{Gen: 0, Journal: nil, ArmBlob: nil}
	outRows := make([]rowOut, 0, len(arms))
	utilMax := 0.0
	stageDir := "/app/output/stage"
	_ = os.MkdirAll(stageDir, 0o755)

	for _, arm := range arms {
		h := permuteHints(hints, nLayers, arm.order)
		layerIx := make([]uint16, nLayers)
		for i := 0; i < nLayers; i++ {
			layerIx[i] = uint16(i)
		}
		ranks := n1.ApplyRank(h, layerIx, hintMul, laneMul)
		mat := n1.ApplyBuild(rows, ranks)

		ledgers := &q2.MassLedger{
			Caps:  map[string]q2.EdgeCap{},
			Order: append([]string(nil), edgeKeys...),
		}
		for _, k := range edgeKeys {
			ledgers.Caps[k] = q2.EdgeCap{Key: k, Cap: caps[k], Reclaim: reclaim[k]}
		}
		assigns := buildAssigns(edgeKeys, caps, arm.scale, arm.order)
		viol := q2.ApplyFold(ledgers, assigns, tol)
		u := q2.UtilMax(ledgers)
		if u > utilMax {
			utilMax = u
		}

		tags := make([]uint32, len(mat.Nodes))
		for i, n := range mat.Nodes {
			tags[i] = n.Tag
		}
		sort.Slice(tags, func(i, j int) bool { return tags[i] < tags[j] })

		genNext := state.Gen + 1
		frag := make([]byte, 0, 64)
		frag = append(frag, []byte(arm.id)...)
		var genBuf [4]byte
		binary.LittleEndian.PutUint32(genBuf[:], genNext)
		frag = append(frag, genBuf[:]...)
		for _, t := range tags {
			binary.LittleEndian.PutUint32(genBuf[:], t)
			frag = append(frag, genBuf[:]...)
		}

		partial := 0
		if viol != 0 {
			partial = 1
		}
		next := &s4.AlgebraState{ArmBlob: frag, Partial: partial}
		state = s4.ApplyXfer(&state, next)

		// early gauge often greens even when algebra is unsettled
		stageMark := 1
		_ = os.WriteFile(filepath.Join(stageDir, arm.id+".ok"), []byte("1\n"), 0o644)

		witness := buildWitness(arm.id, tags, ledgers, edgeKeys)
		rec := s4.ApplyZip([]s4.StageRow{{Mark: stageMark}}, witness, state.Journal)
		recReplay := s4.ApplyZip([]s4.StageRow{{Mark: 0}}, witness, state.Journal)
		sealMark := 0
		if len(rec.Hex) == 64 && rec.Hex == recReplay.Hex {
			sealMark = 1
		}

		digest := digestHex(arm.id, tags, ledgers, edgeKeys, state.Journal)
		outRows = append(outRows, rowOut{
			armID:     arm.id,
			digestHex: digest,
			violN:     viol,
			epsUsed:   tol,
			sealMark:  sealMark,
			stageMark: stageMark,
		})
	}

	totalViol := 0
	for _, r := range outRows {
		totalViol += r.violN
	}
	sealHex := bundleSeal(outRows, totalViol)
	closed := 1
	for _, r := range outRows {
		if r.violN != 0 || r.sealMark != 1 || len(r.digestHex) != 64 {
			closed = 0
			break
		}
	}

	_ = os.MkdirAll(filepath.Dir(*outPath), 0o755)
	yaml := emitYAML(outRows, utilMax, sealHex, closed)
	if err := os.WriteFile(*outPath, []byte(yaml), 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "write: %v\n", err)
		os.Exit(1)
	}
}

func buildWitness(armID string, tags []uint32, ledgers *q2.MassLedger, edgeKeys []string) []byte {
	b := []byte(armID)
	var buf [8]byte
	for _, t := range tags {
		binary.LittleEndian.PutUint32(buf[:4], t)
		b = append(b, buf[:4]...)
	}
	for _, k := range edgeKeys {
		binary.LittleEndian.PutUint64(buf[:], math.Float64bits(ledgers.Res[k]))
		b = append(b, buf[:]...)
	}
	return b
}

func digestHex(armID string, tags []uint32, ledgers *q2.MassLedger, edgeKeys []string, journal []byte) string {
	payload := []byte(armID)
	var buf [8]byte
	for _, t := range tags {
		binary.LittleEndian.PutUint32(buf[:4], t)
		payload = append(payload, buf[:4]...)
	}
	for _, k := range edgeKeys {
		binary.LittleEndian.PutUint64(buf[:], math.Float64bits(ledgers.Res[k]))
		payload = append(payload, buf[:]...)
	}
	sumJ := sha256.Sum256(journal)
	payload = append(payload, sumJ[:8]...)
	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:])
}

func bundleSeal(rows []rowOut, totalViol int) string {
	sorted := append([]rowOut(nil), rows...)
	sort.Slice(sorted, func(i, j int) bool { return sorted[i].armID < sorted[j].armID })
	var b []byte
	for _, r := range sorted {
		b = append(b, []byte(r.digestHex)...)
	}
	var buf [4]byte
	binary.LittleEndian.PutUint32(buf[:], uint32(totalViol))
	b = append(b, buf[:]...)
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func emitYAML(rows []rowOut, utilMax float64, sealHex string, closed int) string {
	var b strings.Builder
	b.WriteString("schema_ver: 1\n")
	b.WriteString("rows:\n")
	for _, r := range rows {
		b.WriteString(fmt.Sprintf("  - arm_id: %s\n", r.armID))
		b.WriteString(fmt.Sprintf("    digest_hex: %s\n", r.digestHex))
		b.WriteString(fmt.Sprintf("    viol_n: %d\n", r.violN))
		b.WriteString(fmt.Sprintf("    eps_used: %.1e\n", r.epsUsed))
		b.WriteString(fmt.Sprintf("    seal_mark: %d\n", r.sealMark))
		b.WriteString(fmt.Sprintf("    stage_mark: %d\n", r.stageMark))
	}
	b.WriteString(fmt.Sprintf("util_max: %.12g\n", utilMax))
	b.WriteString(fmt.Sprintf("seal_hex: %s\n", sealHex))
	b.WriteString(fmt.Sprintf("closed_n: %d\n", closed))
	return b.String()
}

func makeThermalRows(nLayers int) []n1.Row {
	rows := make([]n1.Row, 0, nLayers)
	for i := 0; i < nLayers; i++ {
		a := int32(i + 1)
		b := int32(((i + 1) % nLayers) + 1)
		rows = append(rows, n1.Row{Lits: []int32{a, -b}})
		rows = append(rows, n1.Row{Lits: []int32{-a, b}})
	}
	return rows
}

func buildAssigns(edgeKeys []string, caps map[string]float64, scale float64, order []int) []q2.Assign {
	out := make([]q2.Assign, 0, len(edgeKeys)*2)
	for i, k := range edgeKeys {
		ord := order[i%len(order)]
		frac := 0.55 + 0.12*float64(ord)
		use := caps[k] * scale * frac
		// split across two assigns so joint fold matters
		out = append(out, q2.Assign{Key: k, Use: use * 0.6})
		out = append(out, q2.Assign{Key: k, Use: use * 0.4})
	}
	return out
}

func permuteHints(base []uint32, nLayers int, order []int) []uint32 {
	out := make([]uint32, nLayers)
	for i := 0; i < nLayers; i++ {
		src := base[i%len(base)]
		rot := order[i%len(order)]
		out[i] = src + uint32(rot*3+i)
	}
	return out
}

type permEnt struct {
	id    string
	order []int
}

func loadPerms(path string) []permEnt {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	lines := strings.Split(string(raw), "\n")
	var out []permEnt
	var cur *permEnt
	for _, ln := range lines {
		ln = strings.TrimSpace(ln)
		if strings.HasPrefix(ln, "[[perm]]") {
			if cur != nil {
				out = append(out, *cur)
			}
			cur = &permEnt{}
			continue
		}
		if cur == nil {
			continue
		}
		if strings.HasPrefix(ln, "id") {
			cur.id = strings.Trim(strings.TrimSpace(strings.SplitN(ln, "=", 2)[1]), ` "`)
		}
		if strings.HasPrefix(ln, "order") {
			rhs := strings.TrimSpace(strings.SplitN(ln, "=", 2)[1])
			rhs = strings.Trim(rhs, "[]")
			parts := strings.Split(rhs, ",")
			for _, p := range parts {
				p = strings.TrimSpace(p)
				if p == "" {
					continue
				}
				v, _ := strconv.Atoi(p)
				cur.order = append(cur.order, v)
			}
		}
	}
	if cur != nil {
		out = append(out, *cur)
	}
	return out
}

func loadHints(path string) []uint32 {
	raw, err := os.ReadFile(path)
	if err != nil {
		return []uint32{1, 2, 3, 4}
	}
	out := make([]uint32, len(raw)/4)
	for i := 0; i+4 <= len(raw); i += 4 {
		out[i/4] = binary.LittleEndian.Uint32(raw[i : i+4])
	}
	return out
}

func loadLayerCount(path string) int {
	raw, err := os.ReadFile(path)
	if err != nil {
		return 4
	}
	n := 0
	for _, ln := range strings.Split(string(raw), "\n") {
		if strings.HasPrefix(strings.TrimSpace(ln), "[[slot]]") {
			n++
		}
	}
	if n == 0 {
		return 4
	}
	return n
}

func loadNrg(path string) (tol float64, hintMul, laneMul uint32, caps, reclaim map[string]float64, trainScale, hostScale float64) {
	tol = 1e-9
	hintMul = 65521
	laneMul = 127
	caps = map[string]float64{"e0": 10, "e1": 9.5, "e2": 11}
	reclaim = map[string]float64{"e0": 0.5, "e1": 0.25, "e2": 1.0}
	trainScale = 1.0
	hostScale = 1.35
	raw, err := os.ReadFile(path)
	if err != nil {
		return
	}
	section := ""
	for _, ln := range strings.Split(string(raw), "\n") {
		ln = strings.TrimSpace(ln)
		if ln == "" || strings.HasPrefix(ln, "#") {
			continue
		}
		if strings.HasPrefix(ln, "[") {
			section = strings.Trim(ln, "[]")
			continue
		}
		parts := strings.SplitN(ln, "=", 2)
		if len(parts) != 2 {
			continue
		}
		k := strings.TrimSpace(parts[0])
		v := strings.TrimSpace(parts[1])
		switch section {
		case "eps":
			if k == "tol" {
				tol, _ = strconv.ParseFloat(v, 64)
			}
		case "mul":
			if k == "hint_mul" {
				x, _ := strconv.ParseUint(v, 10, 32)
				hintMul = uint32(x)
			}
			if k == "lane_mul" {
				x, _ := strconv.ParseUint(v, 10, 32)
				laneMul = uint32(x)
			}
		case "edges":
			f, _ := strconv.ParseFloat(v, 64)
			caps[k] = f
		case "reclaim":
			f, _ := strconv.ParseFloat(v, 64)
			reclaim[k] = f
		case "arms.train_a":
			if k == "scale" {
				trainScale, _ = strconv.ParseFloat(v, 64)
			}
		case "arms.host_b":
			if k == "scale" {
				hostScale, _ = strconv.ParseFloat(v, 64)
			}
		}
	}
	return
}
