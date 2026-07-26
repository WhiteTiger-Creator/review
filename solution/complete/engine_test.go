package cartographer

import (
	"testing"
)

func TestCorridorShortest(t *testing.T) {
	// S . E
	// # # #
	board := Board{
		Rows: 2,
		Cols: 3,
		Tiles: []Tile{
			{Kind: TileStart}, {Kind: TileFloor}, {Kind: TileExit},
			{Kind: TileWall}, {Kind: TileWall}, {Kind: TileWall},
		},
	}
	a := Analyze(board)
	if a.Status != StatusSolved {
		t.Fatalf("status=%v want Solved", a.Status)
	}
	if a.Distance != 2 {
		t.Fatalf("distance=%d want 2", a.Distance)
	}
	if a.ShortestCount != "1" {
		t.Fatalf("count=%q want 1", a.ShortestCount)
	}
	if len(a.CanonicalMoves) != 2 || a.CanonicalMoves[0] != MoveRight || a.CanonicalMoves[1] != MoveRight {
		t.Fatalf("moves=%v want [Right Right]", a.CanonicalMoves)
	}
	if len(a.Trace) != 2 {
		t.Fatalf("trace len=%d", len(a.Trace))
	}
	if a.Trace[0].From != (Coord{0, 0}) || a.Trace[0].To != (Coord{0, 1}) {
		t.Fatalf("trace0=%+v", a.Trace[0])
	}
	if a.Trace[1].From != (Coord{0, 1}) || a.Trace[1].To != (Coord{0, 2}) {
		t.Fatalf("trace1=%+v", a.Trace[1])
	}
	if a.CanonicalMoves == nil || a.Trace == nil || a.MandatoryLandings == nil || a.DecisionPoints == nil {
		t.Fatal("nil slices")
	}
	// Both steps are mandatory on the single route.
	if len(a.MandatoryLandings) != 2 {
		t.Fatalf("landings=%v", a.MandatoryLandings)
	}
	if Validate(board, a) != ValidationValid {
		t.Fatal("self-validate failed")
	}
}

func TestUnsolvableWallBox(t *testing.T) {
	// S #
	// # E
	board := Board{
		Rows: 2,
		Cols: 2,
		Tiles: []Tile{
			{Kind: TileStart}, {Kind: TileWall},
			{Kind: TileWall}, {Kind: TileExit},
		},
	}
	a := Analyze(board)
	if a.Status != StatusUnsolvable {
		t.Fatalf("status=%v want Unsolvable", a.Status)
	}
	if a.Distance != -1 || a.ShortestCount != "0" {
		t.Fatalf("got dist=%d count=%q", a.Distance, a.ShortestCount)
	}
	if a.CanonicalMoves == nil || a.Trace == nil || a.MandatoryLandings == nil || a.DecisionPoints == nil {
		t.Fatal("nil slices")
	}
	if len(a.CanonicalMoves) != 0 || len(a.Trace) != 0 {
		t.Fatal("expected empty slices")
	}
}

func TestInvalid1x1(t *testing.T) {
	board := Board{
		Rows:  1,
		Cols:  1,
		Tiles: []Tile{{Kind: TileStart}},
	}
	a := Analyze(board)
	if a.Status != StatusInvalidInput {
		t.Fatalf("status=%v want InvalidInput", a.Status)
	}
	if a.Distance != 0 || a.ShortestCount != "0" {
		t.Fatalf("got dist=%d count=%q", a.Distance, a.ShortestCount)
	}
	if Validate(board, a) != ValidationValid {
		t.Fatal("invalid self-validate failed")
	}
	bad := a
	bad.Distance = 1
	if Validate(board, bad) != ValidationInvalidInput {
		t.Fatal("expected ValidationInvalidInput")
	}
}

func TestKeyDoor(t *testing.T) {
	// S a D(a) E
	// # # #  #
	// wait cols=4 rows=2
	board := Board{
		Rows: 2,
		Cols: 4,
		Tiles: []Tile{
			{Kind: TileStart}, {Kind: TileKey, Tag: "a"}, {Kind: TileDoor, Tag: "a"}, {Kind: TileExit},
			{Kind: TileWall}, {Kind: TileWall}, {Kind: TileWall}, {Kind: TileWall},
		},
	}
	a := Analyze(board)
	if a.Status != StatusSolved || a.Distance != 3 {
		t.Fatalf("status=%v dist=%d", a.Status, a.Distance)
	}
	if a.ShortestCount != "1" {
		t.Fatalf("count=%q", a.ShortestCount)
	}
	if len(a.Trace) != 3 {
		t.Fatalf("trace=%v", a.Trace)
	}
	if len(a.Trace[0].Keys) != 1 || a.Trace[0].Keys[0] != "a" {
		t.Fatalf("keys after first move: %v", a.Trace[0].Keys)
	}
}

func TestPortalTeleport(t *testing.T) {
	// S P(a) # E
	// # # # P(a)
	board := Board{
		Rows: 2,
		Cols: 4,
		Tiles: []Tile{
			{Kind: TileStart}, {Kind: TilePortal, Tag: "a"}, {Kind: TileWall}, {Kind: TileExit},
			{Kind: TileWall}, {Kind: TileWall}, {Kind: TileWall}, {Kind: TilePortal, Tag: "a"},
		},
	}
	a := Analyze(board)
	if a.Status != StatusSolved {
		t.Fatalf("status=%v", a.Status)
	}
	// Right onto portal -> land on partner (1,3), then need Left,Left,Left? 
	// Partner is at (1,3). From there to Exit at (0,3): move Up.
	// So: Right (teleport to 1,3), Up -> Exit. Distance 2.
	if a.Distance != 2 {
		t.Fatalf("distance=%d want 2; moves=%v trace=%+v", a.Distance, a.CanonicalMoves, a.Trace)
	}
	if a.Trace[0].To != (Coord{1, 3}) {
		t.Fatalf("portal land To=%v want {1,3}", a.Trace[0].To)
	}
}

func TestCrumbleCollapsesOnLeave(t *testing.T) {
	// S C E
	// . . .
	board := Board{
		Rows: 2,
		Cols: 3,
		Tiles: []Tile{
			{Kind: TileStart}, {Kind: TileCrumble}, {Kind: TileExit},
			{Kind: TileFloor}, {Kind: TileFloor}, {Kind: TileFloor},
		},
	}
	a := Analyze(board)
	if a.Status != StatusSolved || a.Distance != 2 {
		t.Fatalf("status=%v dist=%d", a.Status, a.Distance)
	}
	// After leaving crumble toward exit, collapsed should include crumble cell.
	if len(a.Trace) < 2 {
		t.Fatal("short trace")
	}
	// Step1: S->C, no collapse yet (didn't leave crumble).
	if len(a.Trace[0].Collapsed) != 0 {
		t.Fatalf("step1 collapsed=%v", a.Trace[0].Collapsed)
	}
	// Step2: leave C to E, C collapses.
	if len(a.Trace[1].Collapsed) != 1 || a.Trace[1].Collapsed[0] != (Coord{0, 1}) {
		t.Fatalf("step2 collapsed=%v", a.Trace[1].Collapsed)
	}
}

func TestDoorBlocksWithoutKey(t *testing.T) {
	// S D(a) E
	// # # #
	board := Board{
		Rows: 2,
		Cols: 3,
		Tiles: []Tile{
			{Kind: TileStart}, {Kind: TileDoor, Tag: "a"}, {Kind: TileExit},
			{Kind: TileWall}, {Kind: TileWall}, {Kind: TileWall},
		},
	}
	a := Analyze(board)
	if a.Status != StatusUnsolvable {
		t.Fatalf("status=%v want Unsolvable", a.Status)
	}
}

func TestIllegalMoveDoesNotCollapse(t *testing.T) {
	// S C #
	// . . E  -- from crumble, attempting Right into wall must not collapse C.
	board := Board{
		Rows: 2,
		Cols: 3,
		Tiles: []Tile{
			{Kind: TileStart}, {Kind: TileCrumble}, {Kind: TileWall},
			{Kind: TileFloor}, {Kind: TileFloor}, {Kind: TileExit},
		},
	}
	a := Analyze(board)
	if a.Status != StatusSolved {
		t.Fatalf("status=%v", a.Status)
	}
	// Collapse of C appears only after a successful departure from C.
	found := false
	for _, step := range a.Trace {
		if step.From == (Coord{0, 1}) {
			for _, c := range step.Collapsed {
				if c == (Coord{0, 1}) {
					found = true
				}
			}
		}
	}
	if !found {
		t.Fatalf("expected collapse after leaving crumble; trace=%+v", a.Trace)
	}
}

func TestDecisionPointOpenGrid(t *testing.T) {
	// S .
	// . E
	board := Board{
		Rows: 2,
		Cols: 2,
		Tiles: []Tile{
			{Kind: TileStart}, {Kind: TileFloor},
			{Kind: TileFloor}, {Kind: TileExit},
		},
	}
	a := Analyze(board)
	if a.Status != StatusSolved || a.Distance != 2 {
		t.Fatalf("status=%v dist=%d", a.Status, a.Distance)
	}
	if a.ShortestCount != "2" {
		t.Fatalf("count=%q want 2", a.ShortestCount)
	}
	// Canonical: Right then Down (Right < Down when choosing first move? 
	// From start: Right -> (0,1) then Down -> E; or Down -> (1,0) then Right -> E.
	// Lex-smallest: compare sequences [Right,Down] vs [Down,Right].
	// Right(1) < Down(2), so [Right,Down] wins.
	if a.CanonicalMoves[0] != MoveRight || a.CanonicalMoves[1] != MoveDown {
		t.Fatalf("canonical=%v", a.CanonicalMoves)
	}
	if len(a.DecisionPoints) < 1 {
		t.Fatalf("expected decision point, got %v", a.DecisionPoints)
	}
	dp := a.DecisionPoints[0]
	if dp.Step != 1 || len(dp.Alternatives) != 2 {
		t.Fatalf("dp=%+v", dp)
	}
}
