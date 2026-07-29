package ml_test

import (
	"math"
	"testing"

	"godeep-rl/ml"
	"godeep-rl/tensor"
)

func TestRoPEAndCausalAttention(t *testing.T) {
	q := tensor.Ones([]int{4, 8})
	k := tensor.Ones([]int{4, 8})
	v := tensor.Ones([]int{4, 8})

	qRope, err := ml.ApplyRoPE(q, 4, 8)
	if err != nil {
		t.Fatalf("ApplyRoPE failed: %v", err)
	}
	kRope, err := ml.ApplyRoPE(k, 4, 8)
	if err != nil {
		t.Fatalf("ApplyRoPE failed: %v", err)
	}

	out, err := ml.CausalScaledDotProductAttention(qRope, kRope, v, 4, 8)
	if err != nil {
		t.Fatalf("Attention failed: %v", err)
	}

	if len(out.Data) != 32 {
		t.Fatalf("Output shape mismatch")
	}

	// First position should only attend to position 0 (causal mask)
	// Output vector at pos 0 should be v[0] == 1.0 for all dims
	for d := 0; d < 8; d++ {
		if math.Abs(out.Data[d]-1.0) > 1e-4 {
			t.Errorf("Pos 0 dim %d expected 1.0, got %.4f", d, out.Data[d])
		}
	}
}

func TestQuantizationMAE(t *testing.T) {
	data := []float64{-2.5, -1.2, 0.0, 0.5, 1.8, 3.4, 5.1, 7.8}
	cache := ml.QuantizeAsymmetricINT8(data, 2, 4)
	deq := cache.Dequantize()

	mae := 0.0
	for i := range data {
		mae += math.Abs(data[i] - deq[i])
	}
	mae /= float64(len(data))

	if mae > 0.05 {
		t.Errorf("Quantization MAE too high: %.5f", mae)
	}
}

func TestGAEAndPPO(t *testing.T) {
	rewards := []float64{1.0, 0.5, -0.2, 1.2}
	values := []float64{0.8, 0.6, 0.1, 1.0}
	oldLogProbs := []float64{-0.5, -0.4, -0.8, -0.3}
	newLogProbs := []float64{-0.45, -0.38, -0.75, -0.28}

	cfg := ml.DefaultPPOConfig()
	advs, rets := ml.ComputeGAE(rewards, values, cfg)

	if len(advs) != 4 || len(rets) != 4 {
		t.Fatalf("GAE length mismatch")
	}

	// Backward accumulation check: t=3 return should equal reward[3] == 1.2 (since no t+1)
	if math.Abs(rets[3]-1.2) > 1e-4 {
		t.Errorf("Return t=3 expected 1.2, got %.4f", rets[3])
	}

	loss := ml.ComputePPOLoss(oldLogProbs, newLogProbs, advs, cfg)
	if math.IsNaN(loss) || math.IsInf(loss, 0) {
		t.Errorf("Invalid PPO loss: %.4f", loss)
	}
}

func TestGradientClipping(t *testing.T) {
	grads := []float64{3.0, 4.0} // L2 norm is 5.0
	maxNorm := 2.5

	norm := ml.ClipGradientNorm(grads, maxNorm)
	if math.Abs(norm-5.0) > 1e-4 {
		t.Errorf("Expected initial norm 5.0, got %.4f", norm)
	}

	// New norm should equal 2.5
	newNormSq := grads[0]*grads[0] + grads[1]*grads[1]
	newNorm := math.Sqrt(newNormSq)
	if math.Abs(newNorm-maxNorm) > 1e-4 {
		t.Errorf("Clipped norm expected 2.5, got %.4f", newNorm)
	}
}
