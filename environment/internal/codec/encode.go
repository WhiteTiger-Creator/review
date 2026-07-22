package codec

import (
	"encoding/binary"
	"fmt"
)

func Uint32(value uint32) []byte {
	result := make([]byte, 4)
	binary.BigEndian.PutUint32(result, value)
	return result
}

func Uint64(value uint64) []byte {
	result := make([]byte, 8)
	binary.BigEndian.PutUint64(result, value)
	return result
}

func Sized(value []byte) []byte {
	return append(Uint32(uint32(len(value))), value...)
}

func FixedSized(value []byte, length int, label string) ([]byte, error) {
	if len(value) != length {
		return nil, fmt.Errorf("%s must be %d bytes, got %d", label, length, len(value))
	}
	return Sized(value), nil
}
