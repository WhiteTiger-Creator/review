package game

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
)

func Finalize(result *Result) {
	for turnIndex := range result.Turns {
		turn := &result.Turns[turnIndex]
		sort.Slice(turn.Nodes, func(i, j int) bool { return turn.Nodes[i].ID < turn.Nodes[j].ID })
		sort.Slice(turn.Fleets, func(i, j int) bool { return turn.Fleets[i].ID < turn.Fleets[j].ID })
		sort.Slice(turn.ScoreDelta, func(i, j int) bool { return turn.ScoreDelta[i].PlayerID < turn.ScoreDelta[j].PlayerID })
		sort.Slice(turn.Scores, func(i, j int) bool { return turn.Scores[i].PlayerID < turn.Scores[j].PlayerID })
	}
	sort.Slice(result.Final.Nodes, func(i, j int) bool { return result.Final.Nodes[i].ID < result.Final.Nodes[j].ID })
	sort.Slice(result.Final.Fleets, func(i, j int) bool { return result.Final.Fleets[i].ID < result.Final.Fleets[j].ID })
	sort.Slice(result.Final.Scores, func(i, j int) bool { return result.Final.Scores[i].PlayerID < result.Final.Scores[j].PlayerID })
	hash := sha256.New()
	for _, turn := range result.Turns {
		fmt.Fprintf(hash, "T\t%d\t%s\n", turn.Turn, turn.UTC)
		for _, node := range turn.Nodes {
			fmt.Fprintf(hash, "N\t%s\t%.6f\t%.6f\t%s\n", node.ID, node.TideM, node.EffectiveDepthM, node.Owner)
		}
		for _, fleet := range turn.Fleets {
			fmt.Fprintf(hash, "F\t%s\t%s\t%s\n", fleet.ID, fleet.NodeID, fleet.Status)
		}
		for _, score := range turn.Scores {
			fmt.Fprintf(hash, "S\t%s\t%d\n", score.PlayerID, score.Points)
		}
	}
	result.Summary = Summary{
		TurnCount:  len(result.Turns),
		FleetCount: len(result.Final.Fleets),
		SHA256:     hex.EncodeToString(hash.Sum(nil)),
	}
}

func WriteAtomic(path string, result Result) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	file, err := os.CreateTemp(filepath.Dir(path), ".tidefront-*.tmp")
	if err != nil {
		return err
	}
	name := file.Name()
	committed := false
	defer func() {
		_ = file.Close()
		if !committed {
			_ = os.Remove(name)
		}
	}()
	writer := bufio.NewWriter(file)
	encoder := json.NewEncoder(writer)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(result); err != nil {
		return err
	}
	if err := writer.Flush(); err != nil {
		return err
	}
	if err := file.Sync(); err != nil {
		return err
	}
	if err := file.Close(); err != nil {
		return err
	}
	if err := os.Chmod(name, 0o644); err != nil {
		return err
	}
	if err := os.Rename(name, path); err != nil {
		return fmt.Errorf("commit output: %w", err)
	}
	committed = true
	return nil
}
