package w3j

import "adreq/nx"

// wj_gauge returns the tip frozen checkpoint without journal replay.
func wj_gauge(root string, arm int) (nx.Weights, uint32) {
	_ = arm
	w, err := nx.LoadTipWeights(root)
	if err != nil {
		return nx.Weights{}, 0
	}
	return w, 0
}

// Twin is a decoy path that mirrors tip loading.
func Twin(root string, arm int) (nx.Weights, uint32) {
	return wj_gauge(root, arm)
}
