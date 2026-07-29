package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"hanabi/internal/discard"
	"hanabi/internal/hint"
	"hanabi/internal/play"
	"hanabi/internal/rules"
	"hanabi/internal/session"
	"hanabi/internal/table"
	"hanabi/internal/turn"
)

type scenarioFile struct {
	Name        string         `json:"name"`
	Players     int            `json:"players"`
	InfoTokens  int            `json:"info_tokens"`
	FuseTokens  int            `json:"fuse_tokens"`
	Fireworks   map[string]int `json:"fireworks"`
	Hands       [][]table.Card `json:"hands"`
	Deck        []table.Card   `json:"deck"`
	StartPlayer int            `json:"start_player"`
	Moves       []table.Move   `json:"moves"`
}

func main() {
	enginePath := "/app/config/engine.json"
	if v := os.Getenv("HANABI_ENGINE_CONFIG"); v != "" {
		enginePath = v
	}
	policy, err := rules.Load(enginePath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "config: %v\n", err)
		os.Exit(1)
	}

	sum := session.Summary{
		EndReasons: map[string]int{
			"none": 0, "fuse_out": 0, "perfect": 0, "deck_end": 0,
		},
	}

	for _, name := range policy.ScenarioOrder {
		path := filepath.Join(policy.ScenariosDir, name+".json")
		sc, err := loadScenario(path)
		if err != nil {
			fmt.Fprintf(os.Stderr, "scenario %s: %v\n", name, err)
			os.Exit(1)
		}
		log := playScenario(sc, policy)
		outDir := filepath.Join(policy.OutputDir, name)
		if err := session.WriteSession(outDir, log); err != nil {
			fmt.Fprintf(os.Stderr, "write %s: %v\n", name, err)
			os.Exit(1)
		}
		sum.ScenarioCount++
		sum.TotalScore += log.Score
		sum.TotalHints += log.HintsGiven
		sum.TotalPlays += log.CardsPlayed
		sum.TotalDiscards += log.CardsDiscarded
		sum.TotalPlies += log.PlyCount
		sum.EndReasons[log.EndReason]++
		fmt.Printf("scenario %s done\n", name)
	}

	if err := session.WriteSummary(filepath.Join(policy.OutputDir, "summary.json"), sum); err != nil {
		fmt.Fprintf(os.Stderr, "summary: %v\n", err)
		os.Exit(1)
	}
}

func loadScenario(path string) (scenarioFile, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return scenarioFile{}, err
	}
	var sc scenarioFile
	if err := json.Unmarshal(data, &sc); err != nil {
		return scenarioFile{}, err
	}
	return sc, nil
}

func playScenario(sc scenarioFile, policy rules.Policy) session.SessionLog {
	fw := table.CloneFireworks(sc.Fireworks)
	for _, c := range table.Colors {
		if _, ok := fw[c]; !ok {
			fw[c] = 0
		}
	}
	g := &table.Game{
		Players:   sc.Players,
		Hands:     table.CloneHands(sc.Hands),
		Deck:      table.CloneDeck(sc.Deck),
		Info:      sc.InfoTokens,
		Fuse:      sc.FuseTokens,
		Fireworks: fw,
		Current:   sc.StartPlayer,
		EndReason: "none",
	}

	applied := make([]int, 0)
	rejected := make([]int, 0)
	hints := 0
	plays := 0
	discards := 0

	for i, mv := range sc.Moves {
		if g.GameOver {
			rejected = append(rejected, i)
			continue
		}
		switch mv.Type {
		case "hint":
			res := hint.Apply(g, mv, policy)
			if !res.Applied {
				rejected = append(rejected, i)
				continue
			}
			hints++
			applied = append(applied, i)
			turn.Advance(g, "hint", policy)
		case "play":
			res := play.Apply(g, mv.Index, policy)
			if !res.Applied {
				rejected = append(rejected, i)
				continue
			}
			plays++
			applied = append(applied, i)
			turn.Advance(g, "play", policy)
		case "discard":
			res := discard.Apply(g, mv.Index, policy)
			if !res.Applied {
				rejected = append(rejected, i)
				continue
			}
			discards++
			applied = append(applied, i)
			turn.Advance(g, "discard", policy)
		default:
			rejected = append(rejected, i)
		}
	}

	reason := g.EndReason
	if reason == "" {
		reason = "none"
	}

	log := session.SessionLog{
		Scenario:        sc.Name,
		MovesApplied:    applied,
		MovesRejected:   rejected,
		FinalInfoTokens: g.Info,
		FinalFuseTokens: g.Fuse,
		Fireworks:       table.CloneFireworks(g.Fireworks),
		Score:           session.FinalizeScore(g.Fireworks, policy),
		GameOver:        g.GameOver,
		EndReason:       reason,
		HintsGiven:      hints,
		CardsPlayed:     plays,
		CardsDiscarded:  discards,
		PlyCount:        len(applied),
		FinalPlayer:     g.Current,
	}
	return log
}
