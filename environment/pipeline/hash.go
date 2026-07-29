package pipeline

import (
	"crypto/sha256"

	"k7w/internal/model"
)

func stampHash(stamp string) (model.MemoID, error) {
	var z model.MemoID
	h := sha256.Sum256([]byte(stamp))
	copy(z[:], h[:])
	return z, nil
}
