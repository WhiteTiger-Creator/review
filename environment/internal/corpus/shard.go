package corpus

import "path/filepath"

func ShardNames(dir string) ([]string, error) {
	r := NewReader(dir)
	_, err := r.LoadAll()
	if err != nil {
		return nil, err
	}
	return []string{filepath.Base(dir)}, nil
}
