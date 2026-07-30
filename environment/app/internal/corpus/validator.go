package corpus

import "fmt"

func ValidateEvents(events []map[string]any, schemaPath string) error {
	required := []string{
		"schema_version",
		"event_id",
		"collector_id",
		"collector_sequence",
		"observed_at",
		"tenant_id",
		"event_type",
		"payload",
	}
	for i, ev := range events {
		for _, key := range required {
			if _, ok := ev[key]; !ok {
				return fmt.Errorf("event %d missing %s", i, key)
			}
		}
	}
	return nil
}
