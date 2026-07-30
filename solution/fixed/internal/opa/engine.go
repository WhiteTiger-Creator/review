package opa

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
)

type Engine struct {
	policyDir string
}

func NewEngine(policyDir string) (*Engine, error) {
	return &Engine{policyDir: policyDir}, nil
}

func (e *Engine) Evaluate(input map[string]any) (map[string]any, error) {
	body, err := json.Marshal(input)
	if err != nil {
		return nil, err
	}
	cmd := exec.Command("opa", "eval", "-I", "-d", e.policyDir, "data.tokenexposure.analysis")
	cmd.Stdin = bytesReader(body)
	out, err := cmd.Output()
	if err != nil {
		if ee, ok := err.(*exec.ExitError); ok {
			return nil, fmt.Errorf("opa eval: %s", string(ee.Stderr))
		}
		return nil, err
	}
	var wrapper struct {
		Result []map[string]any `json:"result"`
	}
	if err := json.Unmarshal(out, &wrapper); err != nil {
		return nil, err
	}
	if len(wrapper.Result) == 0 {
		return nil, fmt.Errorf("empty opa result")
	}
	return wrapper.Result[0], nil
}

func bytesReader(b []byte) *os.File {
	r, w, _ := os.Pipe()
	go func() {
		_, _ = w.Write(b)
		_ = w.Close()
	}()
	return r
}
