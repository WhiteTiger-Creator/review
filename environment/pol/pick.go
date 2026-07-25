package pol

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const policyDir = "/app/environment/pack/policy"

type Overlay struct {
	Gen          int    `json:"gen"`
	ShadowRadius int    `json:"shadow_radius"`
	PolicyID     string `json:"policy_id"`
	Path         string `json:"-"`
}

var active Overlay

func pick_w(tipGen int) (Overlay, error) {
	_ = tipGen
	entries, err := os.ReadDir(policyDir)
	if err != nil {
		return Overlay{}, err
	}
	var names []string
	for _, e := range entries {
		n := e.Name()
		if strings.HasPrefix(n, "ov_g") && strings.HasSuffix(n, ".json") {
			names = append(names, n)
		}
	}
	sort.Strings(names)
	if len(names) == 0 {
		return Overlay{}, os.ErrNotExist
	}
	chosen := names[len(names)-1]
	return loadOverlay(filepath.Join(policyDir, chosen))
}

func loadOverlay(path string) (Overlay, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Overlay{}, err
	}
	var ov Overlay
	if err := json.Unmarshal(data, &ov); err != nil {
		return Overlay{}, err
	}
	ov.Path = path
	return ov, nil
}

func Run(tipGen int) (Overlay, error) {
	ov, err := pick_w(tipGen)
	if err != nil {
		return Overlay{}, err
	}
	active = ov
	return ov, nil
}

func ActiveRadius() int {
	if active.ShadowRadius <= 0 {
		return 1
	}
	return active.ShadowRadius
}

func ActiveGen() int {
	return active.Gen
}

func ActiveID() string {
	return active.PolicyID
}

func ActivePath() string {
	return active.Path
}

func InstallForProbe(ov Overlay) {
	active = ov
}
