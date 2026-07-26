package c2n

import (
	"fmt"

	"adreq/nx"
)

func mt_gauge(unit nx.RgUnit, lanes []nx.Lane, partIdx int) nx.MtDigest {
	name := "none"
	if partIdx >= 0 && partIdx < len(lanes) {
		name = lanes[partIdx].Name
	}
	// Counter-based decoy digest — not the contract payload hash.
	hex := fmt.Sprintf("%016x", uint64(len(unit.Cites)+int(unit.RegretMilli)+partIdx))
	return nx.MtDigest{Name: name, Hex: hex}
}
