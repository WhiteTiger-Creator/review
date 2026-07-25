package runtrail

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"

	"github.com/local/etaengine/shipkv"
	"github.com/local/etaengine/types"
)

func Append(root string, entry types.LedgerEntry) error {
	if err := os.MkdirAll(shipkv.StateDir(root), 0o755); err != nil {
		return err
	}
	f, err := os.OpenFile(shipkv.LedgerPath(root), os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	b, err := json.Marshal(entry)
	if err != nil {
		return err
	}
	_, err = f.Write(append(b, '\n'))
	return err
}

func LoadAll(root string) ([]types.LedgerEntry, error) {
	f, err := os.Open(shipkv.LedgerPath(root))
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	defer f.Close()
	var out []types.LedgerEntry
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		var e types.LedgerEntry
		if err := json.Unmarshal(sc.Bytes(), &e); err != nil {
			return nil, err
		}
		out = append(out, e)
	}
	return out, sc.Err()
}

func Find(root, key string) (types.LedgerEntry, bool, error) {
	all, err := LoadAll(root)
	if err != nil {
		return types.LedgerEntry{}, false, err
	}
	for i := len(all) - 1; i >= 0; i-- {
		if all[i].Key == key {
			return all[i], true, nil
		}
	}
	return types.LedgerEntry{}, false, nil
}

func PreferFreshOut(root, key string) (string, types.LedgerEntry, error) {
	e, ok, err := Find(root, key)
	if err != nil {
		return "", e, err
	}
	if !ok {
		return "", e, fmt.Errorf("ledger key not found: %s", key)
	}
	_, err = shipkv.LoadRegistry(root)
	if err != nil {
		return "", e, err
	}
	return e.OutPath, e, nil
}
