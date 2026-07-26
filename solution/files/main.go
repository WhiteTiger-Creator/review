package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintf(os.Stderr, "usage: skykingdom play <scenario>|eval\n")
		os.Exit(2)
	}
	switch os.Args[1] {
	case "eval":
		if err := runEval(os.Stdin, os.Stdout); err != nil {
			_ = json.NewEncoder(os.Stdout).Encode(map[string]any{"ok": false, "error": err.Error()})
			os.Exit(1)
		}
	case "play":
		if len(os.Args) != 3 {
			fmt.Fprintf(os.Stderr, "usage: skykingdom play <scenario.json>\n")
			os.Exit(2)
		}
		if err := runPlay(os.Args[2]); err != nil {
			fmt.Fprintf(os.Stderr, "%v\n", err)
			os.Exit(1)
		}
	default:
		fmt.Fprintf(os.Stderr, "unknown mode\n")
		os.Exit(2)
	}
}

type evalReq struct {
	Op       string          `json:"op"`
	Scenario json.RawMessage `json:"scenario"`
	Game     json.RawMessage `json:"game"`
	Line     string          `json:"line"`
	Commands []string        `json:"commands"`
	From     string          `json:"from"`
	To       string          `json:"to"`
	FleetID  string          `json:"fleet_id"`
	Target   string          `json:"target"`
}

func runEval(r io.Reader, w io.Writer) error {
	var req evalReq
	if err := json.NewDecoder(r).Decode(&req); err != nil {
		return err
	}
	enc := json.NewEncoder(w)
	respond := func(result any) error {
		return enc.Encode(map[string]any{"ok": true, "result": result})
	}
	fail := func(err error) error {
		return enc.Encode(map[string]any{"ok": false, "error": err.Error()})
	}
	switch req.Op {
	case "hullCatalog":
		return respond(hullCatalog)
	case "techCatalog":
		return respond(techCatalog)
	case "validateScenario":
		var s Scenario
		if err := json.Unmarshal(req.Scenario, &s); err != nil {
			return err
		}
		out, err := validateScenario(s)
		if err != nil {
			return fail(err)
		}
		return respond(out)
	case "createGame":
		var s Scenario
		if err := json.Unmarshal(req.Scenario, &s); err != nil {
			return err
		}
		g, err := createGame(s)
		if err != nil {
			return fail(err)
		}
		return respond(g)
	case "shortestPath":
		g, err := decodeGame(req.Game)
		if err != nil {
			return err
		}
		d, path, err := shortestPath(g, req.From, req.To)
		if err != nil {
			return fail(err)
		}
		return respond(map[string]any{"distance": d, "path": path})
	case "pathFuelCost":
		g, err := decodeGame(req.Game)
		if err != nil {
			return err
		}
		raw, paid, path, err := pathFuelCost(g, req.FleetID, req.To)
		if err != nil {
			return fail(err)
		}
		return respond(map[string]any{"raw_cost": raw, "paid": paid, "path": path})
	case "isSupplied":
		g, err := decodeGame(req.Game)
		if err != nil {
			return err
		}
		return respond(isSupplied(g, req.FleetID))
	case "combatPreview":
		g, err := decodeGame(req.Game)
		if err != nil {
			return err
		}
		res, err := combatPreview(g, req.FleetID, req.Target)
		if err != nil {
			return fail(err)
		}
		return respond(res)
	case "simulateClash":
		g, err := decodeGame(req.Game)
		if err != nil {
			return err
		}
		ng, clash, err := simulateClash(g, req.FleetID, req.Target)
		if err != nil {
			return fail(err)
		}
		return respond(map[string]any{"game": ng, "clash": clash})
	case "executeCommand":
		g, err := decodeGame(req.Game)
		if err != nil {
			return err
		}
		out, err := executeCommand(g, req.Line)
		if err != nil {
			return err
		}
		return respond(map[string]any{"game": g, "output": out})
	case "replayRun":
		var s Scenario
		if err := json.Unmarshal(req.Scenario, &s); err != nil {
			return err
		}
		g, outs, err := replayRun(s, req.Commands)
		if err != nil {
			return fail(err)
		}
		return respond(map[string]any{"game": g, "outputs": outs})
	case "scoreGame":
		g, err := decodeGame(req.Game)
		if err != nil {
			return err
		}
		return respond(scoreGame(g))
	case "renderGame":
		g, err := decodeGame(req.Game)
		if err != nil {
			return err
		}
		return respond(renderGame(g))
	case "validateGame":
		g, err := decodeGame(req.Game)
		if err != nil {
			return err
		}
		legal, viol := validateGame(g)
		return respond(map[string]any{"legal": legal, "violations": viol})
	default:
		return fmt.Errorf("unknown op")
	}
}

func decodeGame(raw json.RawMessage) (*Game, error) {
	var g Game
	if err := json.Unmarshal(raw, &g); err != nil {
		return nil, err
	}
	g.graph = nil
	return &g, nil
}

func runPlay(path string) error {
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	var s Scenario
	if err := json.Unmarshal(b, &s); err != nil {
		return err
	}
	g, err := createGame(s)
	if err != nil {
		return err
	}
	fmt.Print(renderGame(g))
	sc := bufio.NewScanner(os.Stdin)
	for sc.Scan() {
		line := sc.Text()
		out, err := executeCommand(g, line)
		if err != nil {
			return err
		}
		fmt.Println(out)
		parts := strings.Fields(strings.TrimSpace(line))
		if len(parts) > 0 && strings.EqualFold(parts[0], "EXIT") {
			return nil
		}
	}
	return sc.Err()
}
