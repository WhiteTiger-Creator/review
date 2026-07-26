package cartographer

import (
	"math/big"
	"sort"
)

var moveDeltas = [...]Coord{
	MoveUp:    {Row: -1, Col: 0},
	MoveRight: {Row: 0, Col: 1},
	MoveDown:  {Row: 1, Col: 0},
	MoveLeft:  {Row: 0, Col: -1},
}

type gameState struct {
	pos   int
	keys  uint8
	crumb uint16
}

type boardIndex struct {
	rows, cols int
	tiles      []Tile
	start      int
	exit       int
	// portal partner by cell index; -1 if not a portal
	portalPartner []int
	// crumble bit by cell index; -1 if not crumble
	crumbleBit []int
	crumblePos []int // bit -> cell index
}

func analyzeBoard(board Board) Analysis {
	if !validateBoard(board) {
		return invalidAnalysis()
	}
	idx := indexBoard(board)
	start := gameState{pos: idx.start, keys: 0, crumb: 0}

	distFromStart, reachable := bfsForward(idx, start)
	distToExit := bfsToExit(idx, reachable)

	distance := -1
	if d, ok := distToExit[start]; ok {
		distance = d
	}
	if distance < 0 {
		return unsolvableAnalysis()
	}

	// States on some shortest route: distFromStart + distToExit == distance
	onShortest := map[gameState]bool{}
	for s, d0 := range distFromStart {
		if d1, ok := distToExit[s]; ok && d0+d1 == distance {
			onShortest[s] = true
		}
	}

	ways := countShortestWays(idx, start, distance, distFromStart, distToExit, onShortest)
	total := new(big.Int)
	for s, w := range ways {
		if idx.tiles[s.pos].Kind == TileExit && distFromStart[s] == distance {
			total.Add(total, w)
		}
	}

	canonical, trace := buildCanonical(idx, start, distance, distToExit)
	landings := buildMandatoryLandings(idx, distance, distFromStart, distToExit, onShortest)
	decisions := buildDecisionPoints(idx, start, canonical, distance, distToExit)

	return Analysis{
		Status:            StatusSolved,
		Distance:          distance,
		ShortestCount:     total.String(),
		CanonicalMoves:    canonical,
		Trace:             trace,
		MandatoryLandings: landings,
		DecisionPoints:    decisions,
	}
}

func indexBoard(board Board) *boardIndex {
	n := board.Rows * board.Cols
	idx := &boardIndex{
		rows:          board.Rows,
		cols:          board.Cols,
		tiles:         board.Tiles,
		portalPartner: make([]int, n),
		crumbleBit:    make([]int, n),
	}
	for i := range idx.portalPartner {
		idx.portalPartner[i] = -1
		idx.crumbleBit[i] = -1
	}

	portalsByTag := map[string][]int{}
	crumbleBit := 0
	for i, t := range board.Tiles {
		switch t.Kind {
		case TileStart:
			idx.start = i
		case TileExit:
			idx.exit = i
		case TileCrumble:
			idx.crumbleBit[i] = crumbleBit
			idx.crumblePos = append(idx.crumblePos, i)
			crumbleBit++
		case TilePortal:
			portalsByTag[t.Tag] = append(portalsByTag[t.Tag], i)
		}
	}
	for _, pair := range portalsByTag {
		idx.portalPartner[pair[0]] = pair[1]
		idx.portalPartner[pair[1]] = pair[0]
	}
	return idx
}

func (idx *boardIndex) coord(i int) Coord {
	return Coord{Row: i / idx.cols, Col: i % idx.cols}
}

func (idx *boardIndex) at(c Coord) int {
	return c.Row*idx.cols + c.Col
}

func (idx *boardIndex) inBounds(c Coord) bool {
	return c.Row >= 0 && c.Row < idx.rows && c.Col >= 0 && c.Col < idx.cols
}

func (idx *boardIndex) isCollapsed(s gameState, cell int) bool {
	b := idx.crumbleBit[cell]
	if b < 0 {
		return false
	}
	return s.crumb&(1<<uint(b)) != 0
}

func (idx *boardIndex) hasKey(s gameState, tag byte) bool {
	return s.keys&(1<<uint(tag-'a')) != 0
}

// enterable reports whether cell can be occupied given current keys/collapsed.
func (idx *boardIndex) enterable(s gameState, cell int) bool {
	if idx.isCollapsed(s, cell) {
		return false
	}
	t := idx.tiles[cell]
	switch t.Kind {
	case TileWall:
		return false
	case TileDoor:
		return idx.hasKey(s, t.Tag[0])
	default:
		return true
	}
}

// tryMove applies one orthogonal move. ok is false if illegal.
func (idx *boardIndex) tryMove(s gameState, m Move) (gameState, bool) {
	from := idx.coord(s.pos)
	d := moveDeltas[m]
	next := Coord{Row: from.Row + d.Row, Col: from.Col + d.Col}
	if !idx.inBounds(next) {
		return gameState{}, false
	}
	nextIdx := idx.at(next)
	if !idx.enterable(s, nextIdx) {
		return gameState{}, false
	}
	dest := nextIdx
	if idx.portalPartner[nextIdx] >= 0 {
		dest = idx.portalPartner[nextIdx]
		if !idx.enterable(s, dest) {
			return gameState{}, false
		}
	}

	ns := gameState{pos: dest, keys: s.keys, crumb: s.crumb}
	// Collapse previous crumble after a successful departure.
	if b := idx.crumbleBit[s.pos]; b >= 0 {
		ns.crumb |= 1 << uint(b)
	}
	// Collect key at landing cell.
	if t := idx.tiles[dest]; t.Kind == TileKey {
		ns.keys |= 1 << uint(t.Tag[0]-'a')
	}
	return ns, true
}

func (idx *boardIndex) isExit(s gameState) bool {
	return idx.tiles[s.pos].Kind == TileExit
}

func bfsForward(idx *boardIndex, start gameState) (map[gameState]int, map[gameState]bool) {
	dist := map[gameState]int{start: 0}
	reachable := map[gameState]bool{start: true}
	queue := []gameState{start}
	for head := 0; head < len(queue); head++ {
		s := queue[head]
		if idx.isExit(s) {
			continue // terminal
		}
		d := dist[s]
		for _, m := range [...]Move{MoveUp, MoveRight, MoveDown, MoveLeft} {
			ns, ok := idx.tryMove(s, m)
			if !ok {
				continue
			}
			if _, seen := dist[ns]; seen {
				continue
			}
			dist[ns] = d + 1
			reachable[ns] = true
			queue = append(queue, ns)
		}
	}
	return dist, reachable
}

// bfsToExit computes minimum moves from each reachable state to an exit-occupying state.
func bfsToExit(idx *boardIndex, reachable map[gameState]bool) map[gameState]int {
	// Build reverse edges among reachable states for multi-source BFS from exits.
	pred := make(map[gameState][]gameState, len(reachable))
	exits := []gameState{}
	for s := range reachable {
		if idx.isExit(s) {
			exits = append(exits, s)
			continue
		}
		for _, m := range [...]Move{MoveUp, MoveRight, MoveDown, MoveLeft} {
			ns, ok := idx.tryMove(s, m)
			if !ok || !reachable[ns] {
				continue
			}
			pred[ns] = append(pred[ns], s)
		}
	}

	dist := map[gameState]int{}
	queue := make([]gameState, 0, len(exits))
	for _, e := range exits {
		dist[e] = 0
		queue = append(queue, e)
	}
	for head := 0; head < len(queue); head++ {
		s := queue[head]
		d := dist[s]
		for _, p := range pred[s] {
			if _, seen := dist[p]; seen {
				continue
			}
			dist[p] = d + 1
			queue = append(queue, p)
		}
	}
	return dist
}

func countShortestWays(
	idx *boardIndex,
	start gameState,
	distance int,
	distFromStart, distToExit map[gameState]int,
	onShortest map[gameState]bool,
) map[gameState]*big.Int {
	ways := map[gameState]*big.Int{start: big.NewInt(1)}
	// Process by increasing distFromStart.
	byDist := make([][]gameState, distance+1)
	for s := range onShortest {
		d := distFromStart[s]
		if d >= 0 && d <= distance {
			byDist[d] = append(byDist[d], s)
		}
	}
	for d := 0; d < distance; d++ {
		for _, s := range byDist[d] {
			w := ways[s]
			if w == nil {
				continue
			}
			if idx.isExit(s) {
				continue
			}
			for _, m := range [...]Move{MoveUp, MoveRight, MoveDown, MoveLeft} {
				ns, ok := idx.tryMove(s, m)
				if !ok || !onShortest[ns] {
					continue
				}
				if distFromStart[ns] != d+1 {
					continue
				}
				if distToExit[ns]+d+1 != distance {
					continue
				}
				if ways[ns] == nil {
					ways[ns] = new(big.Int)
				}
				ways[ns].Add(ways[ns], w)
			}
		}
	}
	return ways
}

func buildCanonical(
	idx *boardIndex,
	start gameState,
	distance int,
	distToExit map[gameState]int,
) ([]Move, []TraceStep) {
	moves := make([]Move, 0, distance)
	trace := make([]TraceStep, 0, distance)
	s := start
	for step := 1; step <= distance; step++ {
		remaining := distance - step + 1
		var chosen Move
		var ns gameState
		found := false
		for _, m := range [...]Move{MoveUp, MoveRight, MoveDown, MoveLeft} {
			cand, ok := idx.tryMove(s, m)
			if !ok {
				continue
			}
			dExit, ok := distToExit[cand]
			if !ok || dExit != remaining-1 {
				continue
			}
			chosen = m
			ns = cand
			found = true
			break
		}
		if !found {
			// Should not happen on a solvable board.
			break
		}
		moves = append(moves, chosen)
		trace = append(trace, TraceStep{
			Index:     step,
			Move:      chosen,
			From:      idx.coord(s.pos),
			To:        idx.coord(ns.pos),
			Keys:      keysList(ns.keys),
			Collapsed: collapsedList(idx, ns.crumb),
		})
		s = ns
		if idx.isExit(s) {
			break
		}
	}
	if moves == nil {
		moves = []Move{}
	}
	if trace == nil {
		trace = []TraceStep{}
	}
	return moves, trace
}

func buildMandatoryLandings(
	idx *boardIndex,
	distance int,
	distFromStart, distToExit map[gameState]int,
	onShortest map[gameState]bool,
) []MandatoryLanding {
	landings := []MandatoryLanding{}
	for step := 1; step <= distance; step++ {
		var shared *Coord
		unanimous := true
		for s := range onShortest {
			if distFromStart[s] != step {
				continue
			}
			if distToExit[s]+step != distance {
				continue
			}
			c := idx.coord(s.pos)
			if shared == nil {
				cc := c
				shared = &cc
			} else if *shared != c {
				unanimous = false
				break
			}
		}
		if unanimous && shared != nil {
			landings = append(landings, MandatoryLanding{Step: step, At: *shared})
		}
	}
	return landings
}

func buildDecisionPoints(
	idx *boardIndex,
	start gameState,
	canonical []Move,
	distance int,
	distToExit map[gameState]int,
) []DecisionPoint {
	out := []DecisionPoint{}
	s := start
	for i, cm := range canonical {
		_ = cm
		step := i + 1
		remaining := distance - i
		alts := []Move{}
		for _, m := range [...]Move{MoveUp, MoveRight, MoveDown, MoveLeft} {
			ns, ok := idx.tryMove(s, m)
			if !ok {
				continue
			}
			dExit, ok := distToExit[ns]
			if !ok || dExit != remaining-1 {
				continue
			}
			alts = append(alts, m)
		}
		if len(alts) >= 2 {
			out = append(out, DecisionPoint{
				Step:         step,
				At:           idx.coord(s.pos),
				Alternatives: alts,
			})
		}
		// Advance along canonical.
		ns, ok := idx.tryMove(s, canonical[i])
		if !ok {
			break
		}
		s = ns
	}
	return out
}

func keysList(mask uint8) []string {
	out := []string{}
	for i := 0; i < 4; i++ {
		if mask&(1<<uint(i)) != 0 {
			out = append(out, string(rune('a'+i)))
		}
	}
	return out
}

func collapsedList(idx *boardIndex, mask uint16) []Coord {
	out := []Coord{}
	for b, cell := range idx.crumblePos {
		if mask&(1<<uint(b)) != 0 {
			out = append(out, idx.coord(cell))
		}
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Row != out[j].Row {
			return out[i].Row < out[j].Row
		}
		return out[i].Col < out[j].Col
	})
	return out
}

func emptyMoves() []Move { return []Move{} }
func emptyTrace() []TraceStep {
	return []TraceStep{}
}
func emptyLandings() []MandatoryLanding {
	return []MandatoryLanding{}
}
func emptyDecisions() []DecisionPoint { return []DecisionPoint{} }

func invalidAnalysis() Analysis {
	return Analysis{
		Status:            StatusInvalidInput,
		Distance:          0,
		ShortestCount:     "0",
		CanonicalMoves:    emptyMoves(),
		Trace:             emptyTrace(),
		MandatoryLandings: emptyLandings(),
		DecisionPoints:    emptyDecisions(),
	}
}

func unsolvableAnalysis() Analysis {
	return Analysis{
		Status:            StatusUnsolvable,
		Distance:          -1,
		ShortestCount:     "0",
		CanonicalMoves:    emptyMoves(),
		Trace:             emptyTrace(),
		MandatoryLandings: emptyLandings(),
		DecisionPoints:    emptyDecisions(),
	}
}

func analysisEqual(a, b Analysis) bool {
	if a.Status != b.Status || a.Distance != b.Distance || a.ShortestCount != b.ShortestCount {
		return false
	}
	if a.CanonicalMoves == nil || b.CanonicalMoves == nil ||
		a.Trace == nil || b.Trace == nil ||
		a.MandatoryLandings == nil || b.MandatoryLandings == nil ||
		a.DecisionPoints == nil || b.DecisionPoints == nil {
		return false
	}
	if len(a.CanonicalMoves) != len(b.CanonicalMoves) {
		return false
	}
	for i := range a.CanonicalMoves {
		if a.CanonicalMoves[i] != b.CanonicalMoves[i] {
			return false
		}
	}
	if len(a.Trace) != len(b.Trace) {
		return false
	}
	for i := range a.Trace {
		if !traceEqual(a.Trace[i], b.Trace[i]) {
			return false
		}
	}
	if len(a.MandatoryLandings) != len(b.MandatoryLandings) {
		return false
	}
	for i := range a.MandatoryLandings {
		if a.MandatoryLandings[i] != b.MandatoryLandings[i] {
			return false
		}
	}
	if len(a.DecisionPoints) != len(b.DecisionPoints) {
		return false
	}
	for i := range a.DecisionPoints {
		if !decisionEqual(a.DecisionPoints[i], b.DecisionPoints[i]) {
			return false
		}
	}
	return true
}

func traceEqual(a, b TraceStep) bool {
	if a.Index != b.Index || a.Move != b.Move || a.From != b.From || a.To != b.To {
		return false
	}
	if a.Keys == nil || b.Keys == nil || a.Collapsed == nil || b.Collapsed == nil {
		return false
	}
	if len(a.Keys) != len(b.Keys) {
		return false
	}
	for i := range a.Keys {
		if a.Keys[i] != b.Keys[i] {
			return false
		}
	}
	if len(a.Collapsed) != len(b.Collapsed) {
		return false
	}
	for i := range a.Collapsed {
		if a.Collapsed[i] != b.Collapsed[i] {
			return false
		}
	}
	return true
}

func decisionEqual(a, b DecisionPoint) bool {
	if a.Step != b.Step || a.At != b.At {
		return false
	}
	if a.Alternatives == nil || b.Alternatives == nil {
		return false
	}
	if len(a.Alternatives) != len(b.Alternatives) {
		return false
	}
	for i := range a.Alternatives {
		if a.Alternatives[i] != b.Alternatives[i] {
			return false
		}
	}
	return true
}
