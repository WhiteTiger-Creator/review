package bridge

/*
#cgo LDFLAGS: -L${SRCDIR}/../../orb-rs/target/release -lorb_core -lm -ldl -lpthread
#include "../../include/orb_core.h"
*/
import "C"

type Sample struct {
	X, Y, VX, VY       float64
	On, Grace, Stash, Hops int
	Apex               float64
}

func Init(x, y float64) Sample {
	s := C.skiff_sample_init(C.double(x), C.double(y))
	return unpack(s)
}

func Drift(s *Sample) {
	cs := pack(s)
	C.skiff_drift(&cs)
	*s = unpack(cs)
}

func Arm(s *Sample) {
	cs := pack(s)
	C.skiff_arm(&cs)
	*s = unpack(cs)
}

func Kick(s *Sample) {
	cs := pack(s)
	C.skiff_kick(&cs)
	*s = unpack(cs)
}

func pack(s *Sample) C.SkiffSample {
	return C.SkiffSample{
		x: C.double(s.X), y: C.double(s.Y),
		vx: C.double(s.VX), vy: C.double(s.VY),
		on: C.int(s.On), grace: C.int(s.Grace), stash: C.int(s.Stash),
		hops: C.int(s.Hops), apex: C.double(s.Apex),
	}
}

func unpack(s C.SkiffSample) Sample {
	return Sample{
		X: float64(s.x), Y: float64(s.y),
		VX: float64(s.vx), VY: float64(s.vy),
		On: int(s.on), Grace: int(s.grace), Stash: int(s.stash),
		Hops: int(s.hops), Apex: float64(s.apex),
	}
}
