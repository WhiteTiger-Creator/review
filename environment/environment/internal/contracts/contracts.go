package contracts

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type Contracts struct {
	Aliases           map[string]string `json:"aliases"`
	AllowedAlgorithms []string          `json:"allowed_algorithms"`
	AllowedKeyTypes   []string          `json:"allowed_key_types"`
	RetiredFields     []string          `json:"retired_mtls_fields"`
	AudienceSuffix    string            `json:"audience_suffix"`
}

func Load(root string) (*Contracts, error) {
	raw, err := os.ReadFile(filepath.Join(root, "policy-contract.json"))
	if err != nil {
		return nil, err
	}
	var c Contracts
	if err := json.Unmarshal(raw, &c); err != nil {
		return nil, err
	}
	aliasRaw, err := os.ReadFile(filepath.Join(root, "alias-register.json"))
	if err != nil {
		return nil, err
	}
	var aliasDoc struct {
		Aliases map[string]string `json:"aliases"`
	}
	if err := json.Unmarshal(aliasRaw, &aliasDoc); err != nil {
		return nil, err
	}
	c.Aliases = aliasDoc.Aliases
	return &c, nil
}

func CanonicalService(name string, aliases map[string]string) string {
	name = strings.TrimSpace(strings.ToLower(name))
	if c, ok := aliases[name]; ok {
		return c
	}
	return name
}

func NormalizeAudience(a string, c *Contracts) string {
	a = strings.TrimSpace(a)
	if a == "" {
		return ""
	}
	if c.AudienceSuffix != "" && !strings.HasSuffix(a, c.AudienceSuffix) {
		a = strings.TrimRight(a, "/") + c.AudienceSuffix
	}
	return a
}

func SortStrings(in []string) []string {
	out := append([]string{}, in...)
	sort.Strings(out)
	return out
}
