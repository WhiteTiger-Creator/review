package main

import (
	"encoding/json"
	"os"
	"path/filepath"

	"depctrl/w3j"
)

func runCollect() error {
	if err := ensureOut(); err != nil {
		return err
	}
	arms := []struct {
		path string
		tag  byte
	}{
		{filepath.Join(dataRoot, "events", "m_a.jsonl"), 'a'},
		{filepath.Join(dataRoot, "events", "m_b.jsonl"), 'b'},
		{filepath.Join(dataRoot, "events", "m_h.jsonl"), 'h'},
	}
	var lines []w3j.RawLine
	for _, arm := range arms {
		chunk, err := w3j.LoadRaw(arm.path, arm.tag)
		if err != nil {
			return err
		}
		lines = append(lines, chunk...)
	}
	out := map[string]any{"line_count": len(lines)}
	if err := writeJSON(filepath.Join(runTraceDir, "collected.json"), out); err != nil {
		return err
	}
	// Persist raw bundle for emit/reconcile handoff.
	b, err := json.Marshal(lines)
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(runTraceDir, "raw_lines.json"), b, 0o644)
}

func loadRawLines() ([]w3j.RawLine, error) {
	b, err := os.ReadFile(filepath.Join(runTraceDir, "raw_lines.json"))
	if err != nil {
		return nil, err
	}
	var lines []w3j.RawLine
	if err := json.Unmarshal(b, &lines); err != nil {
		return nil, err
	}
	return lines, nil
}
