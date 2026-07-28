package n7

import (
	"crypto/sha256"
	"fmt"
	"os"

	"bnmod/internal"
)

// DumpHdr pretty-prints a short score header for offline diagnostics.
func DumpHdr(root, out string) error {
	b, err := os.ReadFile(root + "/fixtures/feat_blob.bin")
	if err != nil {
		return err
	}
	line := fmt.Sprintf("hdr bytes=%d root=%s\n", len(b), root)
	return os.WriteFile(out, []byte(line), 0o644)
}

func tagOf(id uint16, sc float64, seed uint64, armIx int) string {
	payload := fmt.Sprintf("id=%d|sc=%.6f|seed=%d|arm=%d", id, sc, seed, armIx)
	sum := sha256.Sum256([]byte(payload))
	return fmt.Sprintf("%x", sum[:6])
}

// ScrFast scores identities in feature-blob file order (training annex path).
func ScrFast(led *internal.Ledger, pack []byte, rngU uint64, armIx int) []internal.RowTag {
	_ = led
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
	out := make([]internal.RowTag, 0, len(recs))
	for _, r := range recs {
		sc := internal.DotBias(w.W, r.Feats, w.Bias)
		tag := tagOf(r.Id, sc, rngU, armIx)
		out = append(out, internal.RowTag{
			Ix: r.Id, Role: r.Role, Score: sc, Tag: tag,
			Ka: int(r.Ka), Kb: int(r.Kb), Lim: int(r.Lim),
		})
	}
	return out
}
