package register

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"gopkg.in/yaml.v3"

	"migrator/internal/contracts"
	"migrator/internal/topology"
)

type Authority struct {
	AuthoritativeStatuses []string `json:"authoritative_statuses"`
	ScopeOrder            []string `json:"scope_order"`
}

type Decision struct {
	ID          string
	Status      string
	Scope       string
	Effective   time.Time
	Supersedes  string
	Amends      string
	Source      string
	Target      string
	Environment string
	Method      string
	Path        string
	Audiences   []string
	Algorithms  []string
	KeyIDs      []string
	Issuer      string
	Fields      map[string]any
}

type Index struct {
	Decisions []struct {
		ID   string `yaml:"id"`
		Path string `yaml:"path"`
	} `yaml:"decisions"`
}

func LoadAuthority(root string) (*Authority, error) {
	raw, err := os.ReadFile(filepath.Join(root, "decision-authority.json"))
	if err != nil {
		return nil, err
	}
	var authority Authority
	return &authority, json.Unmarshal(raw, &authority)
}

func Load(root string, authority *Authority, c *contracts.Contracts) (map[string]Decision, error) {
	idxRaw, err := os.ReadFile(filepath.Join(root, "index.yaml"))
	if err != nil {
		return nil, err
	}
	var idx Index
	if err := yaml.Unmarshal(idxRaw, &idx); err != nil {
		return nil, err
	}

	records := make([]Decision, 0, len(idx.Decisions))
	for _, entry := range idx.Decisions {
		if !strings.HasSuffix(entry.Path, ".yaml") && !strings.HasSuffix(entry.Path, ".yml") {
			continue
		}
		raw, err := os.ReadFile(filepath.Join(root, entry.Path))
		if err != nil {
			return nil, err
		}
		var doc map[string]any
		if err := yaml.Unmarshal(raw, &doc); err != nil {
			return nil, err
		}
		records = append(records, decodeRecord(entry.ID, doc, c))
	}
	return materialize(records, authority)
}

func decodeRecord(id string, doc map[string]any, c *contracts.Contracts) Decision {
	record := Decision{ID: id, Fields: doc}
	record.Status = strings.ToLower(asString(doc["status"]))
	record.Scope = strings.ToLower(asString(doc["scope"]))
	if when, err := time.Parse("2006-01-02", asString(doc["effective_date"])); err == nil {
		record.Effective = when
	}
	record.Supersedes = asString(doc["supersedes"])
	record.Amends = asString(doc["amends"])
	if src, ok := doc["source"].(map[string]any); ok {
		record.Source = contracts.CanonicalService(asString(src["service"]), c.Aliases)
		record.Environment = strings.ToLower(asString(src["environment"]))
		record.Method = strings.ToUpper(asString(src["method"]))
		record.Path = asString(src["path"])
	}
	record.Target = contracts.CanonicalService(asString(doc["target_service"]), c.Aliases)
	record.Audiences = normalizeAudiences(doc["audiences"], c)
	record.Algorithms = normalizeStrings(doc["algorithms"])
	record.KeyIDs = normalizeStrings(doc["allowed_key_ids"])
	record.Issuer = asString(doc["issuer"])
	return record
}

func materialize(records []Decision, authority *Authority) (map[string]Decision, error) {
	allowed := map[string]struct{}{}
	for _, status := range authority.AuthoritativeStatuses {
		allowed[strings.ToLower(status)] = struct{}{}
	}
	byID := map[string]Decision{}
	for _, record := range records {
		byID[record.ID] = record
	}

	active := map[string]Decision{}
	for _, record := range records {
		status := strings.ToLower(record.Status)
		if _, ok := allowed[status]; !ok && status != "accepted" && status != "amended" {
			continue
		}
		if record.Amends != "" {
			base, ok := byID[record.Amends]
			if !ok {
				return nil, fmt.Errorf("amendment %s references missing %s", record.ID, record.Amends)
			}
			merged := base
			merged.ID = record.ID
			merged.Status = record.Status
			if len(record.Audiences) > 0 {
				merged.Audiences = record.Audiences
			}
			if len(record.Algorithms) > 0 {
				merged.Algorithms = record.Algorithms
			}
			if len(record.KeyIDs) > 0 {
				merged.KeyIDs = record.KeyIDs
			}
			if record.Issuer != "" {
				merged.Issuer = record.Issuer
			}
			delete(active, scopeBucket(base))
			record = merged
		}
		bucket := scopeBucket(record)
		if prior, ok := active[bucket]; ok {
			if record.Effective.After(prior.Effective) {
				active[bucket] = record
			}
		} else {
			active[bucket] = record
		}
	}

	out := map[string]Decision{}
	for bucket, record := range active {
		status := strings.ToLower(record.Status)
		if _, ok := allowed[status]; ok || status == "accepted" || status == "amended" {
			out[bucket] = record
		}
	}
	return out, nil
}

func scopeBucket(record Decision) string {
	switch record.Scope {
	case "edge":
		return fmt.Sprintf("edge|%s|%s|%s|%s|%s", record.Source, record.Target, record.Environment, record.Method, record.Path)
	case "service":
		return fmt.Sprintf("service|%s", record.Target)
	case "environment":
		return fmt.Sprintf("environment|%s", record.Environment)
	default:
		return "global"
	}
}

func Lookup(decisions map[string]Decision, edge topology.Edge) *Decision {
	candidates := []string{
		fmt.Sprintf("edge|%s|%s|%s|%s|%s", edge.Source, edge.Target, edge.Environment, edge.Method, edge.Path),
		fmt.Sprintf("service|%s", edge.Target),
		fmt.Sprintf("environment|%s", edge.Environment),
		"global",
	}
	for _, key := range candidates {
		if record, ok := decisions[key]; ok {
			copy := record
			return &copy
		}
	}
	return nil
}

func asString(value any) string {
	if value == nil {
		return ""
	}
	if text, ok := value.(string); ok {
		return text
	}
	return ""
}

func normalizeStrings(value any) []string {
	out := []string{}
	switch typed := value.(type) {
	case []any:
		for _, item := range typed {
			out = append(out, strings.TrimSpace(asString(item)))
		}
	case []string:
		out = append(out, typed...)
	}
	sort.Strings(out)
	return out
}

func normalizeAudiences(value any, c *contracts.Contracts) []string {
	raw := normalizeStrings(value)
	out := make([]string, 0, len(raw))
	seen := map[string]struct{}{}
	for _, audience := range raw {
		audience = contracts.NormalizeAudience(audience, c)
		if audience == "" {
			continue
		}
		if _, ok := seen[audience]; ok {
			continue
		}
		seen[audience] = struct{}{}
		out = append(out, audience)
	}
	sort.Strings(out)
	return out
}
