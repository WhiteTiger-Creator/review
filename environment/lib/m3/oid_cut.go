package m3

import (
	"os"
	"strings"
)

func CutOIDs(repo string) ([]string, error) {
	data, err := os.ReadFile(repo + "/.git/shallow")
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	var oids []string
	for _, ln := range strings.Split(string(data), "\n") {
		ln = strings.TrimSpace(ln)
		if ln != "" {
			oids = append(oids, ln)
		}
	}
	return oids, nil
}
