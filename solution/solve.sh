#!/bin/bash
set -euo pipefail
export PATH="/usr/local/go/bin:/usr/local/bin:${PATH}"

cd /app

cat > /app/internal/rules/load.go << 'GOEOF'
package rules

import (
	"encoding/json"
	"os"
)

// Policy holds table-rule flags used while simulating a hand.
type Policy struct {
	HintCost         int
	MaxInfo          int
	FiveRestoresInfo bool
	EmptyHintsOK     bool
	FuseOnSuccess    bool
	HintKeepsTurn    bool
	ScoreMode        string
	ScenariosDir     string
	OutputDir        string
	ScenarioOrder    []string
}

type engineFile struct {
	ScenariosDir  string   `json:"scenarios_dir"`
	OutputDir     string   `json:"output_dir"`
	ScenarioOrder []string `json:"scenario_order"`
}

// Load reads engine JSON and applies championship defaults only.
func Load(enginePath string) (Policy, error) {
	data, err := os.ReadFile(enginePath)
	if err != nil {
		return Policy{}, err
	}
	var ef engineFile
	if err := json.Unmarshal(data, &ef); err != nil {
		return Policy{}, err
	}
	return Policy{
		ScenariosDir:     ef.ScenariosDir,
		OutputDir:        ef.OutputDir,
		ScenarioOrder:    ef.ScenarioOrder,
		HintCost:         1,
		MaxInfo:          8,
		FiveRestoresInfo: true,
		EmptyHintsOK:     false,
		FuseOnSuccess:    false,
		HintKeepsTurn:    false,
		ScoreMode:        "sum",
	}, nil
}
GOEOF

cat > /app/internal/hint/hint.go << 'GOEOF'
package hint

import (
	"hanabi/internal/rules"
	"hanabi/internal/table"
	"strconv"
)

// Result describes the outcome of a hint attempt.
type Result struct {
	Applied bool
	Matched int
}

// Apply attempts a color or rank hint from the current player.
func Apply(g *table.Game, mv table.Move, policy rules.Policy) Result {
	if g.GameOver {
		return Result{}
	}
	if mv.To < 0 || mv.To >= g.Players || mv.To == g.Current {
		return Result{}
	}
	if g.Info < 1 {
		return Result{}
	}
	hand := g.Hands[mv.To]
	matched := 0
	switch mv.Kind {
	case "color":
		for _, card := range hand {
			if card.C == mv.Value {
				matched++
			}
		}
	case "rank":
		want, err := strconv.Atoi(mv.Value)
		if err != nil {
			return Result{}
		}
		for _, card := range hand {
			if card.R == want {
				matched++
			}
		}
	default:
		return Result{}
	}
	if matched == 0 {
		return Result{}
	}
	g.Info--
	_ = policy
	return Result{Applied: true, Matched: matched}
}
GOEOF

cat > /app/internal/play/play.go << 'GOEOF'
package play

import (
	"hanabi/internal/rules"
	"hanabi/internal/table"
)

// Result describes the outcome of a play attempt.
type Result struct {
	Applied  bool
	Success  bool
	Drew     bool
	Restored bool
	FuseLost bool
}

// Apply attempts to play the card at hand index for the current player.
func Apply(g *table.Game, index int, policy rules.Policy) Result {
	if g.GameOver {
		return Result{}
	}
	hand, card, ok := table.RemoveHandCard(g.Hands[g.Current], index)
	if !ok {
		return Result{}
	}
	g.Hands[g.Current] = hand

	expected := g.Fireworks[card.C] + 1
	success := card.R == expected && expected <= 5
	_ = policy

	out := Result{Applied: true}
	if success {
		g.Fireworks[card.C] = card.R
		out.Success = true
		if card.R == 5 && g.Info < 8 {
			g.Info++
			out.Restored = true
		}
		if table.Perfect(g.Fireworks) {
			g.GameOver = true
			g.EndReason = "perfect"
		}
	} else {
		g.Fuse--
		out.FuseLost = true
		if g.Fuse <= 0 {
			g.Fuse = 0
			g.GameOver = true
			g.EndReason = "fuse_out"
		}
	}

	if !g.GameOver {
		if drawn, ok := table.DrawTop(g); ok {
			g.Hands[g.Current] = append(g.Hands[g.Current], drawn)
			out.Drew = true
		}
	}
	return out
}
GOEOF

cat > /app/internal/discard/discard.go << 'GOEOF'
package discard

import (
	"hanabi/internal/rules"
	"hanabi/internal/table"
)

// Result describes the outcome of a discard attempt.
type Result struct {
	Applied bool
	Drew    bool
	Gained  int
}

// Apply discards the card at hand index for the current player.
func Apply(g *table.Game, index int, policy rules.Policy) Result {
	if g.GameOver {
		return Result{}
	}
	_ = policy
	hand, _, ok := table.RemoveHandCard(g.Hands[g.Current], index)
	if !ok {
		return Result{}
	}
	g.Hands[g.Current] = hand

	gained := 0
	if g.Info < 8 {
		g.Info++
		gained = 1
	}

	out := Result{Applied: true, Gained: gained}
	if drawn, ok := table.DrawTop(g); ok {
		g.Hands[g.Current] = append(g.Hands[g.Current], drawn)
		out.Drew = true
	}
	return out
}
GOEOF

cat > /app/internal/turn/turn.go << 'GOEOF'
package turn

import (
	"hanabi/internal/rules"
	"hanabi/internal/table"
)

// Advance moves ownership to the next player under championship rules.
func Advance(g *table.Game, actionType string, policy rules.Policy) {
	_ = actionType
	_ = policy
	if g.GameOver {
		return
	}
	g.Current = (g.Current + 1) % g.Players
	if g.DeckWasEmpty {
		g.FinalLeft--
		if g.FinalLeft <= 0 {
			g.GameOver = true
			if g.EndReason == "" || g.EndReason == "none" {
				g.EndReason = "deck_end"
			}
		}
	}
}
GOEOF

cat > /app/internal/scoring/score.go << 'GOEOF'
package scoring

import (
	"hanabi/internal/rules"
	"hanabi/internal/table"
)

// Compute returns the championship score: sum of firework ranks.
func Compute(fw map[string]int, policy rules.Policy) int {
	_ = policy
	return table.ScoreSum(fw)
}
GOEOF

cat > /app/internal/table/state.go << 'GOEOF'
package table

// Colors lists the five firework colors in championship order.
var Colors = []string{"R", "Y", "G", "B", "W"}

// Card is a single Hanabi card with color and rank.
type Card struct {
	C string `json:"c"`
	R int    `json:"r"`
}

// Move is one requested action from a scenario.
type Move struct {
	Type  string `json:"type"`
	To    int    `json:"to"`
	Kind  string `json:"kind"`
	Value string `json:"value"`
	Index int    `json:"index"`
}

// Game holds mutable table state for one scenario.
type Game struct {
	Players      int
	Hands        [][]Card
	Deck         []Card
	Info         int
	Fuse         int
	Fireworks    map[string]int
	Current      int
	FinalLeft    int
	DeckWasEmpty bool
	GameOver     bool
	EndReason    string
}

// CloneFireworks returns a copy of the firework map.
func CloneFireworks(src map[string]int) map[string]int {
	out := make(map[string]int, len(Colors))
	for _, c := range Colors {
		out[c] = src[c]
	}
	return out
}

// CloneHands deep-copies every hand.
func CloneHands(hands [][]Card) [][]Card {
	out := make([][]Card, len(hands))
	for i := range hands {
		out[i] = append([]Card(nil), hands[i]...)
	}
	return out
}

// CloneDeck copies the draw pile.
func CloneDeck(deck []Card) []Card {
	return append([]Card(nil), deck...)
}

// ScoreSum returns the championship score: sum of firework ranks.
func ScoreSum(fw map[string]int) int {
	total := 0
	for _, c := range Colors {
		total += fw[c]
	}
	return total
}

// Perfect reports whether every color stack is complete at rank 5.
func Perfect(fw map[string]int) bool {
	for _, c := range Colors {
		if fw[c] != 5 {
			return false
		}
	}
	return true
}

// DrawTop removes and returns the top deck card; ok is false when empty.
func DrawTop(g *Game) (Card, bool) {
	if len(g.Deck) == 0 {
		return Card{}, false
	}
	card := g.Deck[0]
	g.Deck = g.Deck[1:]
	if len(g.Deck) == 0 && !g.DeckWasEmpty {
		g.DeckWasEmpty = true
		g.FinalLeft = g.Players + 1
	}
	return card, true
}

// RemoveHandCard deletes index from a hand and returns the card.
func RemoveHandCard(hand []Card, index int) ([]Card, Card, bool) {
	if index < 0 || index >= len(hand) {
		return hand, Card{}, false
	}
	card := hand[index]
	out := append(append([]Card(nil), hand[:index]...), hand[index+1:]...)
	return out, card, true
}
GOEOF

cat > /app/internal/session/log.go << 'GOEOF'
package session

import (
	"encoding/json"
	"os"
	"path/filepath"

	"hanabi/internal/rules"
	"hanabi/internal/scoring"
)

// SessionLog is the per-scenario output document.
type SessionLog struct {
	Scenario        string         `json:"scenario"`
	MovesApplied    []int          `json:"moves_applied"`
	MovesRejected   []int          `json:"moves_rejected"`
	FinalInfoTokens int            `json:"final_info_tokens"`
	FinalFuseTokens int            `json:"final_fuse_tokens"`
	Fireworks       map[string]int `json:"fireworks"`
	Score           int            `json:"score"`
	GameOver        bool           `json:"game_over"`
	EndReason       string         `json:"end_reason"`
	HintsGiven      int            `json:"hints_given"`
	CardsPlayed     int            `json:"cards_played"`
	CardsDiscarded  int            `json:"cards_discarded"`
	PlyCount        int            `json:"ply_count"`
	FinalPlayer     int            `json:"final_player"`
}

// Summary aggregates totals across scenarios.
type Summary struct {
	ScenarioCount int            `json:"scenario_count"`
	TotalScore    int            `json:"total_score"`
	TotalHints    int            `json:"total_hints"`
	TotalPlays    int            `json:"total_plays"`
	TotalDiscards int            `json:"total_discards"`
	TotalPlies    int            `json:"total_plies"`
	EndReasons    map[string]int `json:"end_reasons"`
}

// FinalizeScore returns the championship sum score with no post clobber.
func FinalizeScore(fw map[string]int, policy rules.Policy) int {
	return scoring.Compute(fw, policy)
}

// WriteSession writes one scenario session log JSON file.
func WriteSession(dir string, log SessionLog) error {
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	path := filepath.Join(dir, "session_log.json")
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	enc := json.NewEncoder(f)
	enc.SetIndent("", "  ")
	return enc.Encode(log)
}

// WriteSummary writes the aggregate summary JSON.
func WriteSummary(path string, sum Summary) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	enc := json.NewEncoder(f)
	enc.SetIndent("", "  ")
	return enc.Encode(sum)
}
GOEOF

go build -o /app/bin/hanabi ./cmd/hanabi
rm -rf /app/output/*
/app/bin/hanabi

echo "Oracle completed."
