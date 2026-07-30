package corpus

import (
	"bufio"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type Reader struct {
	Dir string
}

func NewReader(dir string) *Reader {
	return &Reader{Dir: dir}
}

func (r *Reader) LoadAll() ([]map[string]any, error) {
	entries, err := os.ReadDir(r.Dir)
	if err != nil {
		return nil, err
	}
	var shards []string
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".ndjson") {
			continue
		}
		shards = append(shards, e.Name())
	}
	sort.Strings(shards)
	var events []map[string]any
	for _, name := range shards {
		path := filepath.Join(r.Dir, name)
		f, err := os.Open(path)
		if err != nil {
			return nil, err
		}
		scanner := bufio.NewScanner(f)
		for scanner.Scan() {
			line := strings.TrimSpace(scanner.Text())
			if line == "" {
				continue
			}
			var ev map[string]any
			if err := json.Unmarshal([]byte(line), &ev); err != nil {
				f.Close()
				return nil, fmt.Errorf("%s: %w", path, err)
			}
			events = append(events, ev)
		}
		if err := scanner.Err(); err != nil {
			f.Close()
			return nil, err
		}
		f.Close()
	}
	return events, nil
}
