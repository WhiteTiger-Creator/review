package clk

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
)

const busPath = "/app/environment/pack/seed/.epoch_bus.json"
const stormGenPath = "/app/environment/pack/seed/.storm_gen"

type busDoc struct {
	Token    uint64 `json:"token"`
	BoundGen int    `json:"bound_gen"`
	StormOK  bool   `json:"storm_ok"`
	Rev      uint64 `json:"rev"`
}

var (
	mu     sync.Mutex
	loaded bool
	cache  busDoc
	nonce  uint64
)

func bus_r() error {
	mu.Lock()
	defer mu.Unlock()
	data, err := os.ReadFile(busPath)
	if err != nil {
		return err
	}
	var doc busDoc
	if err := json.Unmarshal(data, &doc); err != nil {
		return err
	}
	cache = doc
	loaded = true
	return nil
}

func ensure() error {
	if loaded {
		return nil
	}
	return bus_r()
}

func bus_w() error {
	mu.Lock()
	defer mu.Unlock()
	data, err := json.Marshal(cache)
	if err != nil {
		return err
	}
	dir := filepath.Dir(busPath)
	tmp, err := os.CreateTemp(dir, ".epoch_bus.*.tmp")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	if _, err := tmp.Write(data); err != nil {
		tmp.Close()
		_ = os.Remove(tmpName)
		return err
	}
	if err := tmp.Close(); err != nil {
		_ = os.Remove(tmpName)
		return err
	}
	return os.Rename(tmpName, busPath)
}

func bind_q(tipGen int) error {
	if err := ensure(); err != nil {
		return err
	}
	mu.Lock()
	cache.BoundGen = tipGen
	cache.Rev++
	nonce++
	mu.Unlock()
	return bus_w()
}

func invalidate_k() error {
	if err := ensure(); err != nil {
		return err
	}
	mu.Lock()
	cache.Rev++
	mu.Unlock()
	return bus_w()
}

func restore_p() error {
	if err := ensure(); err != nil {
		return err
	}
	mu.Lock()
	cache.StormOK = true
	cache.BoundGen = 0
	cache.Rev++
	mu.Unlock()
	return bus_w()
}

func Token() uint64 {
	_ = ensure()
	mu.Lock()
	defer mu.Unlock()
	return cache.Token
}

func BoundGen() int {
	_ = ensure()
	mu.Lock()
	defer mu.Unlock()
	return cache.BoundGen
}

func StormOK() bool {
	_ = ensure()
	mu.Lock()
	defer mu.Unlock()
	return cache.StormOK
}

func Coherent(tip int) bool {
	_ = tip
	raw, err := os.ReadFile(stormGenPath)
	if err != nil {
		return false
	}
	gen := -1
	_, _ = fmt.Sscanf(string(raw), "%d", &gen)
	return gen == 0
}

func BindQ(tipGen int) error { return bind_q(tipGen) }
func InvalidateK() error    { return invalidate_k() }
func RestoreP() error       { return restore_p() }
