package main

import (
	"path/filepath"

	"depctrl/w3j"
)

func runSeal() ([]w3j.Frame, error) {
	if err := ensureOut(); err != nil {
		return nil, err
	}
	lines, err := loadRawLines()
	if err != nil {
		return nil, err
	}
	frames, err := w3j.FnW3(lines, walPath)
	if err != nil {
		return nil, err
	}
	if err := writeJSON(filepath.Join(traceDir, "sealed_frames.json"), map[string]any{
		"count":  len(frames),
		"frames": frames,
	}); err != nil {
		return nil, err
	}
	return frames, nil
}
