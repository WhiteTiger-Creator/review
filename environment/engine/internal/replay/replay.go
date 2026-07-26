package replay

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

type Generation struct {
	Dir string
}

type Summary struct {
	MatchID         string         `json:"match_id"`
	Opponent        string         `json:"opponent"`
	Seed            int64          `json:"seed"`
	Reason          string         `json:"reason"`
	Scores          map[string]int `json:"scores"`
	Plies           int            `json:"plies"`
	Determinism     string         `json:"determinism"`
	AcceptanceFloor int            `json:"acceptance_floor"`
	Accepted        bool           `json:"accepted"`
}

type Terminal struct {
	Reason   string         `json:"reason"`
	Scores   map[string]int `json:"scores"`
	Winner   string         `json:"winner"`
	Accepted bool           `json:"accepted"`
}

type Diagnostics struct {
	BotLegalActions int    `json:"bot_legal_actions"`
	BotFaults       int    `json:"bot_faults"`
	BeliefFaults    int    `json:"belief_faults"`
	ProtocolOK      bool   `json:"protocol_ok"`
	Notes           string `json:"notes"`
}

func Stage(outputRoot, matchID string) (*Generation, error) {
	gen := filepath.Join(outputRoot, "generations", matchID+".staging")
	if err := os.RemoveAll(gen); err != nil {
		return nil, err
	}
	if err := os.MkdirAll(gen, 0o755); err != nil {
		return nil, err
	}
	return &Generation{Dir: gen}, nil
}

func (g *Generation) WriteJSON(name string, v any) error {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(filepath.Join(g.Dir, name), b, 0o644)
}

func (g *Generation) AppendJSONL(name string, v any) error {
	b, err := json.Marshal(v)
	if err != nil {
		return err
	}
	f, err := os.OpenFile(filepath.Join(g.Dir, name), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.Write(append(b, '\n'))
	return err
}

func (g *Generation) FlushPublish(outputRoot, matchID string, injectFail string) error {
	required := []string{"summary.json", "plies.jsonl", "boards.json", "visibility.jsonl", "relay.jsonl", "terminal.json", "bot-diagnostics.json"}
	for _, r := range required {
		if _, err := os.Stat(filepath.Join(g.Dir, r)); err != nil {
			return fmt.Errorf("missing %s", r)
		}
	}
	if injectFail == "validation" {
		return fmt.Errorf("injected validation failure")
	}
	// fsync-ish: reopen and sync directory entries by rewriting
	final := filepath.Join(outputRoot, "generations", matchID)
	if injectFail == "rename" {
		return fmt.Errorf("injected rename failure")
	}
	_ = os.RemoveAll(final)
	if err := os.Rename(g.Dir, final); err != nil {
		return err
	}
	cur := filepath.Join(outputRoot, "current")
	tmp := cur + ".tmp"
	if err := os.WriteFile(tmp, []byte("generations/"+matchID+"\n"), 0o644); err != nil {
		return err
	}
	if injectFail == "pointer" {
		_ = os.Remove(tmp)
		return fmt.Errorf("injected pointer failure")
	}
	return os.Rename(tmp, cur)
}

func ReadCurrent(outputRoot string) (string, error) {
	b, err := os.ReadFile(filepath.Join(outputRoot, "current"))
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(b)), nil
}

func ReadNormalized(outputRoot string) ([]byte, error) {
	cur, err := ReadCurrent(outputRoot)
	if err != nil {
		return nil, err
	}
	sum := filepath.Join(outputRoot, cur, "summary.json")
	plies := filepath.Join(outputRoot, cur, "plies.jsonl")
	term := filepath.Join(outputRoot, cur, "terminal.json")
	a, err := os.ReadFile(sum)
	if err != nil {
		return nil, err
	}
	b, err := os.ReadFile(plies)
	if err != nil {
		return nil, err
	}
	c, err := os.ReadFile(term)
	if err != nil {
		return nil, err
	}
	out := append([]byte{}, a...)
	out = append(out, b...)
	out = append(out, c...)
	return out, nil
}
