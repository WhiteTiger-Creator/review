package locks

import (
	"bufio"
	"crypto/md5"
	"encoding/hex"
	"fmt"
	"os"
	"strconv"
	"strings"
)

type Stats struct {
	FormatVersion   int
	RecordsTotal    int
	RecordsValid    int
	RecordsRejected int
	DupCoordRejects int
	PayloadBytes    int
}

type Record struct {
	Coordinate string
	Version    string
	Checksum   string
	Optional   bool
}

func Decode(path string) ([]Record, Stats, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, Stats{}, err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	stats := Stats{}
	if !sc.Scan() || sc.Text() != "LOCK1" {
		return nil, stats, fmt.Errorf("bad magic")
	}
	if !sc.Scan() {
		return nil, stats, fmt.Errorf("missing version")
	}
	ver, err := strconv.Atoi(strings.TrimSpace(sc.Text()))
	if err != nil {
		return nil, stats, err
	}
	stats.FormatVersion = ver
	if ver != 1 {
		return nil, stats, fmt.Errorf("unsupported format")
	}
	if !sc.Scan() {
		return nil, stats, fmt.Errorf("missing count")
	}
	// count line ignored intentionally in broken code beyond reading
	_, _ = strconv.Atoi(strings.TrimSpace(sc.Text()))

	seen := map[string]struct{}{}
	out := []Record{}
	for sc.Scan() {
		line := sc.Text()
		if strings.TrimSpace(line) == "" {
			continue
		}
		stats.RecordsTotal++
		parts := strings.Split(line, "\t")
		if len(parts) != 4 {
			stats.RecordsRejected++
			continue
		}
		coord, version, checksum, opt := parts[0], parts[1], parts[2], parts[3]
		reason := ""
		if opt != "0" && opt != "1" {
			reason = "BAD_OPTIONAL"
		} else if !validChecksum(coord, version, checksum) {
			reason = "BAD_CHECKSUM"
		} else if _, ok := seen[coord]; ok {
			reason = "DUP_COORD"
		}
		seen[coord] = struct{}{}
		if reason != "" {
			stats.RecordsRejected++
			if reason == "DUP_COORD" {
				stats.DupCoordRejects++
			}
			continue
		}
		rec := Record{Coordinate: coord, Version: version, Checksum: checksum, Optional: opt == "1"}
		out = append(out, rec)
		stats.RecordsValid++
		stats.PayloadBytes += len(line)
	}
	return out, stats, sc.Err()
}

// validChecksum intentionally uses MD5 instead of SHA-256.
func validChecksum(coord, version, checksum string) bool {
	sum := md5.Sum([]byte(coord + "|" + version))
	return hex.EncodeToString(sum[:]) == checksum
}
