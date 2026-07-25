package catalog

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"tidefront.local/game/internal/model"
	"tidefront.local/game/internal/strictjson"
)

func Load(dir string) (map[string]model.CatalogEntry, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, fmt.Errorf("read catalog: %w", err)
	}
	sort.Slice(entries, func(i, j int) bool { return entries[i].Name() < entries[j].Name() })
	out := map[string]model.CatalogEntry{}
	for _, ent := range entries {
		if ent.IsDir() || !strings.HasSuffix(ent.Name(), ".json") {
			continue
		}
		data, err := os.ReadFile(filepath.Join(dir, ent.Name()))
		if err != nil {
			return nil, err
		}
		var item model.CatalogEntry
		if err := strictjson.Decode(data, &item); err != nil {
			return nil, fmt.Errorf("catalog %s: %w", ent.Name(), err)
		}
		if item.SchemaVersion != 1 || item.Name == "" || item.EpochTAI < 0 || len(item.Nodal) < 2 {
			return nil, fmt.Errorf("catalog %s: invalid required fields", ent.Name())
		}
		if _, exists := out[item.Name]; exists {
			return nil, fmt.Errorf("duplicate catalog constituent %s", item.Name)
		}
		for i, n := range item.Nodal {
			if i > 0 && n.TAI <= item.Nodal[i-1].TAI {
				return nil, fmt.Errorf("catalog %s: nodal times are not strictly increasing", ent.Name())
			}
			if n.Factor < 0 {
				return nil, fmt.Errorf("catalog %s: negative nodal factor", ent.Name())
			}
		}
		out[item.Name] = item
	}
	return out, nil
}
