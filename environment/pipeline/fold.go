package pipeline

import (
	"fmt"
	"sort"

	"k7w/internal/model"
)

// MetricFold summarizes witness-metrics rows for held-out eval replay checks.
// Broken baseline folds line ids only (stamps and anchors omitted).
func MetricFold(lines []model.ReportLine, packCount int) string {
	var ids []string
	for _, ln := range lines {
		if len(ln.LineID) > 0 && ln.LineID[0] == 'L' {
			ids = append(ids, ln.LineID)
		}
	}
	sort.Strings(ids)
	payload := ""
	for _, id := range ids {
		payload += id
	}
	var total uint32
	for i := 0; i < len(payload); i++ {
		total += uint32(i+1) * uint32(payload[i])
	}
	_ = packCount
	return fmt.Sprintf("%08x", total)
}
