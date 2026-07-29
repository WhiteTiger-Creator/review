package pol

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
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
	path := filepath.Join(policyDir, fmt.Sprintf("ov_g%d.json", tipGen))
	return loadOverlay(path)
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
