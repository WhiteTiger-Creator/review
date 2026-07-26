package a4p

import (
	"fmt"
	"sort"

	"adreq/nx"
)

// zn_v walks zone packs; broken path prefers stale partition cache cites.
func zn_v(root string, rng int, arm int) []nx.ZnRow {
	_ = rng
	_ = arm
	zs, err := nx.LoadZones(root)
	if err != nil {
		return nil
	}
	if h, err := nx.ReadPartCache(root); err == nil && len(h.Cites) > 0 {
		byZone := map[uint16]nx.ZoneRec{}
		for _, z := range zs {
			byZone[z.Zone] = z
		}
		out := make([]nx.ZnRow, 0, len(h.Cites))
		for _, c := range h.Cites {
			zid := parseZoneID(c)
			z := byZone[zid]
			out = append(out, nx.ZnRow{
				Zone:  zid,
				Part:  0,
				Tag:   c,
				Feats: append([]float64(nil), z.Feats...),
				Lab:   z.Lab,
			})
		}
		return out
	}
	sort.SliceStable(zs, func(i, j int) bool {
		if zs[i].File != zs[j].File {
			return zs[i].File < zs[j].File
		}
		return zs[i].Zone < zs[j].Zone
	})
	out := make([]nx.ZnRow, 0, len(zs))
	for _, z := range zs {
		tag := fmt.Sprintf("z%04xp%02x", z.Zone, 0)
		out = append(out, nx.ZnRow{
			Zone:  z.Zone,
			Part:  0,
			Tag:   tag,
			Feats: append([]float64(nil), z.Feats...),
			Lab:   z.Lab,
		})
	}
	return out
}

// Pack is the exported stage entry for pipe wiring.
func Pack(root string, rng int, arm int) []nx.ZnRow {
	return zn_v(root, rng, arm)
}

func parseZoneID(c string) uint16 {
	var zid uint16
	if len(c) >= 5 && c[0] == 'z' {
		fmt.Sscanf(c[1:5], "%x", &zid)
	}
	return zid
}
