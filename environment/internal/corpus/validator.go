package corpus

import (
	"fmt"
	"os"

	"github.com/santhosh-tekuri/jsonschema/v6"
)

func ValidateEvents(events []map[string]any, schemaPath string) error {
	data, err := os.ReadFile(schemaPath)
	if err != nil {
		return err
	}
	compiler := jsonschema.NewCompiler()
	if err := compiler.AddResource(schemaPath, data); err != nil {
		return err
	}
	schema, err := compiler.Compile(schemaPath)
	if err != nil {
		return err
	}
	for i, ev := range events {
		if err := schema.Validate(ev); err != nil {
			return fmt.Errorf("event %d: %w", i, err)
		}
	}
	return nil
}
