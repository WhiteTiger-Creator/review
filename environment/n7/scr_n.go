package n7

import (
	"bnmod/internal"
)

// ScrN scores a concatenated pack under a rng unit and arm index.
func ScrN(led *internal.Ledger, pack []byte, rngU uint64, armIx int) []internal.RowTag {
	feat, _, wts, err := internal.SplitPack(pack)
	if err != nil {
		return nil
	}
	recs, err := internal.ParseFeat(feat)
	if err != nil {
		return nil
	}
	w, err := internal.ParseWts(wts)
	if err != nil {
		return nil
	}
	byID := make(map[uint16]internal.Rec, len(recs))
	for _, r := range recs {
		byID[r.Id] = r
	}
	root := ""
	if led != nil {
		root = led.Root
	}
	if ord, ok := internal.CachedOrder(root); ok {
		out := make([]internal.RowTag, 0, len(ord))
		for _, id := range ord {
			r, ok := byID[id]
			if !ok {
				continue
			}
			sc := internal.DotBias(w.W, r.Feats, w.Bias)
			tag := tagOf(r.Id, sc, rngU, armIx)
			out = append(out, internal.RowTag{
				Ix: r.Id, Role: r.Role, Score: sc, Tag: tag,
				Ka: int(r.Ka), Kb: int(r.Kb), Lim: int(r.Lim),
			})
		}
		return out
	}
	return ScrFast(led, pack, rngU, armIx)
}

// ScrX loads root artifacts and calls ScrN.
func ScrX(led *internal.Ledger, root string, rngU uint64, armIx int) []internal.RowTag {
	if led != nil && led.Root == "" {
		led.Root = root
	}
	feat, err := internal.ReadFile(root + "/fixtures/feat_blob.bin")
	if err != nil {
		return nil
	}
	pin, err := internal.ReadFile(root + "/data/pin_s.lock")
	if err != nil {
		return nil
	}
	wts, err := internal.ReadFile(root + "/weights/w_blob.bin")
	if err != nil {
		return nil
	}
	stamp, _ := internal.FeatStamp(feat)
	if internal.WarmPresent(root) || !internal.RunEpochOK(root, stamp, 3) {
		pack := append(append(feat, pin...), wts...)
		return ScrFast(led, pack, rngU, armIx)
	}
	pack := append(append(feat, pin...), wts...)
	return ScrN(led, pack, rngU, armIx)
}
