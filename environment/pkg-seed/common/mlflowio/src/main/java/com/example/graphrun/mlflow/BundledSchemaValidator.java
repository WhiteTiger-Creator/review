package com.example.graphrun.mlflow;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.networknt.schema.JsonSchema;
import com.networknt.schema.JsonSchemaFactory;
import com.networknt.schema.SpecVersion;
import com.networknt.schema.ValidationMessage;

import java.io.InputStream;
import java.util.Set;

public final class BundledSchemaValidator {

    private final ObjectMapper mapper = new ObjectMapper();
    private final JsonSchema schema;

    public BundledSchemaValidator() {
        try (InputStream in = getClass().getResourceAsStream("/bundled/run_callback.schema.json")) {
            if (in == null) {
                throw new IllegalStateException("bundled schema missing");
            }
            JsonNode schemaNode = mapper.readTree(in);
            JsonSchemaFactory factory = JsonSchemaFactory.getInstance(SpecVersion.VersionFlag.V7);
            this.schema = factory.getSchema(schemaNode);
        } catch (Exception e) {
            throw new IllegalStateException("failed to load bundled schema", e);
        }
    }

    public void validate(JsonNode callback) {
        Set<ValidationMessage> errors = schema.validate(callback);
        if (!errors.isEmpty()) {
            throw new IllegalArgumentException("callback schema validation failed: " + errors);
        }
    }
}
