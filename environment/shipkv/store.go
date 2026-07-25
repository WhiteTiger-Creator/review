package shipkv

import (
	"encoding/json"
	"os"
	"path/filepath"

	"github.com/local/etaengine/types"
)

func StateDir(root string) string {
	return filepath.Join(root, "state")
}

func RegistryPath(root string) string {
	return filepath.Join(StateDir(root), "registry.json")
}

func StagedPath(root string) string {
	return filepath.Join(StateDir(root), "staged.json")
}

func LedgerPath(root string) string {
	return filepath.Join(StateDir(root), "ledger.jsonl")
}

func LoadRegistry(root string) (types.RegistryState, error) {
	var st types.RegistryState
	b, err := os.ReadFile(RegistryPath(root))
	if err != nil {
		return st, err
	}
	err = json.Unmarshal(b, &st)
	if st.SettingsByGen == nil {
		st.SettingsByGen = map[string]types.InferSettings{}
	}
	return st, err
}

func SaveRegistry(root string, st types.RegistryState) error {
	if err := os.MkdirAll(StateDir(root), 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(st, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(RegistryPath(root), b, 0o644)
}

func LoadStaged(root string) (types.StagedState, bool, error) {
	var st types.StagedState
	b, err := os.ReadFile(StagedPath(root))
	if err != nil {
		if os.IsNotExist(err) {
			return st, false, nil
		}
		return st, false, err
	}
	if err := json.Unmarshal(b, &st); err != nil {
		return st, false, err
	}
	return st, true, nil
}

func SaveStaged(root string, st types.StagedState) error {
	if err := os.MkdirAll(StateDir(root), 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(st, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(StagedPath(root), b, 0o644)
}

func ClearStaged(root string) error {
	err := os.Remove(StagedPath(root))
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	return nil
}

// ResolveEvalKnobs selects knobs and generation labels for evaluate.
func ResolveEvalKnobs(root string) (types.InferSettings, uint64, string, error) {
	reg, err := LoadRegistry(root)
	if err != nil {
		return types.InferSettings{}, 0, "", err
	}
	staged, ok, err := LoadStaged(root)
	if err != nil {
		return types.InferSettings{}, 0, "", err
	}
	if ok && staged.Incomplete {
		return staged.Settings, reg.ActiveGen, reg.EpochToken, nil
	}
	return reg.Settings, reg.ActiveGen, reg.EpochToken, nil
}
