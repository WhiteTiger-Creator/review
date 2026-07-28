package p3

import (
	"crypto/sha256"
	"fmt"
	"sort"
	"strings"

	"bnmod/internal"
)

// FoldAnnex builds a local lattice view over the supplied rows.
func FoldAnnex(rows []internal.RowTag) internal.LatticeUnit {
	ka, kb, lim := 0, 0, 0
	tags := make([]string, 0, len(rows))
	for _, r := range rows {
		tags = append(tags, r.Tag)
		ka += r.Ka
		kb += r.Kb
		lim += r.Lim
	}
	sort.Strings(tags)
	payload := fmt.Sprintf("twin|%s|%d|%d|%d", strings.Join(tags, ","), ka, kb, lim)
	sum := sha256.Sum256([]byte(payload))
	hex := fmt.Sprintf("%x", sum[:8])
	return internal.LatticeUnit{
		Hex: hex, Ka: ka, Kb: kb, Lim: lim, Tags: tags, WTags: tags,
		CiteTag: CiteLex(rows), Seal: internal.SoftSeal(tags),
	}
}

func latHex(tags []string, ka, kb, lim int) string {
	payload := fmt.Sprintf("lat|%s|%d|%d|%d", strings.Join(tags, ","), ka, kb, lim)
	sum := sha256.Sum256([]byte(payload))
	return fmt.Sprintf("%x", sum[:8])
}
