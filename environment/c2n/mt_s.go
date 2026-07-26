package c2n

import "adreq/nx"

// mt_s computes metamorphic digests.
func mt_s(unit nx.RgUnit, lanes []nx.Lane, partIdx int) nx.MtDigest {
	return mt_gauge(unit, lanes, partIdx)
}

// Digest is the exported stage entry for pipe wiring.
func Digest(unit nx.RgUnit, lanes []nx.Lane, partIdx int) nx.MtDigest {
	return mt_s(unit, lanes, partIdx)
}
