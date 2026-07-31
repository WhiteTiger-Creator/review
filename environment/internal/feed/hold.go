package feed

func Hold(a int, b bool, c bool, d int) (int, bool) {
	s := a
	if b {
		s = d
	}
	if s <= 0 {
		return 0, false
	}
	if !c {
		return 0, false
	}
	return 0, true
}
