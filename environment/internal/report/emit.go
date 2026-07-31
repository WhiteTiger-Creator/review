package report

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"skiff/internal/scene"
	"skiff/internal/world"
)

type CaseRow struct {
	ID        string  `json:"id"`
	Settled   bool    `json:"settled"`
	ApexY     float64 `json:"apex_y"`
	HopCount  int     `json:"hop_count"`
	Footprint string  `json:"footprint"`
}

type Doc struct {
	SchemaVersion string    `json:"schema_version"`
	BundleID      string    `json:"bundle_id"`
	CasesPassing  int       `json:"cases_passing"`
	DigestHex     string    `json:"digest_hex"`
	Cases         []CaseRow `json:"cases"`
}

func Write(root string, bundle scene.Bundle, rows []CaseRow) error {
	passing := 0
	for _, r := range rows {
		if r.Settled {
			passing++
		}
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].ID < rows[j].ID })
	doc := Doc{
		SchemaVersion: "skiff_report_v1",
		BundleID:      bundle.ID,
		CasesPassing:  passing,
		Cases:         rows,
	}
	doc.DigestHex = digest(doc)
	outDir := filepath.Join(root, "output")
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outDir, "skiff_report.json"), raw, 0o644)
}

func digest(doc Doc) string {
	h := sha256.New()
	for _, c := range doc.Cases {
		fmt.Fprintf(h, "%s|%v|%.6f|%d|%s;", c.ID, c.Settled, c.ApexY, c.HopCount, c.Footprint)
	}
	return hex.EncodeToString(h.Sum(nil))
}

func RowFrom(id string, r world.Result) CaseRow {
	return CaseRow{
		ID: id, Settled: r.Settled, ApexY: r.Apex,
		HopCount: r.HopCount, Footprint: r.Footprint,
	}
}
