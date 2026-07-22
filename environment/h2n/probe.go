package h2n

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
)

type ProbeView struct {
	PeerHi map[string]string
}

func LoadPeerCaps(path string) (ProbeView, error) {
	f, err := os.Open(path)
	if err != nil {
		return ProbeView{}, err
	}
	defer f.Close()
	peer := map[string]string{}
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		var raw map[string]any
		if err := json.Unmarshal([]byte(line), &raw); err != nil {
			return ProbeView{}, err
		}
		lift, _ := raw["lift"].(bool)
		peerHi, _ := raw["peer_hi"].(string)
		pkg, _ := raw["pkg"].(string)
		dep, _ := raw["dep"].(string)
		if !lift || peerHi == "" || pkg == "" || dep == "" {
			continue
		}
		key := pkg + "\x00" + dep
		peer[key] = peerHi
	}
	if err := sc.Err(); err != nil {
		return ProbeView{}, err
	}
	return ProbeView{PeerHi: peer}, nil
}

func FingerprintPeers(p ProbeView) string {
	keys := make([]string, 0, len(p.PeerHi))
	for k := range p.PeerHi {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	h := sha256.New()
	for _, k := range keys {
		fmt.Fprintf(h, "%s=%s\n", k, p.PeerHi[k])
	}
	return hex.EncodeToString(h.Sum(nil))
}
