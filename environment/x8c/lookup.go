package x8c

func fn_x8(graph GraphView, toggles map[string]bool, mat Material, cacheDir string) (Decision, error) {
	var kept []Edge
	var deferred []Edge
	for _, e := range graph.Edges {
		if !e.Optional {
			kept = append(kept, e)
			continue
		}
		on := toggles[e.ActKey]
		seen := e.ActPresent
		if on || seen {
			if on && !seen {
				deferred = append(deferred, e)
			} else {
				kept = append(kept, e)
			}
		}
	}
	kept = append(kept, deferred...)

	fp := FingerprintFrames(mat.Frames)
	key := HashBytes(mat.SeedJSON, []byte(fp), []byte(mat.PeerFinger))
	storedPeer, rows, ok, err := ReadCacheBlob(cacheDir, key)
	if err != nil {
		return Decision{}, err
	}
	if ok {
		if storedPeer != "" && storedPeer != mat.PeerFinger {
			return Decision{Hit: false, KeyHex: key, Edges: kept}, nil
		}
		if len(rows) == 0 {
			return Decision{Hit: false, KeyHex: key, Edges: graph.Edges}, nil
		}
		return Decision{Hit: true, KeyHex: key, RowsRaw: rows, Edges: graph.Edges}, nil
	}
	return Decision{Hit: false, KeyHex: key, Edges: kept}, nil
}

func FnX8(graph GraphView, toggles map[string]bool, mat Material, cacheDir string) (Decision, error) {
	return fn_x8(graph, toggles, mat, cacheDir)
}

func PutCache(cacheDir, keyHex string, blob []byte) error {
	return putCache(cacheDir, keyHex, blob)
}
