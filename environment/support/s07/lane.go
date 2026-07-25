package s07

import "math"

func F0(x float32) float32 { return float32(math.Sin(float64(x + 7.0))) }

func F1(x float32) float32 { return float32(math.Sin(float64(x + 7.1))) }

func F2(x float32) float32 { return float32(math.Sin(float64(x + 7.2))) }

func F3(x float32) float32 { return float32(math.Sin(float64(x + 7.3))) }

func F4(x float32) float32 { return float32(math.Sin(float64(x + 7.4))) }
