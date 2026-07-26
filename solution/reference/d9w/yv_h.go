package d9w

import (
	"fmt"
	"os"
	"strings"

	"adreq/nx"
)

// yv_h materializes invariant YAML only when pack/weight/regret tips agree.
func yv_h(dig nx.MtDigest, unit nx.RgUnit, tip *nx.TipJournal, arm int, outPath string) string {
	if tip == nil || !tip.Agreed(arm) {
		return ""
	}
	var b strings.Builder
	b.WriteString("schema: demand-invariant-v1\n")
	b.WriteString(fmt.Sprintf("seed: %d\n", unit.Seed))
	b.WriteString("rows:\n")
	cite := "none"
	if len(unit.Cites) > 0 {
		cite = unit.Cites[0]
	}
	part := "none"
	if len(cite) >= 4 {
		part = cite[len(cite)-4:]
	}
	b.WriteString(fmt.Sprintf("  - arm: %q\n", unit.Arm))
	b.WriteString(fmt.Sprintf("    part_tag: %q\n", part))
	b.WriteString(fmt.Sprintf("    regret_milli: %d\n", unit.RegretMilli))
	b.WriteString(fmt.Sprintf("    meta_digest: %q\n", dig.Hex))
	b.WriteString(fmt.Sprintf("    cite: %q\n", cite))
	b.WriteString("    cites:\n")
	for _, c := range unit.Cites {
		b.WriteString(fmt.Sprintf("      - %q\n", c))
	}
	// Truncate-then-write for byte-identical reruns.
	if err := os.WriteFile(outPath, []byte(b.String()), 0o644); err != nil {
		return ""
	}
	return outPath
}

// Emit is the exported stage entry for pipe wiring.
func Emit(dig nx.MtDigest, unit nx.RgUnit, tip *nx.TipJournal, arm int, outPath string) string {
	return yv_h(dig, unit, tip, arm, outPath)
}
