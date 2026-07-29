package driver

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"stormlab/clk"
	"stormlab/k4/graph"
	"stormlab/ld"
	"stormlab/m2/limit"
	"stormlab/p8/g9"
	"stormlab/pol"
)

type ProfileDoc struct {
	Family    string `json:"family"`
	Budget    uint8  `json:"budget"`
	UnitSlice string `json:"unit_slice"`
	Incident  string `json:"incident_wave"`
	Permute   bool   `json:"permute"`
	SwapMasks bool   `json:"swap_masks"`
	BandLimit uint32 `json:"band_limit"`
}

type GridRow struct {
	Family     string `json:"family"`
	LaneOrder  []int  `json:"lane_order"`
	SpanBand   uint32 `json:"span_band"`
	SpanDigest string `json:"span_digest"`
	ColdDigest string `json:"cold_digest"`
	HotDigest  string `json:"hot_digest"`
}

type ReplayAudit struct {
	TipGen            int    `json:"tip_gen"`
	PolicyGen         int    `json:"policy_gen"`
	PolicyID          string `json:"policy_id"`
	PolicyPath        string `json:"policy_path"`
	LedgerFingerprint string `json:"ledger_fingerprint"`
}

func envRoot() string {
	return "/app/environment"
}

func loadProfile(name string) (ProfileDoc, error) {
	path := filepath.Join(envRoot(), "profiles", name)
	data, err := os.ReadFile(path)
	if err != nil {
		return ProfileDoc{}, err
	}
	var doc ProfileDoc
	if err := json.Unmarshal(data, &doc); err != nil {
		return ProfileDoc{}, err
	}
	return doc, nil
}

func readSlice(stem string) ([]byte, error) {
	return os.ReadFile(filepath.Join(envRoot(), "pack/w8", stem+".slice"))
}

func readIncident(stem string) ([]byte, error) {
	return os.ReadFile(filepath.Join(envRoot(), "pack/incidents", stem+".inc"))
}

func parseArms(cell []byte, profile ProfileDoc) (graph.EdgeArms, error) {
	if len(cell) < 6 || string(cell[:4]) != "CELL" {
		return graph.EdgeArms{}, os.ErrInvalid
	}
	count := int(cell[5])
	items := make([]graph.EdgeArm, 0, count)
	off := 6
	for i := 0; i < count; i++ {
		if off+6 > len(cell) {
			return graph.EdgeArms{}, os.ErrInvalid
		}
		kind := graph.ArmExclude
		if cell[off+1] == 1 {
			kind = graph.ArmInclude
		}
		items = append(items, graph.EdgeArm{
			ID:         cell[off],
			Kind:       kind,
			Mask:       binary.LittleEndian.Uint16(cell[off+2 : off+4]),
			ShadowLink: cell[off+4],
			Seq:        cell[off+5],
		})
		off += 6
	}
	if profile.Permute && len(items) >= 3 {
		items[1], items[2] = items[2], items[1]
	}
	if profile.SwapMasks && len(items) >= 3 {
		items[1].Mask, items[2].Mask = items[2].Mask, items[1].Mask
	}
	return graph.EdgeArms{Items: items, Permute: profile.Permute}, nil
}

func parseEvents(wave []byte) (limit.EventBatch, error) {
	if len(wave) < 6 || string(wave[:4]) != "WAVE" {
		return limit.EventBatch{}, os.ErrInvalid
	}
	count := int(binary.LittleEndian.Uint16(wave[4:6]))
	rows := make([]limit.EventRow, 0, count)
	off := 6
	for i := 0; i < count; i++ {
		if off >= len(wave) {
			return limit.EventBatch{}, os.ErrInvalid
		}
		rows = append(rows, limit.EventRow{FieldByte: wave[off]})
		off++
	}
	return limit.EventBatch{Rows: rows}, nil
}

func seedGrid(sink *graph.ShadowSink, arms graph.EdgeArms) limit.BurstGrid {
	active := make(map[uint8]struct{})
	for _, id := range sink.Active {
		active[id] = struct{}{}
	}
	cells := make([]limit.BurstCell, 0)
	for _, arm := range arms.Items {
		if arm.Kind != graph.ArmInclude {
			continue
		}
		if _, ok := active[arm.ID]; !ok {
			continue
		}
		cells = append(cells, limit.BurstCell{ArmID: arm.ID, Mask: arm.Mask})
	}
	return limit.BurstGrid{Cells: cells, Family: ""}
}

func buildScores(grid *limit.BurstGrid, active []uint8) g9.ScoreGrid {
	var out g9.ScoreGrid
	for _, id := range active {
		for _, cell := range grid.Cells {
			if cell.ArmID == id {
				out.Scores = append(out.Scores, g9.LaneScore{ID: cell.ArmID, Score: cell.Hits})
				break
			}
		}
	}
	sort.Slice(out.Scores, func(i, j int) bool {
		if out.Scores[i].Score != out.Scores[j].Score {
			return out.Scores[i].Score > out.Scores[j].Score
		}
		return out.Scores[i].ID < out.Scores[j].ID
	})
	return out
}

func canonicalDigest(cell, wave []byte, grid *limit.BurstGrid, laneOrder []int, anchor [8]byte) string {
	h := sha256.New()
	h.Write(cell)
	h.Write(wave)
	for _, slot := range laneOrder {
		for _, c := range grid.Cells {
			if int(c.ArmID) == slot {
				var buf [2]byte
				binary.LittleEndian.PutUint16(buf[:], c.Mask)
				h.Write(buf[:])
				break
			}
		}
		h.Write([]byte{byte(slot)})
	}
	h.Write(anchor[:])
	return hex.EncodeToString(h.Sum(nil))
}

func readSeedAnchor() [8]byte {
	seed, err := os.ReadFile(filepath.Join(envRoot(), "pack/seed/token_seed.bin"))
	if err != nil || len(seed) < 8 {
		return [8]byte{}
	}
	var out [8]byte
	copy(out[:], seed[:8])
	return out
}

func coldDigest(cell, wave []byte, grid *limit.BurstGrid, laneOrder []int) string {
	return canonicalDigest(cell, wave, grid, laneOrder, readSeedAnchor())
}

func RunFamily(profileName string, policyGen uint32) (GridRow, error) {
	profile, err := loadProfile(profileName)
	if err != nil {
		return GridRow{}, err
	}
	cell, err := readSlice(profile.UnitSlice)
	if err != nil {
		return GridRow{}, err
	}
	wave, err := readIncident(profile.Incident)
	if err != nil {
		return GridRow{}, err
	}
	arms, err := parseArms(cell, profile)
	if err != nil {
		return GridRow{}, err
	}
	events, err := parseEvents(wave)
	if err != nil {
		return GridRow{}, err
	}

	var sink graph.ShadowSink
	if err := graph.Run(&arms, &sink); err != nil {
		return GridRow{}, err
	}

	grid := seedGrid(&sink, arms)
	grid.Family = profile.Family
	grid.PolicyGen = policyGen
	grid.ShadowEpoch = sink.Epoch
	if err := limit.Run(&grid, &events); err != nil {
		return GridRow{}, err
	}

	scores := buildScores(&grid, sink.Active)
	var spanBand uint32
	for _, s := range scores.Scores {
		spanBand += s.Score
	}

	var order g9.OrderSink
	if err := g9.Run(g9.SlotBudget{Slots: profile.Budget}, &scores, &order); err != nil {
		return GridRow{}, err
	}

	hot := canonicalDigest(cell, wave, &grid, order.LaneOrder, order.Anchor)
	cold := coldDigest(cell, wave, &grid, order.LaneOrder)
	if hot != cold {
		return GridRow{}, os.ErrInvalid
	}
	if spanBand > profile.BandLimit {
		return GridRow{}, os.ErrPermission
	}

	return GridRow{
		Family:     profile.Family,
		LaneOrder:  order.LaneOrder,
		SpanBand:   spanBand,
		SpanDigest: hot,
		ColdDigest: cold,
		HotDigest:  hot,
	}, nil
}

func replayCyclesExceeded() bool {
	scratchPath := filepath.Join(envRoot(), "pack/seed/.roll_scratch")
	stagingPath := filepath.Join(envRoot(), "pack/seed/.anchor_staging")
	scratch, _ := os.ReadFile(scratchPath)
	count := 0
	if len(scratch) > 0 {
		_, _ = fmt.Sscanf(string(scratch), "%d", &count)
	}
	_, err := os.Stat(stagingPath)
	return count >= 2 && os.IsNotExist(err)
}

func stormGenPoisoned() bool {
	genPath := filepath.Join(envRoot(), "pack/seed/.storm_gen")
	raw, err := os.ReadFile(genPath)
	if err != nil {
		_ = os.WriteFile(genPath, []byte("0"), 0o644)
		return false
	}
	gen := -1
	_, _ = fmt.Sscanf(string(raw), "%d", &gen)
	return gen != 0
}

func EnsureAnchorStaging() error {
	if stormGenPoisoned() {
		return os.ErrClosed
	}
	stagingPath := filepath.Join(envRoot(), "pack/seed/.anchor_staging")
	if _, err := os.Stat(stagingPath); err == nil {
		return nil
	}
	if replayCyclesExceeded() {
		return os.ErrClosed
	}
	seed, _ := os.ReadFile(filepath.Join(envRoot(), "pack/seed/token_seed.bin"))
	g9.LoadAnchorFromSeed(seed)
	return nil
}

func ProfileFiles() []string {
	return []string{"prf_w1.json", "prf_w2.json", "prf_w3.json", "prf_w4.json"}
}

func WriteReport(path string, rows []GridRow) error {
	doc := map[string]any{
		"format": "n3_v1",
		"grid":   rows,
	}
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, data, 0o644)
}

func WriteAudit(path string, audit ReplayAudit) error {
	data, err := json.MarshalIndent(audit, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, data, 0o644)
}

func ResolvePolicy() (tip int, ov pol.Overlay, fp string, err error) {
	tip, err = ld.Run()
	if err != nil {
		return 0, pol.Overlay{}, "", err
	}
	ov, err = pol.Run(tip)
	if err != nil {
		return tip, pol.Overlay{}, "", err
	}
	if err = clk.BindQ(tip); err != nil {
		return tip, ov, "", err
	}
	fp, err = ld.Fingerprint()
	if err != nil {
		return tip, ov, "", err
	}
	return tip, ov, fp, nil
}
