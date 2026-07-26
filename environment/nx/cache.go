package nx

import (
	"encoding/binary"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// CacheHeader describes a partition cache blob.
type CacheHeader struct {
	Stamp       uint32
	FreezeEpoch uint32
	Cites       []string
}

// ReadPartCache loads data/part_cache.bin when present.
func ReadPartCache(root string) (CacheHeader, error) {
	raw, err := os.ReadFile(filepath.Join(root, "data", "part_cache.bin"))
	if err != nil {
		return CacheHeader{}, err
	}
	if len(raw) < 14 || string(raw[:4]) != "PC01" {
		return CacheHeader{}, fmt.Errorf("bad part cache")
	}
	stamp := binary.LittleEndian.Uint32(raw[4:8])
	fr := binary.LittleEndian.Uint32(raw[8:12])
	n := int(binary.LittleEndian.Uint16(raw[12:14]))
	off := 14
	cites := make([]string, 0, n)
	for i := 0; i < n; i++ {
		if off+12 > len(raw) {
			return CacheHeader{}, fmt.Errorf("short part cache")
		}
		c := strings.TrimRight(string(raw[off:off+12]), "\x00")
		cites = append(cites, c)
		off += 12
	}
	return CacheHeader{Stamp: stamp, FreezeEpoch: fr, Cites: cites}, nil
}

// CacheValid reports whether the cache matches pack stamp and freeze epoch.
func CacheValid(h CacheHeader, stamp uint32, freeze uint32) bool {
	return h.Stamp == stamp && h.FreezeEpoch == freeze && len(h.Cites) > 0
}

// WritePartCache rewrites data/part_cache.bin from packed rows.
func WritePartCache(root string, stamp uint32, freeze uint32, rows []ZnRow) error {
	buf := make([]byte, 0, 14+12*len(rows))
	buf = append(buf, []byte("PC01")...)
	buf = binary.LittleEndian.AppendUint32(buf, stamp)
	buf = binary.LittleEndian.AppendUint32(buf, freeze)
	buf = binary.LittleEndian.AppendUint16(buf, uint16(len(rows)))
	for _, r := range rows {
		b := make([]byte, 12)
		copy(b, []byte(r.Tag))
		buf = append(buf, b...)
	}
	return os.WriteFile(filepath.Join(root, "data", "part_cache.bin"), buf, 0o644)
}
