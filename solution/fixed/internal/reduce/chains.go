package reduce

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
)

type Chain struct {
	ChainID   string   `json:"chain_id"`
	TenantID  string   `json:"tenant_id"`
	TokenID   string   `json:"token_id"`
	EventIDs  []string `json:"event_ids"`
	TraceID   string   `json:"trace_id"`
	RequestID string   `json:"request_id"`
}

func BuildChains(events []map[string]any, configDir string) ([]Chain, error) {
	collectors, err := loadCollectors(filepath.Join(configDir, "collectors.json"))
	if err != nil {
		return nil, err
	}
	normalized := normalizeEvents(events, collectors)
	byKey := map[string]*Chain{}
	for _, ev := range normalized {
		key := chainKey(ev)
		ch, ok := byKey[key]
		if !ok {
			ch = &Chain{
				ChainID:   stableID("chain", key),
				TenantID:  str(ev["tenant_id"]),
				TokenID:   tokenID(ev),
				TraceID:   str(ev["trace_id"]),
				RequestID: str(ev["request_id"]),
			}
			byKey[key] = ch
		}
		ch.EventIDs = append(ch.EventIDs, str(ev["event_id"]))
	}
	out := make([]Chain, 0, len(byKey))
	for _, ch := range byKey {
		out = append(out, *ch)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].ChainID < out[j].ChainID })
	return out, nil
}

func chainKey(ev map[string]any) string {
	tenant := str(ev["tenant_id"])
	payload, _ := ev["payload"].(map[string]any)
	if payload != nil {
		if exchange := str(payload["exchange_id"]); exchange != "" {
			return tenant + "|" + exchange
		}
		if family := str(payload["refresh_family"]); family != "" {
			return tenant + "|" + family
		}
		if family := str(payload["refresh_family_id"]); family != "" {
			return tenant + "|" + family
		}
	}
	trace := str(ev["trace_id"])
	if trace != "" {
		return tenant + "|" + trace
	}
	return tenant + "|" + str(ev["request_id"])
}

func tokenID(ev map[string]any) string {
	payload, _ := ev["payload"].(map[string]any)
	fp := str(payload["token_fingerprint"])
	if fp == "" {
		fp = str(payload["parent_token_fingerprint"])
	}
	return stableID("token", str(ev["tenant_id"])+"|"+fp)
}

func loadCollectors(path string) (map[string]any, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var cfg map[string]any
	if err := json.Unmarshal(b, &cfg); err != nil {
		return nil, err
	}
	return cfg, nil
}

func normalizeEvents(events []map[string]any, collectors map[string]any) []map[string]any {
	out := make([]map[string]any, len(events))
	copy(out, events)
	sort.SliceStable(out, func(i, j int) bool {
		ai := logicalKey(out[i], collectors)
		aj := logicalKey(out[j], collectors)
		if ai == aj {
			return str(out[i]["event_id"]) < str(out[j]["event_id"])
		}
		return ai < aj
	})
	return out
}

func logicalKey(ev map[string]any, collectors map[string]any) string {
	ts := str(ev["observed_at"])
	collector := str(ev["collector_id"])
	offset := "0"
	if items, ok := collectors["collectors"].([]any); ok {
		for _, item := range items {
			m, _ := item.(map[string]any)
			if str(m["collector_id"]) == collector {
				offset = fmt.Sprintf("%v", m["clock_offset_ms"])
			}
		}
	}
	seq := fmt.Sprintf("%v", ev["collector_sequence"])
	return offset + "|" + ts + "|" + seq
}

func str(v any) string {
	if v == nil {
		return ""
	}
	return fmt.Sprintf("%v", v)
}
