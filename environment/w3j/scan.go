package w3j

import (
	"bufio"
	"encoding/json"
	"os"
	"strings"
)

// LoadRaw opens a JSONL arm file and returns raw lines with their arm tag.
// Highest-seq collapse happens later inside journal sealing.
func LoadRaw(path string, armTag byte) ([]RawLine, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var out []RawLine
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		out = append(out, RawLine{Bytes: []byte(line), ArmTag: armTag})
	}
	return out, sc.Err()
}

// ParseLoose unmarshals common event fields without arm-specific policy.
func ParseLoose(line []byte) (map[string]any, error) {
	var raw map[string]any
	if err := json.Unmarshal(line, &raw); err != nil {
		return nil, err
	}
	return raw, nil
}
