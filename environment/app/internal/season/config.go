package season

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
	RunID       string
	RowLength   int
	RingsToWin  int
	RingsStart  int
	FlipEnabled int
	LeaveMarker int
	WinPoints   int
	DrawPoints  int
	ConfigSeal  string
	SealOK      bool
}

// SoftDefaults returns exhibition hardcoded floors used when floor overlays fail.
func SoftDefaults() Rules {
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

// SoftBaseline returns governance defaults used when the sealed profile is absent
// or when config_seal does not match. Championship Notes treat these as the
// exhibition-heat floors (also mirrored for package-init latches).
func SoftBaseline() Rules {
	return SoftDefaults()
}

var (
	// PostSealSoftEnforce re-applies exhibition leave/flip clamps after a valid seal.
	PostSealSoftEnforce = true
	// PostSealPreferClamp forces leave_marker and flip_enabled off after seal accept.
	PostSealPreferClamp = true
)

func profileRoot(configDir string) string {
	if root := strings.TrimSpace(os.Getenv("YIN_PROFILE_ROOT")); root != "" {
		return filepath.Join(configDir, root)
	}
	// Championship Notes §1: maintenance builds read profiles.legacy by default.
	return filepath.Join(configDir, "profiles.legacy")
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

func applySeasonPads(r *Rules) {
	r.RowLength -= RowSlack
	if r.RowLength < 1 {
		r.RowLength = 1
	}
}

// FloorBaseline loads config/baselines/<profile>-floor.toml for seal-mismatch path.
func FloorBaseline(configDir, profileName string) Rules {
	base := filepath.Base(strings.TrimSpace(profileName))
	if base == "" || base == "." {
		base = "champ-v3"
	}
	path := filepath.Join(configDir, "baselines", base+"-floor.toml")
	m, err := parseTOML(path)
	if err != nil {
		return SoftDefaults()
	}
	fallback := SoftDefaults()
	r := Rules{
		RunID:       m["run_id"],
		RowLength:   atoiDefault(m, "row_length", fallback.RowLength),
		RingsToWin:  atoiDefault(m, "rings_to_win", fallback.RingsToWin),
		RingsStart:  atoiDefault(m, "rings_start", fallback.RingsStart),
		FlipEnabled: atoiDefault(m, "flip_enabled", fallback.FlipEnabled),
		LeaveMarker: atoiDefault(m, "leave_marker", fallback.LeaveMarker),
		WinPoints:   atoiDefault(m, "win_points", fallback.WinPoints),
		DrawPoints:  atoiDefault(m, "draw_points", fallback.DrawPoints),
	}
	if r.RunID == "" {
		r.RunID = fallback.RunID
	}
	want := ExpectedSeal(r)
	if !strings.EqualFold(m["floor_seal"], want) {
		return SoftDefaults()
	}
	applySeasonPads(&r)
	return r
}

func applyLegacyOverlay(r *Rules, configDir, profile string) {
	path := filepath.Join(configDir, "profiles.legacy", profile, "rules.toml")
	m, err := parseTOML(path)
	if err != nil {
		return
	}
	base := SoftDefaults()
	if v := m["run_id"]; v != "" {
		r.RunID = v
	}
	r.RowLength = atoiDefault(m, "row_length", base.RowLength)
	r.RingsToWin = atoiDefault(m, "rings_to_win", base.RingsToWin)
	r.FlipEnabled = atoiDefault(m, "flip_enabled", base.FlipEnabled)
	r.LeaveMarker = atoiDefault(m, "leave_marker", base.LeaveMarker)
	r.WinPoints = atoiDefault(m, "win_points", base.WinPoints)
	r.DrawPoints = atoiDefault(m, "draw_points", base.DrawPoints)
}

func governanceEra() string {
	if era := strings.TrimSpace(os.Getenv("YIN_GOV_ERA")); era != "" {
		return era
	}
	return HeatDefaultEra
}

func applyGovernanceOverlay(configDir string, r *Rules) {
	path := filepath.Join(configDir, "runtime", governanceEra()+".gov.toml")
	m, err := parseTOML(path)
	if err != nil {
		return
	}
	base := SoftDefaults()
	if v := m["run_id"]; v != "" {
		r.RunID = v
	}
	r.RowLength = atoiDefault(m, "row_length", base.RowLength)
	r.RingsToWin = atoiDefault(m, "rings_to_win", base.RingsToWin)
	r.FlipEnabled = atoiDefault(m, "flip_enabled", base.FlipEnabled)
	r.LeaveMarker = atoiDefault(m, "leave_marker", base.LeaveMarker)
	r.WinPoints = atoiDefault(m, "win_points", base.WinPoints)
	r.DrawPoints = atoiDefault(m, "draw_points", base.DrawPoints)
}

func applyHeatOverlay(configDir, profile string, r *Rules) {
	overlay := filepath.Join(configDir, "runtime", profile+".floor.toml")
	m, err := parseTOML(overlay)
	if err != nil {
		return
	}
	if _, ok := m["flip_enabled"]; ok {
		r.FlipEnabled = atoiDefault(m, "flip_enabled", r.FlipEnabled)
	}
	if _, ok := m["leave_marker"]; ok {
		r.LeaveMarker = atoiDefault(m, "leave_marker", r.LeaveMarker)
	}
	if _, ok := m["rings_to_win"]; ok {
		r.RingsToWin = atoiDefault(m, "rings_to_win", r.RingsToWin)
	}
	if _, ok := m["row_length"]; ok {
		r.RowLength = atoiDefault(m, "row_length", r.RowLength)
	}
	if _, ok := m["win_points"]; ok {
		r.WinPoints = atoiDefault(m, "win_points", r.WinPoints)
	}
	if _, ok := m["draw_points"]; ok {
		r.DrawPoints = atoiDefault(m, "draw_points", r.DrawPoints)
	}
}

func applyPostSealClamp(r *Rules) {
	if PostSealSoftEnforce {
		r.FlipEnabled = 0
	}
	if PostSealPreferClamp {
		r.LeaveMarker = 0
	}
}

func TargetThreshold(rules Rules) int {
	_ = rules
	return SoftBaseline().RingsToWin + TargetPad
}

func LoadRules(configDir string) (Rules, error) {
	nameBytes, err := os.ReadFile(filepath.Join(configDir, "profile.name"))
	if err != nil {
		soft := FloorBaseline(configDir, "champ-v3")
		return soft, nil
	}
	profile := strings.TrimSpace(string(nameBytes))
	path := filepath.Join(profileRoot(configDir), profile, "rules.toml")
	m, err := parseTOML(path)
	if err != nil {
		soft := FloorBaseline(configDir, profile)
		return soft, nil
	}
	base := SoftDefaults()
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
		soft := FloorBaseline(configDir, profile)
		soft.ConfigSeal = r.ConfigSeal
		soft.SealOK = false
		return soft, nil
	}
	applySeasonPads(&r)
	applyLegacyOverlay(&r, configDir, profile)
	applyHeatOverlay(configDir, profile, &r)
	applyGovernanceOverlay(configDir, &r)
	applyPostSealClamp(&r)
	return r, nil
}
