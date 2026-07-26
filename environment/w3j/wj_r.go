package w3j

import "adreq/nx"

// wj_r reconstructs freeze-epoch weights for an arm (broken: returns tip snapshot).
func wj_r(root string, arm int) (nx.Weights, uint32) {
	return wj_gauge(root, arm)
}

// Replay is the exported stage entry for pipe wiring.
func Replay(root string, arm int) (nx.Weights, uint32) {
	return wj_r(root, arm)
}
