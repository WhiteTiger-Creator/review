package q2

// EdgeCap holds nominal capacity and reclaim for one adjacent-pair edge.
type EdgeCap struct {
	Key     string
	Cap     float64
	Reclaim float64
}

// Assign is one use contribution on an edge.
type Assign struct {
	Key string
	Use float64
}

// MassLedger accumulates joint uses and residuals per edge.
type MassLedger struct {
	Caps  map[string]EdgeCap
	Uses  map[string]float64
	Res   map[string]float64
	Order []string
}

// fn_p9 folds assignment residuals into mass ledgers under epsilon.
func fn_p9(ledgers *MassLedger, assigns []Assign, eps float64) int {
	if ledgers.Uses == nil {
		ledgers.Uses = map[string]float64{}
	}
	if ledgers.Res == nil {
		ledgers.Res = map[string]float64{}
	}
	viol := 0
	for _, a := range assigns {
		cap := ledgers.Caps[a.Key]
		if a.Use > cap.Cap+eps {
			viol++
		}
		ledgers.Uses[a.Key] = a.Use
		ledgers.Res[a.Key] = a.Use - cap.Cap
	}
	return viol
}

// ApplyFold invokes fn_p9 after clearing use maps.
func ApplyFold(ledgers *MassLedger, assigns []Assign, eps float64) int {
	ledgers.Uses = map[string]float64{}
	ledgers.Res = map[string]float64{}
	return fn_p9(ledgers, assigns, eps)
}

// UtilMax returns max joint_use/eff across edges.
func UtilMax(ledgers *MassLedger) float64 {
	max := 0.0
	for _, k := range ledgers.Order {
		cap := ledgers.Caps[k]
		eff := cap.Cap - cap.Reclaim
		if eff < 1e-12 {
			eff = 1e-12
		}
		u := ledgers.Uses[k] / eff
		if u > max {
			max = u
		}
	}
	return max
}
