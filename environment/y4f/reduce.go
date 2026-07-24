package y4f

import (
	"sort"

	"depctrl/w3j"
)

func fn_y4(frames []w3j.Frame, allowed map[string]bool, probe ProbeView) ([]RowOut, error) {
	type key struct{ pkg, dep string }
	buckets := map[key][]w3j.Frame{}
	for _, fr := range frames {
		k := key{fr.Pkg, fr.Dep}
		if len(allowed) > 0 && !allowed[fr.Pkg+"\x00"+fr.Dep] {
			continue
		}
		buckets[k] = append(buckets[k], fr)
	}

	keys := make([]key, 0, len(buckets))
	for k := range buckets {
		keys = append(keys, k)
	}
	sort.Slice(keys, func(i, j int) bool {
		if keys[i].pkg != keys[j].pkg {
			return keys[i].pkg < keys[j].pkg
		}
		return keys[i].dep < keys[j].dep
	})

	var out []RowOut
	for _, k := range keys {
		group := buckets[k]
		sort.SliceStable(group, func(i, j int) bool {
			if group[i].Seq != group[j].Seq {
				return group[i].Seq < group[j].Seq
			}
			return group[i].Epoch < group[j].Epoch
		})
		lo := group[0].Lo
		hi := group[0].Hi
		preTok := group[0].PreTok
		lift := group[0].Lift
		for _, r := range group[1:] {
			if cmpVer(r.Lo, lo) < 0 {
				lo = r.Lo
			}
			if cmpVer(r.Hi, hi) > 0 {
				hi = r.Hi
			}
			if r.PreTok != "" && preTok == "" {
				preTok = r.PreTok
			}
			if r.Lift {
				lift = true
			}
		}
		pkey := k.pkg + "\x00" + k.dep
		if peer, ok := probe.PeerHi[pkey]; ok {
			if lift {
				if cmpVer(peer, hi) > 0 {
					hi = peer
				}
			} else if cmpVer(peer, hi) < 0 {
				hi = peer
			}
		}
		if preTok == "allow" || preTok == "" {
			hi = StripPreToken(hi)
			lo = StripPreToken(lo)
		}
		if preTok != "allow" {
			preTok = ""
		}
		out = append(out, RowOut{
			Pkg: k.pkg, Dep: k.dep, Lo: lo, Hi: hi, PreTok: preTok, Lift: lift,
			RowDigest: RowDigest(k.pkg, k.dep, lo, hi, preTok, lift),
		})
	}
	return out, nil
}

func FnY4(frames []w3j.Frame, allowed map[string]bool, probe ProbeView) ([]RowOut, error) {
	return fn_y4(frames, allowed, probe)
}
