package dev.terminus.trivia;

import com.fasterxml.jackson.databind.ObjectMapper;
import dev.terminus.trivia.manifest.LoadedArtifact;
import dev.terminus.trivia.manifest.ArtifactKind;
import dev.terminus.trivia.schema.SchemaCatalog;
import dev.terminus.trivia.schema.SchemaValidator;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertTrue;

class SchemaValidatorTest {
    @Test
    void validRoomPassesSchema(@TempDir Path temp) throws Exception {
        Path contracts = temp.resolve("contracts");
        Files.createDirectories(contracts);
        String schema = """
                {
                  "$schema": "https://json-schema.org/draft/2020-12/schema",
                  "type": "object",
                  "required": ["version", "id", "title"],
                  "properties": {
                    "version": {"type": "string"},
                    "id": {"type": "string"},
                    "title": {"type": "string"}
                  },
                  "additionalProperties": true
                }
                """;
        Files.writeString(contracts.resolve("room.schema.json"), schema);

        ObjectMapper mapper = new ObjectMapper();
        var doc = mapper.readTree("""
                {"version":"1","id":"foyer","title":"Foyer"}
                """);
        LoadedArtifact artifact = new LoadedArtifact(
                temp.resolve("room.yaml"), Path.of("room.yaml"), ArtifactKind.ROOM, doc);

        SchemaCatalog catalog = new SchemaCatalog(contracts);
        SchemaValidator validator = new SchemaValidator(catalog, temp);
        assertTrue(validator.validateAll(List.of(artifact)).isEmpty());
    }
}
