package main

import (
	"fmt"
	"os"

	"stormlab/k4/graph"
	"stormlab/ld"
	"stormlab/m2/limit"
	"stormlab/p8/g9"
	"stormlab/pol"
)

func fail(msg string) int {
	fmt.Fprintf(os.Stderr, "lib_probe: %s\n", msg)
	return 1
}

func installRadius(r int, gen int) {
	pol.InstallForProbe(pol.Overlay{
		Gen:          gen,
		ShadowRadius: r,
		PolicyID:     "probe",
		Path:         "probe",
	})
}

func checkQ7() int {
	installRadius(2, 99)
	arms := graph.EdgeArms{
		Items: []graph.EdgeArm{
			{ID: 1, Kind: graph.ArmInclude, Mask: 0x00FF, Seq: 2},
			{ID: 4, Kind: graph.ArmInclude, Mask: 0x00FF, Seq: 3},
			{ID: 9, Kind: graph.ArmExclude, Mask: 0x000F, ShadowLink: 1, Seq: 1},
		},
	}
	var sink graph.ShadowSink
	if err := graph.Run(&arms, &sink); err != nil {
		return fail(fmt.Sprintf("graph.Run: %v", err))
	}
	for _, id := range sink.Active {
		if id == 4 {
			return fail("graph.Run kept include arm 4 after overlap suppression")
		}
	}
	if len(sink.Active) != 1 || sink.Active[0] != 1 {
		return fail(fmt.Sprintf("graph.Run active=%v want [1]", sink.Active))
	}
	return 0
}

func checkQ8() int {
	installRadius(2, 99)
	arms := graph.EdgeArms{
		Items: []graph.EdgeArm{
			{ID: 2, Kind: graph.ArmInclude, Mask: 0x000F, Seq: 2},
			{ID: 9, Kind: graph.ArmExclude, Mask: 0x000F, ShadowLink: 1, Seq: 1},
		},
	}
	var sink graph.ShadowSink
	if err := graph.Run(&arms, &sink); err != nil {
		return fail(fmt.Sprintf("graph.Run distance: %v", err))
	}
	if len(sink.Active) != 1 || sink.Active[0] != 2 {
		return fail(fmt.Sprintf("graph.Run distance active=%v want [2]", sink.Active))
	}
	return 0
}

func checkQ9() int {
	installRadius(2, 99)
	arms := graph.EdgeArms{
		Items: []graph.EdgeArm{
			{ID: 5, Kind: graph.ArmInclude, Mask: 0x00FF, Seq: 1},
			{ID: 9, Kind: graph.ArmExclude, Mask: 0x00FF, ShadowLink: 1, Seq: 2},
			{ID: 1, Kind: graph.ArmInclude, Mask: 0x00FF, Seq: 3},
		},
	}
	var sink graph.ShadowSink
	if err := graph.Run(&arms, &sink); err != nil {
		return fail(fmt.Sprintf("graph.Run seq: %v", err))
	}
	for _, id := range sink.Active {
		if id == 5 {
			return fail("graph.Run seq kept include arm 5 after exclude-first pass")
		}
	}
	if len(sink.Active) != 1 || sink.Active[0] != 1 {
		return fail(fmt.Sprintf("graph.Run seq active=%v want [1]", sink.Active))
	}
	return 0
}

func checkQ10() int {
	grid := limit.BurstGrid{
		Cells:       []limit.BurstCell{{ArmID: 7, Mask: 0x0003}},
		Family:      "probe_a",
		PolicyGen:   0,
		ShadowEpoch: 11,
	}
	events := limit.EventBatch{
		Rows: []limit.EventRow{{FieldByte: 0x01}, {FieldByte: 0x02}, {FieldByte: 0x04}},
	}
	if err := limit.Run(&grid, &events); err != nil {
		return fail(fmt.Sprintf("limit.Run: %v", err))
	}
	if grid.Cells[0].Hits != 2 {
		return fail(fmt.Sprintf("limit.Run hits=%d want 2", grid.Cells[0].Hits))
	}
	if grid.CacheEpoch != grid.ShadowEpoch {
		return fail(fmt.Sprintf("limit.Run cache_epoch=%d shadow_epoch=%d", grid.CacheEpoch, grid.ShadowEpoch))
	}
	return 0
}

func checkQ11() int {
	grid := limit.BurstGrid{
		Cells:       []limit.BurstCell{{ArmID: 1, Mask: 0x01}},
		Family:      "probe_evt",
		PolicyGen:   0,
		ShadowEpoch: 5,
	}
	events := limit.EventBatch{
		Rows: []limit.EventRow{{FieldByte: 0x01}},
	}
	if err := limit.Run(&grid, &events); err != nil {
		return fail(fmt.Sprintf("limit.Run eventbytes first: %v", err))
	}
	grid2 := limit.BurstGrid{
		Cells:       []limit.BurstCell{{ArmID: 1, Mask: 0x01}},
		Family:      "probe_evt",
		PolicyGen:   0,
		ShadowEpoch: 5,
	}
	events2 := limit.EventBatch{
		Rows: []limit.EventRow{{FieldByte: 0x02}},
	}
	if err := limit.Run(&grid2, &events2); err != nil {
		return fail(fmt.Sprintf("limit.Run eventbytes second: %v", err))
	}
	if grid2.Cells[0].Hits != 0 {
		return fail(fmt.Sprintf("limit.Run reused hits=%d want 0 after event byte change", grid2.Cells[0].Hits))
	}
	return 0
}

func checkQ12() int {
	grid := limit.BurstGrid{
		Cells:       []limit.BurstCell{{ArmID: 1, Mask: 0x01}},
		Family:      "probe_stale",
		PolicyGen:   0,
		ShadowEpoch: 2,
	}
	events := limit.EventBatch{
		Rows: []limit.EventRow{{FieldByte: 0x01}},
	}
	if err := limit.Run(&grid, &events); err != nil {
		return fail(fmt.Sprintf("limit.Run first: %v", err))
	}
	grid2 := limit.BurstGrid{
		Cells:       []limit.BurstCell{{ArmID: 2, Mask: 0x02}},
		Family:      "probe_stale",
		PolicyGen:   0,
		ShadowEpoch: 3,
	}
	events2 := limit.EventBatch{
		Rows: []limit.EventRow{{FieldByte: 0x01}},
	}
	if err := limit.Run(&grid2, &events2); err != nil {
		return fail(fmt.Sprintf("limit.Run second: %v", err))
	}
	if grid2.Cells[0].Hits != 0 {
		return fail(fmt.Sprintf("limit.Run reused stale hits=%d want 0", grid2.Cells[0].Hits))
	}
	return 0
}

func checkQ13() int {
	installRadius(2, 99)
	stagingPath := "/app/environment/pack/seed/.anchor_staging"
	original, _ := os.ReadFile(stagingPath)
	defer func() {
		if original != nil {
			_ = os.WriteFile(stagingPath, original, 0o644)
		}
	}()
	staging := []byte("HOTSTG01")
	if err := os.WriteFile(stagingPath, staging, 0o644); err != nil {
		return fail(fmt.Sprintf("staging write: %v", err))
	}
	grid := g9.ScoreGrid{
		Scores: []g9.LaneScore{
			{ID: 5, Score: 10},
			{ID: 6, Score: 10},
		},
	}
	var out g9.OrderSink
	if err := g9.Run(g9.SlotBudget{Slots: 2}, &grid, &out); err != nil {
		return fail(fmt.Sprintf("g9.Run: %v", err))
	}
	if len(out.LaneOrder) != 2 {
		return fail(fmt.Sprintf("g9.Run lane_order=%v want len 2", out.LaneOrder))
	}
	if out.LaneOrder[0] != 5 || out.LaneOrder[1] != 6 {
		return fail(fmt.Sprintf("g9.Run lane_order=%v want [5 6] from staged anchor tie-break", out.LaneOrder))
	}
	want := g9.ReadStagedAnchor()
	if out.Anchor != want {
		return fail("g9.Run anchor staging tail not preserved")
	}
	var wantArr [8]byte
	copy(wantArr[:], staging)
	if want != wantArr {
		return fail("g9.ReadStagedAnchor did not load staged bytes")
	}
	return 0
}

func checkQ14() int {
	installRadius(2, 99)
	stagingPath := "/app/environment/pack/seed/.anchor_staging"
	original, _ := os.ReadFile(stagingPath)
	defer func() {
		if original != nil {
			_ = os.WriteFile(stagingPath, original, 0o644)
		}
	}()
	staging := []byte("HOTSTG01")
	if err := os.WriteFile(stagingPath, staging, 0o644); err != nil {
		return fail(fmt.Sprintf("staging write budgettie: %v", err))
	}
	grid := g9.ScoreGrid{
		Scores: []g9.LaneScore{
			{ID: 5, Score: 10},
			{ID: 6, Score: 10},
		},
	}
	var out g9.OrderSink
	if err := g9.Run(g9.SlotBudget{Slots: 1}, &grid, &out); err != nil {
		return fail(fmt.Sprintf("g9.Run budgettie: %v", err))
	}
	if len(out.LaneOrder) != 1 || out.LaneOrder[0] != 5 {
		return fail(fmt.Sprintf("g9.Run budgettie lane_order=%v want [5]", out.LaneOrder))
	}
	return 0
}

func checkQ15() int {
	events := limit.EventBatch{
		Rows: []limit.EventRow{{FieldByte: 0x01}, {FieldByte: 0x01}},
	}
	gridA := limit.BurstGrid{
		Cells:       []limit.BurstCell{{ArmID: 1, Mask: 0x01}},
		Family:      "fam_alpha",
		PolicyGen:   0,
		ShadowEpoch: 9,
	}
	if err := limit.Run(&gridA, &events); err != nil {
		return fail(fmt.Sprintf("limit.Run fam_alpha: %v", err))
	}
	if gridA.Cells[0].Hits != 2 {
		return fail(fmt.Sprintf("limit.Run fam_alpha hits=%d want 2", gridA.Cells[0].Hits))
	}
	gridB := limit.BurstGrid{
		Cells:       []limit.BurstCell{{ArmID: 1, Mask: 0x02}},
		Family:      "fam_beta",
		PolicyGen:   0,
		ShadowEpoch: 9,
	}
	if err := limit.Run(&gridB, &events); err != nil {
		return fail(fmt.Sprintf("limit.Run fam_beta: %v", err))
	}
	if gridB.Cells[0].Hits != 0 {
		return fail(fmt.Sprintf("limit.Run fam_beta reused hits=%d want 0 across family tags", gridB.Cells[0].Hits))
	}
	if gridB.CacheEpoch != gridB.ShadowEpoch {
		return fail(fmt.Sprintf("limit.Run fam_beta cache_epoch=%d want %d", gridB.CacheEpoch, gridB.ShadowEpoch))
	}
	return 0
}

func checkQ16() int {
	// Held-out radius: abs(id-link)=2 must survive R=3 and suppress at R=2.
	installRadius(3, 99)
	arms := graph.EdgeArms{
		Items: []graph.EdgeArm{
			{ID: 1, Kind: graph.ArmInclude, Mask: 0x00FF, Seq: 2},
			{ID: 3, Kind: graph.ArmInclude, Mask: 0x00FF, Seq: 3},
			{ID: 9, Kind: graph.ArmExclude, Mask: 0x000F, ShadowLink: 1, Seq: 1},
		},
	}
	var sink graph.ShadowSink
	if err := graph.Run(&arms, &sink); err != nil {
		return fail(fmt.Sprintf("graph.Run radius3: %v", err))
	}
	if len(sink.Active) != 2 {
		return fail(fmt.Sprintf("graph.Run radius3 active=%v want both includes", sink.Active))
	}
	installRadius(2, 99)
	var sink2 graph.ShadowSink
	if err := graph.Run(&arms, &sink2); err != nil {
		return fail(fmt.Sprintf("graph.Run radius2: %v", err))
	}
	for _, id := range sink2.Active {
		if id == 3 {
			return fail("graph.Run radius2 kept include 3")
		}
	}
	return 0
}

func checkQ17() int {
	tip, err := ld.Run()
	if err != nil {
		return fail(fmt.Sprintf("ld.Run: %v", err))
	}
	if tip != 0 {
		return fail(fmt.Sprintf("ld.Run tip=%d want 0 (tombstoned gen1 ignored)", tip))
	}
	ov, err := pol.Run(tip)
	if err != nil {
		return fail(fmt.Sprintf("pol.Run: %v", err))
	}
	if ov.Gen != 0 || ov.ShadowRadius != 2 || ov.PolicyID != "ov_base" {
		return fail(fmt.Sprintf("pol.Run overlay=%+v want gen0 radius2 ov_base", ov))
	}
	return 0
}

func checkQ18() int {
	events := limit.EventBatch{
		Rows: []limit.EventRow{{FieldByte: 0x01}},
	}
	gridA := limit.BurstGrid{
		Cells:       []limit.BurstCell{{ArmID: 1, Mask: 0x01}},
		Family:      "fam_pol",
		PolicyGen:   0,
		ShadowEpoch: 4,
	}
	if err := limit.Run(&gridA, &events); err != nil {
		return fail(fmt.Sprintf("limit.Run pol0: %v", err))
	}
	gridB := limit.BurstGrid{
		Cells:       []limit.BurstCell{{ArmID: 1, Mask: 0x02}},
		Family:      "fam_pol",
		PolicyGen:   1,
		ShadowEpoch: 4,
	}
	if err := limit.Run(&gridB, &events); err != nil {
		return fail(fmt.Sprintf("limit.Run pol1: %v", err))
	}
	if gridB.Cells[0].Hits != 0 {
		return fail(fmt.Sprintf("limit.Run pol1 reused hits=%d want 0 across PolicyGen", gridB.Cells[0].Hits))
	}
	return 0
}

var probeChecks = map[string]func() int{
	"q7":  checkQ7,
	"q8":  checkQ8,
	"q9":  checkQ9,
	"q10": checkQ10,
	"q11": checkQ11,
	"q12": checkQ12,
	"q13": checkQ13,
	"q14": checkQ14,
	"q15": checkQ15,
	"q16": checkQ16,
	"q17": checkQ17,
	"q18": checkQ18,
}

func main() {
	if len(os.Args) > 1 {
		name := os.Args[1]
		fn, ok := probeChecks[name]
		if !ok {
			fmt.Fprintf(os.Stderr, "lib_probe: unknown check %q\n", name)
			os.Exit(1)
		}
		if fn() != 0 {
			os.Exit(1)
		}
		fmt.Printf("lib_probe %s ok\n", name)
		return
	}
	failures := 0
	for _, name := range []string{"q7", "q8", "q9", "q10", "q11", "q12", "q13", "q14", "q15", "q16", "q17", "q18"} {
		failures += probeChecks[name]()
	}
	if failures != 0 {
		os.Exit(1)
	}
	fmt.Println("lib_probe ok")
}
