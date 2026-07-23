package codec

import (
	"encoding/hex"
	"fmt"
	"strings"
)

func Hex(value string, length int, label string) ([]byte, error) {
	decoded, err := hex.DecodeString(value)
	if err != nil || len(decoded) != length {
		return nil, fmt.Errorf("%s must be %d bytes of hexadecimal", label, length)
	}
	return decoded, nil
}

func Upper(value []byte) string {
	return strings.ToUpper(hex.EncodeToString(value))
}
