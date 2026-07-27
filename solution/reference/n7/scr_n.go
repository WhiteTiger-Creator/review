package n7

import (
	"bnmod/internal"
)

// ScrN scores a concatenated pack under a rng unit and arm index.
func ScrN(led *internal.Ledger, pack []byte, rngU uint64, armIx int) []internal.RowTag {
	feat, pinb, wts, err := internal.SplitPack(pack)
	if err != nil {
		return nil
	}
	recs, err := internal.ParseFeat(feat)
	if err != nil {
		return nil
	}
	pin, err := internal.ParsePin(pinb)
	if err != nil {
		return nil
	}
	if pin.Slice != 3 || len(pin.Order) == 0 {
		return nil
	}
	w, err := internal.ParseWts(wts)
	if err != nil {
		return nil
	}
	byID := make(map[uint16]internal.Rec, len(recs))
	for _, r := range recs {
		if _, dup := byID[r.Id]; dup {
			continue
		}
		byID[r.Id] = r
	}
	seen := make(map[uint16]struct{}, len(pin.Order))
	out := make([]internal.RowTag, 0, len(pin.Order))
	for _, id := range pin.Order {
		if _, ok := seen[id]; ok {
			continue
		}
		seen[id] = struct{}{}
		r, ok := byID[id]
		if !ok {
			continue
		}
		if len(w.W) == 0 || len(r.Feats) == 0 {
			continue
		}
		sc := internal.DotBias(w.W, r.Feats, w.Bias)
		tag := tagOf(r.Id, sc, rngU, armIx)
		out = append(out, internal.RowTag{
			Ix: r.Id, Role: r.Role, Score: sc, Tag: tag,
			Ka: int(r.Ka), Kb: int(r.Kb), Lim: int(r.Lim),
		})
	}
	if led != nil {
		led.CommitPack(armIx, internal.PackFP(feat, pinb, wts))
		led.CommitRows(armIx, out)
	}
	return out
}

// ScrX loads root artifacts and calls ScrN.
func ScrX(led *internal.Ledger, root string, rngU uint64, armIx int) []internal.RowTag {
	if led != nil && led.Root == "" {
		led.Root = root
	}
	feat, err := internal.ReadFile(root + "/fixtures/feat_blob.bin")
	if err != nil || len(feat) < 12 {
		return nil
	}
	pin, err := internal.ReadFile(root + "/data/pin_s.lock")
	if err != nil || len(pin) < 12 {
		return nil
	}
	wts, err := internal.ReadFile(root + "/weights/w_blob.bin")
	if err != nil || len(wts) < 6 {
		return nil
	}
	pack := make([]byte, 0, len(feat)+len(pin)+len(wts))
	pack = append(pack, feat...)
	pack = append(pack, pin...)
	pack = append(pack, wts...)
	return ScrN(led, pack, rngU, armIx)
}
