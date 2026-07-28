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
	Fade      = 0.994
	Mid       = 4
	Gamma     = 5.0
	JitterEps = 1e-8
	Beta      = 0.5
	ConfCeil  = 40.0
)

type Model struct {
	X        [][]float64
	Y        [][]float64
	Schedule []float64
	RStar    int
}

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
		if t > Mid {
			lt = 2 * Lambda
		}
		schedule[t-1] = lt
		doFade := lt == Lambda

		XtX := gram(X)
		newY := make([][]float64, I)
		for i := 0; i < I; i++ {
			obs := cat.ItemObs[i]
			nI := len(obs)
			rI := localMax(obs)
			A := addScaledEye(XtX, lt*float64(nI))
			b := make([]float64, Factors)
			for _, o := range obs {
				c := confidence(o.Count, rI)
				xu := X[o.Index]
				addOuter(&A, xu, c-1.0)
				for f := 0; f < Factors; f++ {
					b[f] += c * xu[f]
				}
			}
			addJitter(&A, lt)
			newY[i] = cholSolve(A, b)
		}
		blended := make([][]float64, I)
		for i := 0; i < I; i++ {
			blended[i] = make([]float64, Factors)
			for f := 0; f < Factors; f++ {
				blended[i][f] = (1.0-Beta)*Y[i][f] + Beta*newY[i][f]
			}
		}
		if doFade {
			scaleRows(blended, Fade)
		}
		Y = blended

		YtY := gram(Y)
		newX := make([][]float64, U)
		for u := 0; u < U; u++ {
			obs := cat.UserObs[u]
			nU := len(obs)
			rU := localMax(obs)
			A := addScaledEye(YtY, lt*float64(nU))
			b := make([]float64, Factors)
			for _, o := range obs {
				c := confidence(o.Count, rU)
				yi := Y[o.Index]
				addOuter(&A, yi, c-1.0)
				for f := 0; f < Factors; f++ {
					b[f] += c * yi[f]
				}
			}
			addJitter(&A, lt)
			newX[u] = cholSolve(A, b)
		}
		if doFade {
			scaleRows(newX, Fade)
		}
		X = newX
	}
	normalizeRows(X)
	normalizeRows(Y)
	polarityAlign(X, Y)
	signCanon(X)
	signCanon(Y)
	return &Model{X: X, Y: Y, Schedule: schedule, RStar: rStar}
}

func localMax(obs []data.Obs) int {
	if len(obs) == 0 {
		return 1
	}
	m := obs[0].Count
	for _, o := range obs[1:] {
		if o.Count > m {
			m = o.Count
		}
	}
	return m
}

func confidence(r, rLocal int) float64 {
	c := 1.0 + Alpha*math.Log1p(float64(r))/math.Log1p(float64(rLocal))
	if c > ConfCeil {
		return ConfCeil
	}
	return c
}

func (m *Model) Score(cat *data.Catalog, userID, itemID int) float64 {
	ui, okU := cat.UserIdx[userID]
	ii, okI := cat.ItemIdx[itemID]
	if !okU || !okI {
		return 0.0
	}
	raw := dot(m.X[ui], m.Y[ii])
	nU := len(cat.UserObs[ui])
	nI := len(cat.ItemObs[ii])
	return raw * math.Sqrt(float64(nU+nI)/(float64(nU+nI)+Gamma))
}

func (m *Model) ScoreRaw(cat *data.Catalog, userID, itemID int) float64 {
	ui, okU := cat.UserIdx[userID]
	ii, okI := cat.ItemIdx[itemID]
	if !okU || !okI {
		return 0.0
	}
	return dot(m.X[ui], m.Y[ii])
}

func (m *Model) MeanAbsScore(cat *data.Catalog) float64 {
	U := len(cat.Users)
	I := len(cat.Items)
	if U == 0 || I == 0 {
		return 0
	}
	sum := 0.0
	for u := 0; u < U; u++ {
		for i := 0; i < I; i++ {
			v := dot(m.X[u], m.Y[i])
			if v < 0 {
				sum -= v
			} else {
				sum += v
			}
		}
	}
	return sum / float64(U*I)
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

func scaleRows(M [][]float64, s float64) {
	for i := range M {
		for j := range M[i] {
			M[i][j] *= s
		}
	}
}

func normalizeRows(M [][]float64) {
	for i := range M {
		nrm := 0.0
		for _, v := range M[i] {
			nrm += v * v
		}
		nrm = math.Sqrt(nrm)
		if nrm == 0 {
			continue
		}
		for j := range M[i] {
			M[i][j] /= nrm
		}
	}
}

func addJitter(A *[][]float64, lambdaT float64) {
	j := JitterEps * lambdaT
	for f := 0; f < Factors; f++ {
		(*A)[f][f] += j
	}
}

func polarityAlign(X, Y [][]float64) {
	sum := 0.0
	for _, row := range X {
		if len(row) > 0 {
			sum += row[0]
		}
	}
	if sum >= 0 {
		return
	}
	for i := range X {
		for j := range X[i] {
			X[i][j] = -X[i][j]
		}
	}
	for i := range Y {
		for j := range Y[i] {
			Y[i][j] = -Y[i][j]
		}
	}
}

func signCanon(M [][]float64) {
	for i := range M {
		if len(M[i]) > 0 && M[i][0] < 0 {
			for j := range M[i] {
				M[i][j] = -M[i][j]
			}
		}
	}
}

func dot(a, b []float64) float64 {
	s := 0.0
	for i := range a {
		s += a[i] * b[i]
	}
	return s
}
