package dev.terminus.trivia.audit;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.terminus.trivia.registry.DungeonRegistry;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Optional;

public final class StateStore {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    public record CachedState(String inputDigest, DungeonRegistry registry) {}

    public Optional<CachedState> load(Path stateFile) throws Exception {
        if (!Files.isRegularFile(stateFile)) {
            return Optional.empty();
        }
        JsonNode node = MAPPER.readTree(stateFile.toFile());
        if (!node.path("success").asBoolean(false)) {
            return Optional.empty();
        }
        DungeonRegistry registry = MAPPER.treeToValue(node.get("registry"), DungeonRegistry.class);
        return Optional.of(new CachedState(node.path("input_digest").asText(), registry));
    }

    public void save(Path stateFile, String inputDigest, DungeonRegistry registry,
                     boolean success) throws Exception {
        AuditState.write(stateFile, inputDigest, registry, success);
    }
}
