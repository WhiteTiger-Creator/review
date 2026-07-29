package emit

import (
	"fmt"
	"k7w/internal/model"
)

func Line(lineID, scope, tid, rationale string, anchor int64) model.ReportLine {
	return model.ReportLine{
		LineID:        lineID,
		ScopeCode:     scope,
		TimingAnchor:  anchor,
		TransitionID:  tid,
		RationaleText: rationale,
	}
}

func RationaleFor(scope string) string {
	return fmt.Sprintf("scope=%s via pipeline", scope)
}
