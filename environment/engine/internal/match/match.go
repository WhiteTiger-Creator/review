package match

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"

	"fog-chess-relay/internal/board"
	"fog-chess-relay/internal/fog"
	"fog-chess-relay/internal/integrity"
	"fog-chess-relay/internal/legal"
	"fog-chess-relay/internal/protocol"
	"fog-chess-relay/internal/relay"
	"fog-chess-relay/internal/replay"
)

type PositionSpec struct {
	ID               string                       `json:"id"`
	Seed             int64                        `json:"seed"`
	AlphaFEN         string                       `json:"alpha_fen"`
	BetaFEN          string                       `json:"beta_fen"`
	TeamAWhiteOn     string                       `json:"team_a_white_on"`
	RelayDelay       int                          `json:"relay_delay"`
	RelayCapacity    int                          `json:"relay_capacity"`
	FogRadius        int                          `json:"fog_radius"`
	Activation       []string                     `json:"activation"`
	Horizon          int                          `json:"horizon"`
	Opponent         string                       `json:"opponent"`
	DropRestrict     []string                     `json:"drop_restrictions"`
	PieceIDMap       map[string]string            `json:"piece_id_map,omitempty"`
	Public           bool                         `json:"public"`
	AcceptanceFloor  int                          `json:"acceptance_floor"`
	InitialQueues    map[string][]relay.QueuedPiece `json:"initial_queues,omitempty"`
}

type OpponentDoctrine struct {
	Name   string `json:"name"`
	Style  string `json:"style"`
	SeedBias int64 `json:"seed_bias"`
}

type Controller struct {
	Root       string
	OutputRoot string
	InjectFail string
}

type seatBot struct {
	cmd *exec.Cmd
	in  io.WriteCloser
	out *bufio.Reader
}

func LoadPosition(path string) (PositionSpec, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return PositionSpec{}, err
	}
	var p PositionSpec
	if err := json.Unmarshal(b, &p); err != nil {
		return PositionSpec{}, err
	}
	if p.TeamAWhiteOn == "" {
		p.TeamAWhiteOn = "alpha"
	}
	if p.RelayDelay <= 0 {
		p.RelayDelay = 1
	}
	if p.RelayCapacity <= 0 {
		p.RelayCapacity = 3
	}
	if p.Horizon <= 0 {
		p.Horizon = 40
	}
	if len(p.Activation) == 0 {
		p.Activation = []string{"alpha", "beta"}
	}
	return p, nil
}

func LoadOpponent(root, name string) (OpponentDoctrine, error) {
	b, err := os.ReadFile(filepath.Join(root, "opponents", name+".json"))
	if err != nil {
		return OpponentDoctrine{}, err
	}
	var o OpponentDoctrine
	if err := json.Unmarshal(b, &o); err != nil {
		return OpponentDoctrine{}, err
	}
	return o, nil
}

func (c *Controller) VerifyAssets() error {
	man, err := integrity.LoadManifest(filepath.Join(c.Root, "integrity", "manifest.json"))
	if err != nil {
		return err
	}
	return integrity.Verify(c.Root, man)
}

func (c *Controller) RunMatch(pos PathOrSpec, botPath string, compile bool) error {
	spec, err := pos.Load()
	if err != nil {
		return err
	}
	if err := c.VerifyAssets(); err != nil {
		return err
	}
	opp, err := LoadOpponent(c.Root, spec.Opponent)
	if err != nil {
		return err
	}
	alpha, err := board.ParseFEN(spec.AlphaFEN, "alpha")
	if err != nil {
		return err
	}
	beta, err := board.ParseFEN(spec.BetaFEN, "beta")
	if err != nil {
		return err
	}
	if err := board.ValidateBasic(alpha); err != nil {
		return fmt.Errorf("alpha: %w", err)
	}
	if err := board.ValidateBasic(beta); err != nil {
		return fmt.Errorf("beta: %w", err)
	}
	if legal.IsCheckmate(alpha) || legal.IsStalemate(alpha) || legal.IsCheckmate(beta) || legal.IsStalemate(beta) {
		if !strings.Contains(spec.ID, "terminal-fixture") {
			return fmt.Errorf("already-terminal state")
		}
	}
	applyPieceMap(alpha, spec.PieceIDMap)
	applyPieceMap(beta, spec.PieceIDMap)

	bin := botPath
	workDir := botPath
	strategy := filepath.Join(botPath, "strategy.json")
	if st, err := os.Stat(botPath); err == nil && st.IsDir() {
		if _, err := os.Stat(strategy); err != nil {
			return fmt.Errorf("playbook missing strategy.json under %s", botPath)
		}
		player := filepath.Join(c.Root, "bin", "relayplayer")
		if _, err := os.Stat(player); err != nil {
			return fmt.Errorf("sealed relayplayer missing: %v", err)
		}
		bin = player
	} else if compile {
		// Legacy compile path retained only for local engine development; production uses sealed player.
		tmp, err := os.MkdirTemp("", "relaybot-build-*")
		if err != nil {
			return err
		}
		defer os.RemoveAll(tmp)
		if err := copyTree(botPath, tmp); err != nil {
			return err
		}
		cmd := exec.Command("go", "build", "-o", filepath.Join(tmp, "relaybot"), ".")
		cmd.Dir = tmp
		cmd.Env = append(os.Environ(), "GOFLAGS=-mod=mod", "CGO_ENABLED=0")
		if out, err := cmd.CombinedOutput(); err != nil {
			return fmt.Errorf("bot compile failed: %v: %s", err, out)
		}
		bin = filepath.Join(tmp, "relaybot")
		workDir = tmp
		strategy = ""
	}

	agent, err := startBot(bin, workDir, strategy)
	if err != nil {
		return err
	}
	defer agent.close()

	rm := relay.NewManager(spec.RelayCapacity, spec.RelayDelay)
	for team, items := range spec.InitialQueues {
		if q := rm.Queues[team]; q != nil {
			q.Items = append([]relay.QueuedPiece{}, items...)
		}
	}
	fogA := fog.NewTracker(spec.FogRadius)
	fogB := fog.NewTracker(spec.FogRadius)
	trackers := map[string]*fog.Tracker{"alpha": fogA, "beta": fogB}
	boards := map[string]*board.Board{"alpha": alpha, "beta": beta}
	repCounts := map[string]map[uint64]int{
		"alpha": {},
		"beta":  {},
	}

	gen, err := replay.Stage(c.OutputRoot, spec.ID)
	if err != nil {
		return err
	}
	_ = gen.WriteJSON("boards.json", map[string]string{
		"alpha": alpha.ToFEN(),
		"beta":  beta.ToFEN(),
	})

	scores := map[string]int{"team_a": 0, "team_b": 0}
	reason := "horizon"
	botLegal := 0
	botFaults := 0
	beliefFaults := 0
	requests := map[string]string{}
	teamARequests := 0
	ply := 0

	for step := 0; step < spec.Horizon; step++ {
		boardID := spec.Activation[step%len(spec.Activation)]
		b := boards[boardID]
		h := legal.ZobristLike(b)
		repCounts[boardID][h]++

		if legal.IsCheckmate(b) {
			winner := teamOfColor(b.Side.Opponent(), boardID, spec.TeamAWhiteOn)
			scores[winner] += 100
			reason = "checkmate:" + boardID
			break
		}
		if legal.IsStalemate(b) {
			reason = "stalemate:" + boardID
			break
		}
		if repCounts[boardID][h] >= 3 {
			reason = "repetition:" + boardID
			// repetition while behind: punish the side that would otherwise idle the draw
			matA := materialTeam(boards, "team_a", spec.TeamAWhiteOn)
			matB := materialTeam(boards, "team_b", spec.TeamAWhiteOn)
			sideTeam := teamOfColor(b.Side, boardID, spec.TeamAWhiteOn)
			if sideTeam == "team_a" && matA < matB {
				scores["team_a"] -= 5
			} else if sideTeam == "team_b" && matB < matA {
				scores["team_b"] -= 5
			}
			break
		}

		side := b.Side
		team := teamOfColor(side, boardID, spec.TeamAWhiteOn)
		view := trackers[boardID].Observe(b, side, nil)
		ready := rm.Ready(team)
		readyKinds := []string{}
		for _, it := range ready {
			readyKinds = append(readyKinds, it.Kind.String())
		}
		sort.Strings(readyKinds)
		moves := legal.LegalMoves(b)
		dropMoves := []legal.Move{}
		seen := map[board.Kind]bool{}
		for _, it := range ready {
			if seen[it.Kind] {
				continue
			}
			seen[it.Kind] = true
			dropMoves = append(dropMoves, legal.LegalDrops(b, it.Kind)...)
		}
		obs := protocol.Observation{
			Type: "observation", MatchID: spec.ID, Board: boardID, Side: side.String(), Team: team,
			Ply: ply, Step: step, Horizon: spec.Horizon,
			VisibleSquares: view.Visible, Pieces: view.Pieces, Sightings: view.Sightings, Check: view.Check,
			ReadyDrops: readyKinds, QueueDelay: spec.RelayDelay, QueueCapacity: spec.RelayCapacity,
			QueueLen: len(rm.Queues[team].Items),
			LegalMoves: protocol.MoveStrings(moves), LegalDrops: protocol.MoveStrings(dropMoves),
			PublicEvents: append([]relay.Event{}, rm.Events...),
			RequestHint: requests[team], SeedHint: fmt.Sprintf("%d", spec.Seed),
		}
		_ = gen.AppendJSONL("visibility.jsonl", obs)

		var action protocol.Action
		if team == "team_a" {
			if err := protocol.Encode(agent.in, obs); err != nil {
				botFaults++
				reason = "protocol_fault"
				break
			}
			action, err = protocol.DecodeAction(agent.out)
			if err != nil {
				botFaults++
				reason = "protocol_fault"
				break
			}
		} else {
			action = chooseOpponent(opp, spec, b, boardID, moves, dropMoves, readyKinds, requests["team_b"], step)
		}

		applied := false
		var chosen legal.Move
		canMove := len(moves) > 0 || len(dropMoves) > 0
		if action.Request != "" {
			requests[team] = action.Request
			applied = true
			if team == "team_a" {
				teamARequests++
			}
			_ = gen.AppendJSONL("plies.jsonl", map[string]any{"ply": ply, "board": boardID, "team": team, "action": "request", "value": action.Request})
		} else if action.Hold {
			// Hold is only legal when no board reply exists, or as idle when not in check
			// with an empty move/drop set. Holding while checked with replies is a fault.
			if view.Check && canMove {
				if team == "team_a" {
					botFaults++
					reason = "hold_in_check"
					break
				}
			} else if canMove && !view.Check {
				// Idle holds while legal play remains are faults for the agent seat.
				if team == "team_a" {
					botFaults++
					reason = "idle_hold"
					break
				}
			}
			applied = true
			_ = gen.AppendJSONL("plies.jsonl", map[string]any{"ply": ply, "board": boardID, "team": team, "action": "hold"})
		} else if action.Drop != nil {
			mv, err := protocol.ParseMoveAction(action)
			if err == nil {
				for _, d := range dropMoves {
					if d.IsDrop && d.DropKind == mv.DropKind && d.To == mv.To {
						if restricted(spec.DropRestrict, d) {
							continue
						}
						if _, ok := rm.Consume(team, d.DropKind); ok {
							nb, _ := legal.Apply(b, d)
							boards[boardID] = nb
							chosen = d
							applied = true
							rm.Events[len(rm.Events)-1].Board = boardID
							rm.Events[len(rm.Events)-1].Square = d.To.String()
						}
						break
					}
				}
			}
		} else if action.Move != "" {
			mv, err := protocol.ParseMoveAction(action)
			if err == nil {
				for _, lm := range moves {
					if lm.From == mv.From && lm.To == mv.To && lm.Promote == mv.Promote {
						nb, cap := legal.Apply(b, lm)
						if !cap.IsEmpty() && cap.Kind != board.King {
							capTeam := relay.TeamForCapture(side, boardID, spec.TeamAWhiteOn)
							rm.Capture(capTeam, boardID, cap.ID, cap.Kind)
						}
						boards[boardID] = nb
						chosen = lm
						applied = true
						break
					}
				}
			}
		}
		if !applied {
			if team == "team_a" {
				botFaults++
				reason = "illegal_action"
				break
			}
			// opponent fallback: first legal move
			if len(moves) > 0 {
				lm := moves[0]
				nb, cap := legal.Apply(b, lm)
				if !cap.IsEmpty() && cap.Kind != board.King {
					capTeam := relay.TeamForCapture(side, boardID, spec.TeamAWhiteOn)
					rm.Capture(capTeam, boardID, cap.ID, cap.Kind)
				}
				boards[boardID] = nb
				chosen = lm
				applied = true
			} else if len(dropMoves) > 0 {
				d := dropMoves[0]
				rm.Consume(team, d.DropKind)
				nb, _ := legal.Apply(b, d)
				boards[boardID] = nb
				chosen = d
				applied = true
			} else {
				reason = "no_legal"
				break
			}
		}
		if team == "team_a" {
			botLegal++
			if isKingWalkOntoStaleThreat(obs, action) {
				beliefFaults++
			}
		}
		_ = gen.AppendJSONL("plies.jsonl", map[string]any{
			"ply": ply, "board": boardID, "team": team, "side": side.String(), "uci": chosen.UCI(),
		})
		_ = gen.AppendJSONL("relay.jsonl", map[string]any{
			"step": step, "queues": rm.Queues, "events": rm.Events,
		})
		rm.Advance()
		ply++
		_ = step
	}

	// material scoring
	scores["team_a"] += materialTeam(boards, "team_a", spec.TeamAWhiteOn)
	scores["team_b"] += materialTeam(boards, "team_b", spec.TeamAWhiteOn)
	scores["team_a"] += len(rm.Ready("team_a")) * 2
	scores["team_b"] += len(rm.Ready("team_b")) * 2
	scores["team_a"] += rm.Queues["team_a"].PendingScore
	scores["team_b"] += rm.Queues["team_b"].PendingScore

	winner := "draw"
	if scores["team_a"] > scores["team_b"] {
		winner = "team_a"
	} else if scores["team_b"] > scores["team_a"] {
		winner = "team_b"
	}
	floor := spec.AcceptanceFloor
	accepted := botFaults == 0 && beliefFaults == 0 && (floor <= 0 || scores["team_a"] >= floor)
	if accepted && spec.Horizon >= 16 && teamARequests == 0 {
		accepted = false
	}

	_ = gen.WriteJSON("summary.json", replay.Summary{
		MatchID: spec.ID, Opponent: opp.Name, Seed: spec.Seed, Reason: reason, Scores: scores, Plies: ply,
		Determinism: "seeded", AcceptanceFloor: floor, Accepted: accepted,
	})
	_ = gen.WriteJSON("terminal.json", replay.Terminal{Reason: reason, Scores: scores, Winner: winner, Accepted: accepted})
	_ = gen.WriteJSON("bot-diagnostics.json", replay.Diagnostics{
		BotLegalActions: botLegal, BotFaults: botFaults, BeliefFaults: beliefFaults,
		ProtocolOK: botFaults == 0 && beliefFaults == 0, Notes: "fog-chess-relay",
	})
	_ = gen.WriteJSON("boards.json", map[string]string{"alpha": boards["alpha"].ToFEN(), "beta": boards["beta"].ToFEN()})

	term := protocol.TerminalMsg{Type: "terminal", Reason: reason, Scores: scores}
	_ = protocol.Encode(agent.in, term)

	if err := gen.FlushPublish(c.OutputRoot, spec.ID, c.InjectFail); err != nil {
		return err
	}
	return nil
}

type PathOrSpec struct {
	Path string
	Spec *PositionSpec
}

func (p PathOrSpec) Load() (PositionSpec, error) {
	if p.Spec != nil {
		return *p.Spec, nil
	}
	return LoadPosition(p.Path)
}

func teamOfColor(c board.Color, boardID, teamAWhiteOn string) string {
	if boardID == teamAWhiteOn {
		if c == board.White {
			return "team_a"
		}
		return "team_b"
	}
	if c == board.Black {
		return "team_a"
	}
	return "team_b"
}

func materialTeam(boards map[string]*board.Board, team, teamAWhiteOn string) int {
	total := 0
	for id, b := range boards {
		for sq := board.Square(0); sq < 64; sq++ {
			p := b.At(sq)
			if p.IsEmpty() || p.Kind == board.King {
				continue
			}
			t := teamOfColor(p.Color, id, teamAWhiteOn)
			if t == team {
				total += board.MaterialValue(p.Kind)
			}
		}
	}
	return total
}

func isKingWalkOntoStaleThreat(obs protocol.Observation, action protocol.Action) bool {
	if action.Move == "" || len(action.Move) < 4 {
		return false
	}
	from := action.Move[0:2]
	to := action.Move[2:4]
	kingFrom := false
	for _, p := range obs.Pieces {
		if p.Own && p.Kind == "k" && p.Square == from {
			kingFrom = true
			break
		}
	}
	if !kingFrom {
		return false
	}
	for _, s := range obs.Sightings {
		if s.Age <= 2 && s.SqName == to {
			return true
		}
	}
	return false
}

func restricted(rules []string, m legal.Move) bool {
	for _, r := range rules {
		if strings.HasPrefix(r, "no-file:") && strings.Contains(m.To.String(), strings.TrimPrefix(r, "no-file:")) {
			return true
		}
		if r == "no-pawn-drop" && m.IsDrop && m.DropKind == board.Pawn {
			return true
		}
	}
	return false
}

func applyPieceMap(b *board.Board, m map[string]string) {
	if len(m) == 0 {
		return
	}
	for i := board.Square(0); i < 64; i++ {
		p := b.At(i)
		if p.IsEmpty() {
			continue
		}
		if v, ok := m[p.ID]; ok {
			p.ID = v
			b.Set(i, p)
		}
	}
}

func chooseOpponent(opp OpponentDoctrine, spec PositionSpec, b *board.Board, boardID string, moves, drops []legal.Move, ready []string, req string, step int) protocol.Action {
	seed := spec.Seed + opp.SeedBias + int64(step*17)
	pick := func(n int) int {
		if n <= 0 {
			return 0
		}
		v := int(seed % int64(n))
		if v < 0 {
			v = -v
		}
		return v
	}
	if opp.Style == "king_safety" && legal.InCheck(b, b.Side) && len(drops) > 0 {
		d := drops[pick(len(drops))]
		return protocol.Action{Type: "action", Board: boardID, Side: b.Side.String(), Drop: &protocol.Drop{Piece: d.DropKind.String(), Square: d.To.String()}}
	}
	if opp.Style == "promotion_pressure" {
		for _, m := range moves {
			if m.Promote == board.Queen {
				return protocol.Action{Type: "action", Board: boardID, Side: b.Side.String(), Move: m.UCI()}
			}
		}
	}
	if opp.Style == "tactical_relay" && req != "" {
		for _, m := range moves {
			if m.Capture != board.Empty && m.Capture.String() == req {
				return protocol.Action{Type: "action", Board: boardID, Side: b.Side.String(), Move: m.UCI()}
			}
		}
	}
	// Prefer highest-value captures, then checks, then other moves.
	bestCap := -1
	var capMoves []legal.Move
	var checkMoves []legal.Move
	quiet := []legal.Move{}
	for _, m := range moves {
		if m.Capture != board.Empty {
			v := board.MaterialValue(m.Capture)
			if v > bestCap {
				bestCap = v
				capMoves = []legal.Move{m}
			} else if v == bestCap {
				capMoves = append(capMoves, m)
			}
			continue
		}
		nb, _ := legal.Apply(b, m)
		if legal.InCheck(nb, b.Side.Opponent()) {
			checkMoves = append(checkMoves, m)
		} else {
			quiet = append(quiet, m)
		}
	}
	if opp.Style == "passive" {
		if len(quiet) > 0 {
			m := quiet[pick(len(quiet))]
			return protocol.Action{Type: "action", Board: boardID, Side: b.Side.String(), Move: trimPromo(m)}
		}
		if len(moves) > 0 {
			m := moves[pick(len(moves))]
			return protocol.Action{Type: "action", Board: boardID, Side: b.Side.String(), Move: trimPromo(m)}
		}
		return protocol.Action{Type: "action", Board: boardID, Side: b.Side.String(), Hold: true}
	}
	if len(capMoves) > 0 {
		m := capMoves[pick(len(capMoves))]
		return protocol.Action{Type: "action", Board: boardID, Side: b.Side.String(), Move: trimPromo(m)}
	}
	if len(checkMoves) > 0 {
		m := checkMoves[pick(len(checkMoves))]
		return protocol.Action{Type: "action", Board: boardID, Side: b.Side.String(), Move: trimPromo(m)}
	}
	if len(drops) > 0 && (opp.Style == "tactical_relay" || opp.Style == "king_safety" || pick(2) == 0) {
		d := drops[pick(len(drops))]
		return protocol.Action{Type: "action", Board: boardID, Side: b.Side.String(), Drop: &protocol.Drop{Piece: d.DropKind.String(), Square: d.To.String()}}
	}
	if len(quiet) > 0 {
		m := quiet[pick(len(quiet))]
		return protocol.Action{Type: "action", Board: boardID, Side: b.Side.String(), Move: trimPromo(m)}
	}
	if len(moves) > 0 {
		m := moves[pick(len(moves))]
		return protocol.Action{Type: "action", Board: boardID, Side: b.Side.String(), Move: trimPromo(m)}
	}
	if len(drops) > 0 {
		d := drops[pick(len(drops))]
		return protocol.Action{Type: "action", Board: boardID, Side: b.Side.String(), Drop: &protocol.Drop{Piece: d.DropKind.String(), Square: d.To.String()}}
	}
	return protocol.Action{Type: "action", Board: boardID, Side: b.Side.String(), Hold: true}
}

func trimPromo(m legal.Move) string {
	return m.From.String() + m.To.String() + func() string {
		if m.Promote == board.Empty {
			return ""
		}
		return m.Promote.String()
	}()
}

func startBot(bin, dir, strategy string) (*seatBot, error) {
	cmd := exec.Command(bin)
	if dir != "" {
		cmd.Dir = dir
	}
	cmd.Env = append(os.Environ(), "CGO_ENABLED=0")
	if strategy != "" {
		cmd.Env = append(cmd.Env, "FOG_CHESS_STRATEGY="+strategy)
	}
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		return nil, err
	}
	return &seatBot{cmd: cmd, in: stdin, out: bufio.NewReader(stdout)}, nil
}

func (s *seatBot) close() {
	_ = s.in.Close()
	_ = s.cmd.Wait()
}

func copyTree(src, dst string) error {
	return filepath.Walk(src, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(src, path)
		target := filepath.Join(dst, rel)
		if info.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		b, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		return os.WriteFile(target, b, 0o644)
	})
}
