package a4p

import (
	"fmt"
	"sort"

	"adreq/nx"
)

// zn_v materializes eigengap partitions, invalidating stale partition caches.
func zn_v(root string, rng int, arm int) []nx.ZnRow {
	_ = rng
	arms, err := nx.LoadSplit(root)
	if err != nil || arm < 0 || arm >= len(arms) {
		return nil
	}
	freeze := arms[arm].FreezeEpoch
	stamp, err := nx.MaxPackStamp(root)
	if err != nil {
		return nil
	}
	if h, err := nx.ReadPartCache(root); err == nil && nx.CacheValid(h, stamp, freeze) {
		zs, err := nx.LoadZones(root)
		if err != nil {
			return nil
		}
		byZone := map[uint16]nx.ZoneRec{}
		for _, z := range zs {
			byZone[z.Zone] = z
		}
		out := make([]nx.ZnRow, 0, len(h.Cites))
		for _, c := range h.Cites {
			zid, part := parseCite(c)
			z := byZone[zid]
			out = append(out, nx.ZnRow{
				Zone:  zid,
				Part:  part,
				Tag:   c,
				Feats: append([]float64(nil), z.Feats...),
				Lab:   z.Lab,
			})
		}
		return out
	}

	zs, err := nx.LoadZones(root)
	if err != nil {
		return nil
	}
	type item struct {
		z    nx.ZoneRec
		mean float64
	}
	items := make([]item, 0, len(zs))
	for _, z := range zs {
		items = append(items, item{z: z, mean: nx.Mean(z.Feats)})
	}
	sort.SliceStable(items, func(i, j int) bool {
		if items[i].mean == items[j].mean {
			return items[i].z.Zone < items[j].z.Zone
		}
		return items[i].mean < items[j].mean
	})
	cutAfter := 0
	bestGap := -1.0
	for i := 0; i+1 < len(items); i++ {
		g := items[i+1].mean - items[i].mean
		if g > bestGap {
			bestGap = g
			cutAfter = i + 1
		}
	}
	out := make([]nx.ZnRow, 0, len(items))
	for i, it := range items {
		part := uint16(0)
		if i >= cutAfter {
			part = 1
		}
		tag := fmt.Sprintf("z%04xp%02x", it.z.Zone, part)
		out = append(out, nx.ZnRow{
			Zone:  it.z.Zone,
			Part:  part,
			Tag:   tag,
			Feats: append([]float64(nil), it.z.Feats...),
			Lab:   it.z.Lab,
		})
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].Part != out[j].Part {
			return out[i].Part < out[j].Part
		}
		return out[i].Zone < out[j].Zone
	})
	_ = nx.WritePartCache(root, stamp, freeze, out)
	return out
}

// Pack is the exported stage entry for pipe wiring.
func Pack(root string, rng int, arm int) []nx.ZnRow {
	return zn_v(root, rng, arm)
}

func tagOf(zone uint16, part uint16) string {
	return fmt.Sprintf("z%04xp%02x", zone, part)
}

func parseCite(c string) (uint16, uint16) {
	var zid, part uint16
	if len(c) >= 8 && c[0] == 'z' {
		fmt.Sscanf(c[1:5], "%x", &zid)
		if len(c) >= 8 && c[5] == 'p' {
			fmt.Sscanf(c[6:8], "%x", &part)
		}
	}
	return zid, part
}
