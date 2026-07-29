package memo

import (
	"crypto/sha256"
	"encoding/hex"
	"k7w/internal/model"
)

var seen = map[string]struct{}{}

// MarkUnique records a transition when the idempotency key is unseen.
func MarkUnique(id model.MemoID, row model.Transition) (bool, error) {
	if row.ID == "" {
		return false, nil
	}
	h := sha256.Sum256(append([]byte(row.ID), id[:8]...))
	key := hex.EncodeToString(h[:])
	if _, ok := seen[key]; ok {
		return false, nil
	}
	seen[key] = struct{}{}
	return true, nil
}

func ResetLedger() {
	seen = map[string]struct{}{}
}
