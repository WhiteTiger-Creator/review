package internal

import (
	"encoding/binary"
	"fmt"
	"os"
	"path/filepath"
)

const runEpochName = "run_epoch.bin"

// RunEpochPath is the freeze/run-epoch marker under data/.
func RunEpochPath(root string) string {
	return filepath.Join(root, "data", runEpochName)
}

// ReadRunEpoch loads RN01 stamp+slice when present.
func ReadRunEpoch(root string) (stamp uint32, slice uint16, ok bool) {
	raw, err := os.ReadFile(RunEpochPath(root))
	if err != nil || len(raw) < 10 || string(raw[:4]) != "RN01" {
		return 0, 0, false
	}
	return binary.LittleEndian.Uint32(raw[4:8]), binary.LittleEndian.Uint16(raw[8:10]), true
}

// RunEpochOK reports whether RN01 matches feature stamp and pin slice.
func RunEpochOK(root string, stamp uint32, slice uint16) bool {
	s, sl, ok := ReadRunEpoch(root)
	return ok && s == stamp && sl == slice
}

// WriteRunEpoch rewrites RN01 from the active feature stamp and pin slice.
func WriteRunEpoch(root string, stamp uint32, slice uint16) error {
	if root == "" {
		return fmt.Errorf("empty root")
	}
	buf := make([]byte, 0, 10)
	buf = append(buf, []byte("RN01")...)
	buf = binary.LittleEndian.AppendUint32(buf, stamp)
	buf = binary.LittleEndian.AppendUint16(buf, slice)
	_ = os.MkdirAll(filepath.Join(root, "data"), 0o755)
	return os.WriteFile(RunEpochPath(root), buf, 0o644)
}
