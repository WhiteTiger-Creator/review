package c2n

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
	"strings"

	"adreq/nx"
)

// mt_s computes metamorphic-noninterference digests under a lane index.
func mt_s(unit nx.RgUnit, lanes []nx.Lane, partIdx int) nx.MtDigest {
	if partIdx < 0 || partIdx >= len(lanes) {
		return nx.MtDigest{Name: "none", Hex: strings.Repeat("0", 16)}
	}
	ln := lanes[partIdx]
	keys := make([]string, 0, len(unit.Cites))
	for _, c := range unit.Cites {
		if len(c) >= 5 && c[0] == 'z' {
			keys = append(keys, c[1:5])
		} else {
			keys = append(keys, c)
		}
	}
	sort.Strings(keys)
	payload := fmt.Sprintf("%s|%d|%s|%s|%d", ln.Kind, ln.Seed, unit.Arm, strings.Join(keys, ","), unit.RegretMilli)
	switch ln.Kind {
	case "cluster":
		payload = "C:" + payload
	case "feature":
		payload = "F:" + payload
	case "stream":
		payload = "S:" + payload
	case "fuzz":
		payload = fmt.Sprintf("Z:%d:%s", ln.N, payload)
	default:
		payload = "X:" + payload
	}
	sum := sha256.Sum256([]byte(payload))
	return nx.MtDigest{Name: ln.Name, Hex: hex.EncodeToString(sum[:8])}
}

// Digest is the exported stage entry for pipe wiring.
func Digest(unit nx.RgUnit, lanes []nx.Lane, partIdx int) nx.MtDigest {
	return mt_s(unit, lanes, partIdx)
}
