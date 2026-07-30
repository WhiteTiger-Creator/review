package state

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type Manager struct {
	path string
}

func New(path string) *Manager {
	return &Manager{path: path}
}

func (m *Manager) Publish(report map[string]any, dot string, outputDir string) error {
	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return err
	}
	staging := filepath.Join(outputDir, ".staging")
	if err := os.MkdirAll(staging, 0o755); err != nil {
		return err
	}
	reportPath := filepath.Join(staging, "token_exposure_report.json")
	dotPath := filepath.Join(staging, "token_exposure_graph.dot")
	rb, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(reportPath, append(rb, '\n'), 0o644); err != nil {
		return err
	}
	if err := os.WriteFile(dotPath, []byte(dot), 0o644); err != nil {
		return err
	}
	finalReport := filepath.Join(outputDir, "token_exposure_report.json")
	finalDot := filepath.Join(outputDir, "token_exposure_graph.dot")
	if err := os.Rename(reportPath, finalReport); err != nil {
		return err
	}
	if err := os.Rename(dotPath, finalDot); err != nil {
		return err
	}
	cp := &Checkpoint{Path: m.path}
	return cp.Save(map[string]any{"status": Finished, "published": true})
}
