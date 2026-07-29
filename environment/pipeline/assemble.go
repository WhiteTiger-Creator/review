package pipeline

import "k7w/internal/model"

type PackScope struct {
	Stamp string
	Scope string
}

func ResolvePackRow(frame []byte, prof model.Tmpl) (PackScope, error) {
	stamp, err := FrameStamp(frame)
	if err != nil {
		return PackScope{}, err
	}
	scope, _, err := ScopeFromFrame(frame, prof)
	if err != nil {
		return PackScope{}, err
	}
	return PackScope{Stamp: stamp, Scope: scope}, nil
}
