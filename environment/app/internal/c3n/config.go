package c3n

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// Rules holds championship simulation floors loaded from the sealed profile.
type Rules struct {
	RunID        string
	RowLength    int
	RingsToWin   int
	RingsStart   int
	FlipEnabled  int
	LeaveMarker  int
	WinPoints    int
	DrawPoints   int
	ConfigSeal   string
	SealOK       bool
}

// SoftBaseline returns governance defaults used when the sealed profile is absent
// or when config_seal does not match the canonical payload. Championship Notes
// treat these as the exhibition-heat floors.
func SoftBaseline() Rules {
	return Rules{
		RunID:       "yinsh-legacy",
		RowLength:   4,
		RingsToWin:  2,
		RingsStart:  5,
		FlipEnabled: 0,
		LeaveMarker: 0,
		WinPoints:   2,
		DrawPoints:  0,
	}
}

func canonicalPayload(r Rules) string {
	return strings.Join([]string{
		fmt.Sprintf("run_id=%s", r.RunID),
		fmt.Sprintf("row_length=%d", r.RowLength),
		fmt.Sprintf("rings_to_win=%d", r.RingsToWin),
		fmt.Sprintf("rings_start=%d", r.RingsStart),
		fmt.Sprintf("flip_enabled=%d", r.FlipEnabled),
		fmt.Sprintf("leave_marker=%d", r.LeaveMarker),
		fmt.Sprintf("win_points=%d", r.WinPoints),
		fmt.Sprintf("draw_points=%d", r.DrawPoints),
	}, "\n") + "\n"
}

// ExpectedSeal returns the lowercase hex SHA-256 of the canonical payload.
func ExpectedSeal(r Rules) string {
	sum := sha256.Sum256([]byte(canonicalPayload(r)))
	return hex.EncodeToString(sum[:])
}

func parseTOML(path string) (map[string]string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	out := map[string]string{}
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		k := strings.TrimSpace(parts[0])
		v := strings.TrimSpace(parts[1])
		v = strings.Trim(v, `"`)
		out[k] = v
	}
	return out, nil
}

func atoiDefault(m map[string]string, key string, def int) int {
	if s, ok := m[key]; ok {
		if n, err := strconv.Atoi(s); err == nil {
			return n
		}
	}
	return def
}

// LoadRules reads profile.name and the sealed rules.toml under config/profiles.
func LoadRules(configDir string) (Rules, error) {
	nameBytes, err := os.ReadFile(filepath.Join(configDir, "profile.name"))
	if err != nil {
		return SoftBaseline(), nil
	}
	profile := strings.TrimSpace(string(nameBytes))
	path := filepath.Join(configDir, "profiles", profile, "rules.toml")
	m, err := parseTOML(path)
	if err != nil {
		return SoftBaseline(), nil
	}
	base := SoftBaseline()
	r := Rules{
		RunID:       m["run_id"],
		RowLength:   atoiDefault(m, "row_length", base.RowLength),
		RingsToWin:  atoiDefault(m, "rings_to_win", base.RingsToWin),
		RingsStart:  atoiDefault(m, "rings_start", base.RingsStart),
		FlipEnabled: atoiDefault(m, "flip_enabled", base.FlipEnabled),
		LeaveMarker: atoiDefault(m, "leave_marker", base.LeaveMarker),
		WinPoints:   atoiDefault(m, "win_points", base.WinPoints),
		DrawPoints:  atoiDefault(m, "draw_points", base.DrawPoints),
		ConfigSeal:  m["config_seal"],
	}
	if r.RunID == "" {
		r.RunID = base.RunID
	}
	want := ExpectedSeal(r)
	r.SealOK = strings.EqualFold(r.ConfigSeal, want)
	if !r.SealOK {
		soft := SoftBaseline()
		soft.ConfigSeal = r.ConfigSeal
		soft.SealOK = false
		return soft, nil
	}
	return r, nil
}
