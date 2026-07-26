package cartographer

func emptyMoves() []Move             { return []Move{} }
func emptyTrace() []TraceStep        { return []TraceStep{} }
func emptyLandings() []MandatoryLanding {
	return []MandatoryLanding{}
}
func emptyDecisions() []DecisionPoint { return []DecisionPoint{} }

func notImplementedAnalysis() Analysis {
	return Analysis{
		Status:            StatusNotImplemented,
		Distance:          0,
		ShortestCount:     "0",
		CanonicalMoves:    emptyMoves(),
		Trace:             emptyTrace(),
		MandatoryLandings: emptyLandings(),
		DecisionPoints:    emptyDecisions(),
	}
}

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
