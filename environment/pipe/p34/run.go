package p34

import (
	"adreq/c2n"
	"adreq/d9w"
	"adreq/nx"
)

// Run digests metamorphic lanes and emits YAML when tips agree.
func Run(bundle nx.Bundle, lanes []nx.Lane, arm int, outPath string) error {
	if len(bundle.Units) == 0 {
		return nil
	}
	unit := bundle.Units[0]
	var digs []nx.MtDigest
	for i := range lanes {
		digs = append(digs, c2n.Digest(unit, lanes, i))
	}
	dig := nx.MtDigest{Name: "none", Hex: "0000000000000000"}
	if len(digs) > 0 {
		dig = digs[0]
	}
	for _, d := range digs {
		if d.Name == "hold_cluster" {
			dig = d
			break
		}
	}
	_ = d9w.Emit(dig, unit, bundle.Tip, arm, outPath)
	return nil
}
