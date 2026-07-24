package main

import (
	"encoding/json"
	"os"
	"path/filepath"

	"depctrl/h2n"
	"depctrl/w3j"
	"depctrl/x8c"
	"depctrl/y4f"
)

func runSealAndFold() error {
	frames, err := runSeal()
	if err != nil {
		return err
	}
	return runFold(frames)
}

func runFold(frames []w3j.Frame) error {
	if err := ensureOut(); err != nil {
		return err
	}
	graph, toggles, err := loadSeedGraph()
	if err != nil {
		return err
	}
	seedJSON, err := os.ReadFile(filepath.Join(dataRoot, "seed_lock.json"))
	if err != nil {
		return err
	}
	actJSON, err := os.ReadFile(filepath.Join(dataRoot, "act_map.json"))
	if err != nil {
		return err
	}
	probeSrc := filepath.Join(dataRoot, "events", "m_h.jsonl")
	peerView, err := h2n.LoadPeerCaps(probeSrc)
	if err != nil {
		return err
	}
	peerFP := h2n.FingerprintPeers(peerView)
	mat := x8c.Material{
		SeedJSON:   seedJSON,
		ActJSON:    actJSON,
		Frames:     frames,
		PeerFinger: peerFP,
	}
	dec, err := x8c.FnX8(graph, toggles, mat, cacheDir)
	if err != nil {
		return err
	}

	var rows []y4f.RowOut
	if dec.Hit && len(dec.RowsRaw) > 0 {
		if err := json.Unmarshal(dec.RowsRaw, &rows); err != nil {
			return err
		}
	} else {
		allowed := map[string]bool{}
		for _, e := range dec.Edges {
			allowed[e.Pkg+"\x00"+e.Dep] = true
		}
		pv := y4f.ProbeView{PeerHi: peerView.PeerHi}
		rows, err = y4f.FnY4(frames, allowed, pv)
		if err != nil {
			return err
		}
		rowsJSON, err := json.Marshal(rows)
		if err != nil {
			return err
		}
		blob, err := x8c.WrapCacheBlob(peerFP, rowsJSON)
		if err != nil {
			return err
		}
		if dec.KeyHex != "" {
			_ = x8c.PutCache(cacheDir, dec.KeyHex, blob)
		}
	}

	report := map[string]any{"rows": rows}
	if rows == nil {
		report["rows"] = []y4f.RowOut{}
	}
	if err := writeJSON(stagingPath, report); err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(traceDir, "last_run.json"), map[string]any{
		"cache_hit": dec.Hit,
		"row_n":     len(rows),
		"frame_n":   len(frames),
	}); err != nil {
		return err
	}
	return writeJSON(reportPath, report)
}
