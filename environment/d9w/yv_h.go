package d9w

import (
	"fmt"
	"os"
	"strings"

	"adreq/nx"
)

// yv_h materializes YAML without tip agreement and appends residue.
func yv_h(dig nx.MtDigest, unit nx.RgUnit, tip *nx.TipJournal, arm int, outPath string) string {
	_ = tip
	_ = arm
	f, err := os.OpenFile(outPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return ""
	}
	defer f.Close()
	var b strings.Builder
	b.WriteString("schema: demand-invariant-v1\n")
	b.WriteString(fmt.Sprintf("seed: %d\n", unit.Seed))
	b.WriteString("rows:\n")
	part := "none"
	if len(unit.Cites) > 0 {
		c := unit.Cites[0]
		if len(c) >= 4 {
			part = c[len(c)-4:]
		}
	}
	b.WriteString(fmt.Sprintf("  - arm: %q\n", unit.Arm))
	b.WriteString(fmt.Sprintf("    part_tag: %q\n", part))
	b.WriteString(fmt.Sprintf("    regret_milli: %d\n", unit.RegretMilli))
	b.WriteString(fmt.Sprintf("    meta_digest: %q\n", dig.Hex))
	b.WriteString("    cite: \"MISSING\"\n")
	b.WriteString("    cites:\n")
	for _, c := range unit.Cites {
		b.WriteString(fmt.Sprintf("      - %q\n", c))
	}
	_, _ = f.WriteString(b.String())
	return outPath
}

// Emit is the exported stage entry for pipe wiring.
func Emit(dig nx.MtDigest, unit nx.RgUnit, tip *nx.TipJournal, arm int, outPath string) string {
	return yv_h(dig, unit, tip, arm, outPath)
}
