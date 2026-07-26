package cartographer

// Move is one orthogonal step attempt.
type Move int

const (
	MoveUp Move = iota
	MoveRight
	MoveDown
	MoveLeft
)

// Status is the outcome of Analyze.
type Status int

const (
	StatusSolved Status = iota
	StatusUnsolvable
	StatusInvalidInput
	StatusNotImplemented
)

// TraceStep records one move on the canonical shortest route.
type TraceStep struct {
	Index     int
	Move      Move
	From      Coord
	To        Coord
	Keys      []string
	Collapsed []Coord
}

// MandatoryLanding is a coordinate shared by every shortest route at one step.
type MandatoryLanding struct {
	Step int
	At   Coord
}

// DecisionPoint lists shortest-winning alternatives from a canonical state.
type DecisionPoint struct {
	Step         int
	At           Coord
	Alternatives []Move
}

// Analysis is the complete cartographer result for one board.
type Analysis struct {
	Status            Status
	Distance          int
	ShortestCount     string
	CanonicalMoves    []Move
	Trace             []TraceStep
	MandatoryLandings []MandatoryLanding
	DecisionPoints    []DecisionPoint
}

// ValidationStatus is the outcome of Validate.
type ValidationStatus int

const (
	ValidationValid ValidationStatus = iota
	ValidationInvalidInput
	ValidationInvalidAnalysis
)

// Analyze studies every shortest winning route through board.
// The starter build returns StatusNotImplemented for valid boards until the engine is completed.
func Analyze(board Board) Analysis {
	if !validateBoard(board) {
		return invalidAnalysis()
	}
	return notImplementedAnalysis()
}

// Validate checks whether candidate exactly matches the canonical analysis for board.
func Validate(board Board, candidate Analysis) ValidationStatus {
	expected := Analyze(board)
	if expected.Status == StatusInvalidInput {
		if analysisEqual(expected, candidate) {
			return ValidationValid
		}
		return ValidationInvalidInput
	}
	if expected.Status == StatusNotImplemented {
		return ValidationInvalidAnalysis
	}
	if analysisEqual(expected, candidate) {
		return ValidationValid
	}
	return ValidationInvalidAnalysis
}
