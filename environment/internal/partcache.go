package internal

import (
	"encoding/binary"
	"fmt"
	"os"
	"path/filepath"
)

// PartCacheHeader describes a pin-order partition cache blob (PC01).
type PartCacheHeader struct {
	Stamp uint32
	Slice uint16
	Order []uint16
}

// FeatStamp returns the u32 stamp from a FEAT blob header.
func FeatStamp(feat []byte) (uint32, error) {
	if len(feat) < 12 || string(feat[0:4]) != "FEAT" {
		return 0, fmt.Errorf("feat hdr")
	}
	return binary.LittleEndian.Uint32(feat[8:12]), nil
}

// ReadPartCache loads data/part_cache.bin when present.
func ReadPartCache(root string) (PartCacheHeader, error) {
	raw, err := os.ReadFile(filepath.Join(root, "data", "part_cache.bin"))
	if err != nil {
		return PartCacheHeader{}, err
	}
	if len(raw) < 12 || string(raw[:4]) != "PC01" {
		return PartCacheHeader{}, fmt.Errorf("bad part cache")
	}
	stamp := binary.LittleEndian.Uint32(raw[4:8])
	slice := binary.LittleEndian.Uint16(raw[8:10])
	n := int(binary.LittleEndian.Uint16(raw[10:12]))
	off := 12
	order := make([]uint16, 0, n)
	for i := 0; i < n; i++ {
		if off+2 > len(raw) {
			return PartCacheHeader{}, fmt.Errorf("short part cache")
		}
		order = append(order, binary.LittleEndian.Uint16(raw[off:]))
		off += 2
	}
	return PartCacheHeader{Stamp: stamp, Slice: slice, Order: order}, nil
}

// PartCacheValid reports whether the cache matches pack stamp and pin slice.
func PartCacheValid(h PartCacheHeader, stamp uint32, slice uint16) bool {
	return h.Stamp == stamp && h.Slice == slice && len(h.Order) > 0
}

// CachedOrder returns packing ids from PC01 when present (stamp unchecked).
func CachedOrder(root string) ([]uint16, bool) {
	h, err := ReadPartCache(root)
	if err != nil || len(h.Order) == 0 {
		return nil, false
	}
	return h.Order, true
}

// WritePartCache rewrites data/part_cache.bin from pin packing order.
func WritePartCache(root string, stamp uint32, slice uint16, order []uint16) error {
	if root == "" {
		return fmt.Errorf("empty root")
	}
	buf := make([]byte, 0, 12+2*len(order))
	buf = append(buf, []byte("PC01")...)
	buf = binary.LittleEndian.AppendUint32(buf, stamp)
	buf = binary.LittleEndian.AppendUint16(buf, slice)
	buf = binary.LittleEndian.AppendUint16(buf, uint16(len(order)))
	for _, id := range order {
		buf = binary.LittleEndian.AppendUint16(buf, id)
	}
	_ = os.MkdirAll(filepath.Join(root, "data"), 0o755)
	return os.WriteFile(filepath.Join(root, "data", "part_cache.bin"), buf, 0o644)
}
