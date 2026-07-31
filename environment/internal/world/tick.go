package world

import (
	"fmt"

	"skiff/internal/band"
	"skiff/internal/bridge"
	"skiff/internal/feed"
	"skiff/internal/scene"
)

type Result struct {
	Apex      float64
	HopCount  int
	Footprint string
	Settled   bool
}

const stashMax = 4

func Run(c scene.Case) Result {
	s := bridge.Init(c.StartX, c.StartY)
	s.VX = c.VX
	skin := c.Skin
	if skin <= 0 {
		skin = 0.5
	}
	stash := 0
	for i := 0; i < c.Ticks; i++ {
		bridge.Drift(&s)
		seated := false
		for _, sol := range c.Solids {
			if s.X < sol.X0 || s.X > sol.X1 {
				continue
			}
			if sol.OneWay {
				ny, ok := band.Snap(s.Y, sol.Y, skin, s.VY)
				if ok {
					s.Y = ny
					s.VY = 0
					seated = true
				}
			} else if s.Y >= sol.Y {
				s.Y = sol.Y
				if s.VY > 0 {
					s.VY = 0
				}
				seated = true
			}
		}
		if seated {
			s.On = 1
		} else {
			s.On = 0
		}
		bridge.Arm(&s)
		eligible := s.On != 0 || s.Grace > 0
		var hop bool
		stash, hop = feed.Hold(stash, feed.At(c.Press, i), eligible, stashMax)
		s.Stash = stash
		if hop {
			bridge.Kick(&s)
		}
	}
	return Result{
		Apex:      s.Apex,
		HopCount:  s.Hops,
		Footprint: fmt.Sprintf("x%dy%dh%d", int(s.X*10+0.5), int(s.Y*10+0.5), s.Hops),
		Settled:   true,
	}
}
