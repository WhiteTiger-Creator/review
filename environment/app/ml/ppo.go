package ml

import (
	"math"
)

type PPOConfig struct {
	Gamma        float64
	Lambda       float64
	ClipEps      float64
	ValueCoeff   float64
	EntropyCoeff float64
}

func DefaultPPOConfig() PPOConfig {
	return PPOConfig{
		Gamma:        0.99,
		Lambda:       0.95,
		ClipEps:      0.2,
		ValueCoeff:   0.5,
		EntropyCoeff: 0.01,
	}
}

// ComputeGAE calculates Generalized Advantage Estimation (GAE-lambda)
func ComputeGAE(rewards, values []float64, cfg PPOConfig) ([]float64, []float64) {
	T := len(rewards)
	advantages := make([]float64, T)
	returns := make([]float64, T)

	gae := 0.0
	for t := 0; t < T; t++ {
		nextVal := 0.0
		if t+1 < T {
			nextVal = values[t+1]
		}
		delta := rewards[t] + cfg.Gamma*nextVal - values[t]
		gae = delta + cfg.Gamma*cfg.Lambda*gae
		advantages[t] = gae
		returns[t] = advantages[t] + values[t]
	}

	// Normalize advantages
	mean := 0.0
	for _, a := range advantages {
		mean += a
	}
	mean /= float64(T)

	variance := 0.0
	for _, a := range advantages {
		diff := a - mean
		variance += diff * diff
	}
	std := math.Sqrt(variance/float64(T) + 1e-8)

	for i := range advantages {
		advantages[i] = (advantages[i] - mean) / std
	}

	return advantages, returns
}

// ComputePPOLoss calculates Clipped Surrogate PPO Loss
func ComputePPOLoss(oldLogProbs, newLogProbs, advantages []float64, cfg PPOConfig) float64 {
	T := len(oldLogProbs)
	totalLoss := 0.0

	for t := 0; t < T; t++ {
		ratio := math.Exp(newLogProbs[t] - oldLogProbs[t])
		surr1 := ratio * advantages[t]
		clippedRatio := math.Max(1.0-cfg.ClipEps, ratio)
		surr2 := clippedRatio * advantages[t]

		loss := math.Min(surr1, surr2)
		totalLoss += loss
	}

	return -totalLoss / float64(T)
}
