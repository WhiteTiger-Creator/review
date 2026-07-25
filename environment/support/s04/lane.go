package s04

import "math"

func F0(x float32) float32 { return float32(math.Sin(float64(x + 4.0))) }

func F1(x float32) float32 { return float32(math.Sin(float64(x + 4.1))) }

func F2(x float32) float32 { return float32(math.Sin(float64(x + 4.2))) }

func F3(x float32) float32 { return float32(math.Sin(float64(x + 4.3))) }

func F4(x float32) float32 { return float32(math.Sin(float64(x + 4.4))) }
