//go:build !labals

package als

import (
	"math"
	"trustloom/internal/data"
	"trustloom/internal/hashinit"
)

const (
	Factors   = 4
	Lambda    = 0.15
	Alpha     = 25.0
	Iters     = 8
	InitScale = 0.02
	Fade      = 1.0 // lab still disables fade
	Mid       = 8   // no schedule split
)

type Model struct {
	X        [][]float64
	Y        [][]float64
	Schedule []float64
	RStar    int
}

// Fit still uses user-then-item Hu order, unscaled ridge, and absolute log1p confidence.
func Fit(cat *data.Catalog) *Model {
	U := len(cat.Users)
	I := len(cat.Items)
	rStar := cat.RStar
	if rStar < 1 {
		rStar = 1
	}
	X := make([][]float64, U)
	Y := make([][]float64, I)
	for u := 0; u < U; u++ {
		X[u] = make([]float64, Factors)
		for f := 0; f < Factors; f++ {
			X[u][f] = InitScale * hashinit.Unit("user", cat.Users[u], f)
		}
	}
	for i := 0; i < I; i++ {
		Y[i] = make([]float64, Factors)
		for f := 0; f < Factors; f++ {
			Y[i][f] = InitScale * hashinit.Unit("item", cat.Items[i], f)
		}
	}
	schedule := make([]float64, Iters)
	for t := 1; t <= Iters; t++ {
		lt := Lambda
		schedule[t-1] = lt

		// wrong order: users first
		YtY := gram(Y)
		newX := make([][]float64, U)
		for u := 0; u < U; u++ {
			obs := cat.UserObs[u]
			A := addScaledEye(YtY, lt) // missing n_u
			b := make([]float64, Factors)
			for _, o := range obs {
				c := 1.0 + Alpha*math.Log1p(float64(o.Count)) // missing /log1p(R*)
				yi := Y[o.Index]
				addOuter(&A, yi, c-1.0)
				for f := 0; f < Factors; f++ {
					b[f] += c * yi[f]
				}
			}
			newX[u] = cholSolve(A, b)
		}
		X = newX

		XtX := gram(X)
		newY := make([][]float64, I)
		for i := 0; i < I; i++ {
			obs := cat.ItemObs[i]
			A := addScaledEye(XtX, lt)
			b := make([]float64, Factors)
			for _, o := range obs {
				c := 1.0 + Alpha*math.Log1p(float64(o.Count))
				xu := X[o.Index]
				addOuter(&A, xu, c-1.0)
				for f := 0; f < Factors; f++ {
					b[f] += c * xu[f]
				}
			}
			newY[i] = cholSolve(A, b)
		}
		Y = newY
	}
	// missing packing
	return &Model{X: X, Y: Y, Schedule: schedule, RStar: rStar}
}

func (m *Model) Score(cat *data.Catalog, userID, itemID int) float64 {
	ui, okU := cat.UserIdx[userID]
	ii, okI := cat.ItemIdx[itemID]
	if !okU || !okI {
		return 0.0
	}
	return dot(m.X[ui], m.Y[ii])
}

func (m *Model) MeanAbsScore(cat *data.Catalog) float64 {
	// wrong: averages query scores only / returns 0
	return 0
}

func gram(M [][]float64) [][]float64 {
	G := make([][]float64, Factors)
	for a := 0; a < Factors; a++ {
		G[a] = make([]float64, Factors)
	}
	for _, row := range M {
		for a := 0; a < Factors; a++ {
			for b := 0; b < Factors; b++ {
				G[a][b] += row[a] * row[b]
			}
		}
	}
	return G
}

func addScaledEye(base [][]float64, scale float64) [][]float64 {
	A := make([][]float64, Factors)
	for i := 0; i < Factors; i++ {
		A[i] = make([]float64, Factors)
		copy(A[i], base[i])
		A[i][i] += scale
	}
	return A
}

func addOuter(A *[][]float64, v []float64, scale float64) {
	for i := 0; i < Factors; i++ {
		for j := 0; j < Factors; j++ {
			(*A)[i][j] += scale * v[i] * v[j]
		}
	}
}

func cholSolve(A [][]float64, b []float64) []float64 {
	n := Factors
	L := make([][]float64, n)
	for i := 0; i < n; i++ {
		L[i] = make([]float64, n)
	}
	for i := 0; i < n; i++ {
		for j := 0; j <= i; j++ {
			s := 0.0
			for k := 0; k < j; k++ {
				s += L[i][k] * L[j][k]
			}
			if i == j {
				v := A[i][i] - s
				if v < 0 {
					v = 0
				}
				L[i][j] = math.Sqrt(v)
			} else {
				L[i][j] = (A[i][j] - s) / L[j][j]
			}
		}
	}
	y := make([]float64, n)
	for i := 0; i < n; i++ {
		s := 0.0
		for k := 0; k < i; k++ {
			s += L[i][k] * y[k]
		}
		y[i] = (b[i] - s) / L[i][i]
	}
	x := make([]float64, n)
	for i := n - 1; i >= 0; i-- {
		s := 0.0
		for k := i + 1; k < n; k++ {
			s += L[k][i] * x[k]
		}
		x[i] = (y[i] - s) / L[i][i]
	}
	return x
}

func dot(a, b []float64) float64 {
	s := 0.0
	for i := range a {
		s += a[i] * b[i]
	}
	return s
}
