#!/bin/bash
set -euo pipefail

export PATH="/usr/local/cargo/bin:/usr/local/go/bin:${PATH}"
export CGO_ENABLED=1

cat > /app/orb-rs/src/wisp.rs <<'EOF'
fn clamp_nonneg(v: i32) -> i32 {
    if v < 0 {
        0
    } else {
        v
    }
}

fn decay_one(v: i32) -> i32 {
    clamp_nonneg(v - 1)
}

fn refresh(ceiling: i32) -> i32 {
    if ceiling < 0 {
        0
    } else if ceiling > 64 {
        64
    } else {
        ceiling
    }
}

pub fn arm_g(a: bool, b: i32, c: i32) -> i32 {
    let ceiling = refresh(c);
    if a {
        return ceiling;
    }
    if b <= 0 {
        return 0;
    }
    let next = decay_one(b);
    if next > ceiling {
        ceiling
    } else {
        next
    }
}
EOF

cat > /app/internal/feed/hold.go <<'EOF'
package feed

func saturate(v, lo, hi int) int {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

func armed(pressed bool, latch, ceiling int) int {
	if pressed {
		return saturate(ceiling, 0, 64)
	}
	return saturate(latch, 0, 64)
}

// Hold maps latch state + press + eligibility into (newLatch, hop).
func Hold(a int, b bool, c bool, d int) (int, bool) {
	s := armed(b, a, d)
	if s <= 0 {
		return 0, false
	}
	if c {
		return 0, true
	}
	next := s - 1
	if next <= 0 {
		return 0, false
	}
	return next, false
}
EOF

cat > /app/internal/band/snap.go <<'EOF'
package band

func inside(a, b, c float64) bool {
	return a >= b && a <= b+c
}

func fallingOrRest(d float64) bool {
	return d >= 0
}

func Snap(a float64, b float64, c float64, d float64) (float64, bool) {
	if c < 0 {
		return a, false
	}
	if !fallingOrRest(d) {
		return a, false
	}
	if !inside(a, b, c) {
		return a, false
	}
	return b, true
}

func BandHits(samples []float64, top, skin float64, speeds []float64) int {
	n := 0
	for i := 0; i < len(samples) && i < len(speeds); i++ {
		if _, ok := Snap(samples[i], top, skin, speeds[i]); ok {
			n++
		}
	}
	return n
}
EOF

/app/scripts/build.sh
/app/scripts/run.sh
