
package scoring

import "math"

func SoftGate(x float32) float32 {
    return float32(2.0 / (1.0 + math.Exp(float64(-x))))
}
