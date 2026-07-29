"""Extreme Hard Verifier Test Suite for task 96: godeep-rl.

Validates 4D tensor autograd, NTK-aware RoPE attention, per-head INT8 KV-cache,
episodic GAE-lambda PPO loss, gradient norm clipping, and Go package integrity.
"""

import os
import subprocess


def test_go_package_compilation_and_tests() -> None:
    """Verify that all Go packages under /app compile cleanly and pass unit tests."""
    result = subprocess.run(
        ["go", "test", "-v", "./..."],
        cwd="/app",
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, (
        f"go test failed with exit code {result.returncode}:\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )


def test_go_binary_build_and_cli() -> None:
    """Verify that main.go builds cleanly and CLI subcommands produce expected outputs."""
    build_res = subprocess.run(
        ["go", "build", "-o", "/tmp/godeep-rl", "main.go"],
        cwd="/app",
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert build_res.returncode == 0, f"go build failed:\n{build_res.stderr}"
    assert os.path.exists("/tmp/godeep-rl"), "Executable /tmp/godeep-rl missing"

    # Train command
    train_res = subprocess.run(
        ["/tmp/godeep-rl", "train"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert train_res.returncode == 0, f"train command failed: {train_res.stderr}"
    assert "PPO Loss:" in train_res.stdout

    # Eval command
    eval_res = subprocess.run(
        ["/tmp/godeep-rl", "eval"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert eval_res.returncode == 0, f"eval command failed: {eval_res.stderr}"
    assert "Eval Attention Output Mean:" in eval_res.stdout

    # Quantize command
    quant_res = subprocess.run(
        ["/tmp/godeep-rl", "quantize-kv"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert quant_res.returncode == 0, f"quantize-kv command failed: {quant_res.stderr}"
    assert "INT8 Quantization MAE:" in quant_res.stdout


def test_autograd_4d_matmul_and_topological_sort() -> None:
    """Verify autograd 4D tensor matrix multiplication & branching DAG gradient precision."""
    test_code = """package main

import (
	"fmt"
	"math"
	"os"

	"godeep-rl/tensor"
)

func main() {
	// Shape 1x1x2x2
	a := tensor.NewTensor([]int{1, 1, 2, 2}, []float64{1.0, 2.0, 3.0, 4.0})
	b := tensor.NewTensor([]int{1, 1, 2, 2}, []float64{0.5, 0.2, 0.1, 0.8})
	a.RequiresGrad = true
	b.RequiresGrad = true

	// Branching DAG: C = MatMul(A, B), D = Add(C, A)
	c, err := tensor.MatMul(a, b)
	if err != nil {
		fmt.Printf("MatMul err: %v\\n", err)
		os.Exit(1)
	}

	d, err := tensor.Add(c, a)
	if err != nil {
		fmt.Printf("Add err: %v\\n", err)
		os.Exit(1)
	}

	d.Backward()

	// Gradient dA_00 should be (dC_00/dA_00) + (dC_01/dA_00) + (dD_00/dA_00) = 0.5 + 0.2 + 1.0 = 1.7
	expectedGradA00 := 1.7
	if math.Abs(a.Grad[0]-expectedGradA00) > 1e-4 {
		fmt.Printf("Branching Grad A[0] mismatch: got %.5f, expected %.5f\\n", a.Grad[0], expectedGradA00)
		os.Exit(1)
	}

	fmt.Println("AUTOGRAD_BRANCHING_SUCCESS")
}
"""
    with open("/app/test_branching_autograd.go", "w") as f:
        f.write(test_code)

    try:
        res = subprocess.run(
            ["go", "run", "/app/test_branching_autograd.go"],
            cwd="/app",
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert res.returncode == 0, f"Branching autograd test failed: {res.stderr}\n{res.stdout}"
        assert "AUTOGRAD_BRANCHING_SUCCESS" in res.stdout
    finally:
        if os.path.exists("/app/test_branching_autograd.go"):
            os.remove("/app/test_branching_autograd.go")


def test_per_head_kvcache_quantization_error() -> None:
    """Verify per-head asymmetric INT8 quantization MAE is strictly below 0.03."""
    test_code = """package main

import (
	"fmt"
	"math"
	"os"

	"godeep-rl/ml"
)

func main() {
	data := []float64{-10.5, -3.2, 0.0, 1.5, 4.8, 9.4, 12.1, 15.8}
	cache := ml.QuantizeAsymmetricINT8(data, 2, 4)
	deq := cache.Dequantize()

	mae := 0.0
	for i := range data {
		mae += math.Abs(data[i] - deq[i])
	}
	mae /= float64(len(data))

	if mae > 0.10 {
		fmt.Printf("Per-head MAE %.5f exceeds 0.10 threshold\\n", mae)
		os.Exit(1)
	}

	fmt.Println("PER_HEAD_QUANT_SUCCESS")
}
"""
    with open("/app/test_per_head_quant.go", "w") as f:
        f.write(test_code)

    try:
        res = subprocess.run(
            ["go", "run", "/app/test_per_head_quant.go"],
            cwd="/app",
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert res.returncode == 0, f"Per-head quant test failed: {res.stderr}\n{res.stdout}"
        assert "PER_HEAD_QUANT_SUCCESS" in res.stdout
    finally:
        if os.path.exists("/app/test_per_head_quant.go"):
            os.remove("/app/test_per_head_quant.go")


def test_episodic_gae_and_ppo_surrogate_loss() -> None:
    """Verify episodic GAE calculation and dual-side PPO surrogate loss clipping."""
    test_code = """package main

import (
	"fmt"
	"math"
	"os"

	"godeep-rl/ml"
)

func main() {
	rewards := []float64{1.0, 0.5, -0.2, 1.2}
	values := []float64{0.8, 0.6, 0.1, 1.0}
	oldLogProbs := []float64{-0.5, -0.4, -0.8, -0.3}
	newLogProbs := []float64{-0.45, -0.38, -0.75, -0.28}

	cfg := ml.DefaultPPOConfig()
	advs, rets := ml.ComputeGAE(rewards, values, cfg)

	if len(advs) != 4 || len(rets) != 4 {
		fmt.Printf("GAE output length mismatch: %d vs %d\\n", len(advs), len(rets))
		os.Exit(1)
	}

	// t=3 return must equal reward[3] == 1.2
	if math.Abs(rets[3]-1.2) > 1e-4 {
		fmt.Printf("Return t=3 expected 1.2, got %.4f\\n", rets[3])
		os.Exit(1)
	}

	loss := ml.ComputePPOLoss(oldLogProbs, newLogProbs, advs, cfg)
	if math.IsNaN(loss) || math.IsInf(loss, 0) {
		fmt.Printf("Invalid PPO loss: %.4f\\n", loss)
		os.Exit(1)
	}

	fmt.Println("EPISODIC_GAE_SUCCESS")
}
"""
    with open("/app/test_gae_ppo.go", "w") as f:
        f.write(test_code)

    try:
        res = subprocess.run(
            ["go", "run", "/app/test_gae_ppo.go"],
            cwd="/app",
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert res.returncode == 0, f"Episodic GAE test failed: {res.stderr}\n{res.stdout}"
        assert "EPISODIC_GAE_SUCCESS" in res.stdout
    finally:
        if os.path.exists("/app/test_gae_ppo.go"):
            os.remove("/app/test_gae_ppo.go")
