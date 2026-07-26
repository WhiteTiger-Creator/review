package g9

// ReadStagedAnchor loads staging bytes from anchor_staging, falling back to token_seed.

import "os"

const stagingPath = "/app/environment/pack/seed/.anchor_staging"
const seedPath = "/app/environment/pack/seed/token_seed.bin"

func ReadStagedAnchor() [8]byte {
	data, err := os.ReadFile(stagingPath)
	if err != nil || len(data) < 8 {
		data, err = os.ReadFile(seedPath)
		if err != nil || len(data) < 8 {
			return [8]byte{}
		}
	}
	var out [8]byte
	copy(out[:], data[:8])
	return out
}

func LoadAnchorFromSeed(seed []byte) {
	var buf [8]byte
	if len(seed) >= 8 {
		copy(buf[:], seed[:8])
	}
	_ = os.WriteFile(stagingPath, buf[:], 0o644)
}

func ClearStaging() {
	_ = os.Remove(stagingPath)
}
