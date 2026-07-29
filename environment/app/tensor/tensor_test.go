package tensor_test

import (
	"math"
	"testing"
	"godeep-rl/tensor"
)

func TestMatMulBackward(t *testing.T) {
	// A: 2x3, B: 3x2
	aData := []float64{1.0, 2.0, 3.0, 4.0, 5.0, 6.0}
	bData := []float64{0.1, 0.2, 0.3, 0.4, 0.5, 0.6}

	a := tensor.NewTensor([]int{2, 3}, aData)
	b := tensor.NewTensor([]int{3, 2}, bData)
	a.RequiresGrad = true
	b.RequiresGrad = true

	c, err := tensor.MatMul(a, b)
	if err != nil {
		t.Fatalf("MatMul failed: %v", err)
	}

	c.Backward()

	if a.Grad == nil || b.Grad == nil {
		t.Fatalf("Gradients are nil")
	}

	// Finite-difference numerical gradient check for A[0,0]
	eps := 1e-5
	aDataPlus := []float64{1.0 + eps, 2.0, 3.0, 4.0, 5.0, 6.0}
	aDataMinus := []float64{1.0 - eps, 2.0, 3.0, 4.0, 5.0, 6.0}

	aPlus := tensor.NewTensor([]int{2, 3}, aDataPlus)
	aMinus := tensor.NewTensor([]int{2, 3}, aDataMinus)
	bNorm := tensor.NewTensor([]int{3, 2}, bData)

	cPlus, _ := tensor.MatMul(aPlus, bNorm)
	cMinus, _ := tensor.MatMul(aMinus, bNorm)

	sumPlus := 0.0
	for _, v := range cPlus.Data {
		sumPlus += v
	}
	sumMinus := 0.0
	for _, v := range cMinus.Data {
		sumMinus += v
	}

	numGrad := (sumPlus - sumMinus) / (2.0 * eps)
	if math.Abs(a.Grad[0]-numGrad) > 1e-4 {
		t.Errorf("MatMul A grad mismatch: got %.5f, expected %.5f", a.Grad[0], numGrad)
	}
}

func TestSoftmaxBackward(t *testing.T) {
	x := tensor.NewTensor([]int{3}, []float64{1.0, 2.0, 3.0})
	x.RequiresGrad = true

	out, err := tensor.Softmax(x)
	if err != nil {
		t.Fatalf("Softmax error: %v", err)
	}

	out.Backward()

	// Derivative of sum(Softmax(x)) with respect to any x_i should be 0 since sum(Softmax) == 1
	for i, g := range x.Grad {
		if math.Abs(g) > 1e-5 {
			t.Errorf("Softmax grad x[%d] should be 0, got %.5f", i, g)
		}
	}
}
