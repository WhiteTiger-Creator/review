package corpus

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"sort"
)

func EvidenceFingerprint(events []map[string]any) string {
	ids := make([]string, 0, len(events))
	for _, ev := range events {
		ids = append(ids, fmtEventID(ev))
	}
	sort.Strings(ids)
	h := sha256.New()
	for _, id := range ids {
		_, _ = h.Write([]byte(id))
		_, _ = h.Write([]byte{0})
	}
	return hex.EncodeToString(h.Sum(nil))
}

func fmtEventID(ev map[string]any) string {
	b, _ := json.Marshal(ev)
	return string(b)
}
