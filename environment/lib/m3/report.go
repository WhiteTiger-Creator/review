package m3

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

type WalkRecord struct {
	Ordinal  int    `json:"ordinal"`
	Kind     string `json:"kind"`
	ObjectID string `json:"object_id"`
}

type Rejection struct {
	Code   string `json:"code"`
	Detail string `json:"detail"`
}

type Report struct {
	SchemaVersion int          `json:"schema_version"`
	RepoPath      string       `json:"repo_path"`
	ReleaseRef    string       `json:"release_ref"`
	Admitted      bool         `json:"admitted"`
	WalkRecords   []WalkRecord `json:"walk_records"`
	Rejection     *Rejection   `json:"rejection,omitempty"`
	WalkDigest    string       `json:"walk_digest"`
}

func DigestWalk(records []WalkRecord) string {
	h := sha256.New()
	for _, r := range records {
		_, _ = fmt.Fprintf(h, "%d:%s:%s\n", r.Ordinal, r.Kind, r.ObjectID)
	}
	return hex.EncodeToString(h.Sum(nil))
}

func WriteReport(path string, rep Report) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	rep.WalkDigest = DigestWalk(rep.WalkRecords)
	b, err := json.MarshalIndent(rep, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(b, '\n'), 0o644)
}
