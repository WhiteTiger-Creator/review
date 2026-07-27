package n7

import (
	"crypto/sha256"
	"fmt"
	"os"
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
