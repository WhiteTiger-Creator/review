package cryptoutil

import (
	"crypto/sha512"

	"beaconaudit/internal/codec"
)

func SHA512(data []byte) string {
	digest := sha512.Sum512(data)
	return codec.Upper(digest[:])
}
