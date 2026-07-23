package dev.terminus.trivia.schema;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.networknt.schema.JsonSchema;
import com.networknt.schema.JsonSchemaFactory;
import com.networknt.schema.SpecVersion;
import com.networknt.schema.ValidationMessage;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

public final class SchemaCatalog {
    private final Map<String, JsonSchema> schemas = new HashMap<>();
    private final ObjectMapper mapper = new ObjectMapper();

    public SchemaCatalog(Path contractsDir) throws Exception {
        JsonSchemaFactory factory = JsonSchemaFactory.getInstance(SpecVersion.VersionFlag.V202012);
        try (var stream = Files.list(contractsDir)) {
            stream.filter(p -> p.getFileName().toString().endsWith(".schema.json"))
                    .forEach(p -> {
                        try {
                            JsonNode node = mapper.readTree(p.toFile());
                            schemas.put(p.getFileName().toString(), factory.getSchema(node));
                        } catch (Exception e) {
                            throw new IllegalStateException("Failed loading schema " + p, e);
                        }
                    });
        }
    }

    public JsonSchema get(String schemaFile) {
        JsonSchema schema = schemas.get(schemaFile);
        if (schema == null) {
            throw new IllegalArgumentException("Unknown schema: " + schemaFile);
        }
        return schema;
    }
}
