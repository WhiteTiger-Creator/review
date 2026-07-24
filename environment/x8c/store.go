package x8c

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type cacheBlob struct {
	PeerFinger string          `json:"peer_finger"`
	Rows       json.RawMessage `json:"rows"`
}

func putCache(cacheDir, keyHex string, blob []byte) error {
	if err := os.MkdirAll(cacheDir, 0o755); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(cacheDir, keyHex+".json"), blob, 0o644)
}

func WrapCacheBlob(peerFinger string, rowsJSON []byte) ([]byte, error) {
	return json.Marshal(cacheBlob{PeerFinger: peerFinger, Rows: rowsJSON})
}

func ReadCacheBlob(cacheDir, keyHex string) (peerFinger string, rows []byte, ok bool, err error) {
	b, err := os.ReadFile(filepath.Join(cacheDir, keyHex+".json"))
	if err != nil {
		if os.IsNotExist(err) {
			return "", nil, false, nil
		}
		return "", nil, false, err
	}
	var cb cacheBlob
	if err := json.Unmarshal(b, &cb); err != nil {
		return "", nil, false, err
	}
	return cb.PeerFinger, []byte(cb.Rows), true, nil
}
