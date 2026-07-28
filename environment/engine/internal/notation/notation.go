package notation

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type Table struct {
	Squares []string          `json:"squares"`
	Pieces  map[string]string `json:"pieces"`
}

func Load(path string) (Table, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return Table{}, err
	}
	var t Table
	if err := json.Unmarshal(b, &t); err != nil {
		return Table{}, err
	}
	return t, nil
}

func NormalizeID(id string, mapping map[string]string) string {
	if v, ok := mapping[id]; ok {
		return v
	}
	return id
}

func SortedJoin(xs []string) string {
	cp := append([]string{}, xs...)
	sort.Strings(cp)
	return strings.Join(cp, ",")
}

func DefaultPath(root string) string {
	return filepath.Join(root, "notation", "standard.json")
}
