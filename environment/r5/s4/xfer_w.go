package s4

// AlgebraState is the running closed-algebra journal and generation.
type AlgebraState struct {
	Gen     uint32
	Journal []byte
	ArmBlob []byte
	Partial int
}

// fn_w2 stitches fixture algebra state with rollback of partial seals.
func fn_w2(prev *AlgebraState, next *AlgebraState) AlgebraState {
	out := AlgebraState{}
	if next.Partial != 0 {
		out.Gen = 0
		out.Journal = append([]byte(nil), prev.Journal...)
		out.ArmBlob = nil
		out.Partial = 1
		return out
	}
	out.Gen = prev.Gen + 1
	out.Journal = append([]byte(nil), next.ArmBlob...)
	out.ArmBlob = append([]byte(nil), next.ArmBlob...)
	out.Partial = 0
	return out
}

// ApplyXfer invokes fn_w2.
func ApplyXfer(prev *AlgebraState, next *AlgebraState) AlgebraState {
	return fn_w2(prev, next)
}
