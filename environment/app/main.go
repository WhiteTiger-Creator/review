package main

import (
	"fmt"
	"math"
	"os"

	"godeep-rl/ml"
	"godeep-rl/tensor"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: godeep-rl <command> [args]")
		fmt.Println("Commands: train, eval, quantize-kv")
		os.Exit(1)
	}

	cmd := os.Args[1]
	switch cmd {
	case "train":
		runTrain()
	case "eval":
		runEval()
	case "quantize-kv":
		runQuantizeKV()
	default:
		fmt.Printf("Unknown command: %s\n", cmd)
		os.Exit(1)
	}
}

func runTrain() {
	fmt.Println("Running godeep-rl PPO training...")
	rewards := []float64{1.0, 0.5, -0.2, 1.2, 0.8, 1.5, -0.5, 2.0}
	values := []float64{0.8, 0.6, 0.1, 1.0, 0.7, 1.2, -0.2, 1.8}
	oldLogProbs := []float64{-0.5, -0.4, -0.8, -0.3, -0.5, -0.2, -0.9, -0.1}
	newLogProbs := []float64{-0.45, -0.38, -0.75, -0.28, -0.48, -0.18, -0.85, -0.08}

	cfg := ml.DefaultPPOConfig()
	advs, rets := ml.ComputeGAE(rewards, values, cfg)
	loss := ml.ComputePPOLoss(oldLogProbs, newLogProbs, advs, cfg)

	fmt.Printf("GAE Returns: %.3f\n", rets[0])
	fmt.Printf("PPO Loss: %.4f\n", loss)
}

func runEval() {
	fmt.Println("Running godeep-rl policy evaluation...")
	q := tensor.Ones([]int{4, 8})
	k := tensor.Ones([]int{4, 8})
	v := tensor.Ones([]int{4, 8})

	qRope, _ := ml.ApplyRoPE(q, 4, 8)
	kRope, _ := ml.ApplyRoPE(k, 4, 8)
	out, err := ml.CausalScaledDotProductAttention(qRope, kRope, v, 4, 8)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("Eval Attention Output Mean: %.4f\n", out.Data[0])
}

func runQuantizeKV() {
	fmt.Println("Running godeep-rl KV-Cache INT8 quantization benchmark...")
	data := []float64{-2.5, -1.2, 0.0, 0.5, 1.8, 3.4, 5.1, 7.8}
	cache := ml.QuantizeAsymmetricINT8(data, 2, 4)
	deq := cache.Dequantize()

	mae := 0.0
	for i := range data {
		mae += math.Abs(data[i] - deq[i])
	}
	mae /= float64(len(data))
	fmt.Printf("INT8 Quantization MAE: %.5f\n", mae)
}
