package dev.terminus.trivia.audit;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.terminus.trivia.registry.DungeonRegistry;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.Optional;

public final class StateStore {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    public record CachedState(String inputDigest, DungeonRegistry registry) {}

    public Optional<CachedState> load(Path stateFile) throws Exception {
        if (!Files.isRegularFile(stateFile)) {
            return Optional.empty();
        }
        String raw = Files.readString(stateFile);
        if (!raw.trim().endsWith("}")) {
            return Optional.empty();
        }
        JsonNode node;
        try {
            node = MAPPER.readTree(raw);
        } catch (Exception ex) {
            return Optional.empty();
        }
        if (!node.path("success").asBoolean(false)) {
            return Optional.empty();
        }
        if (!node.has("registry")) {
            return Optional.empty();
        }
        DungeonRegistry registry = MAPPER.treeToValue(node.get("registry"), DungeonRegistry.class);
        return Optional.of(new CachedState(node.path("input_digest").asText(), registry));
    }

    public void save(Path stateFile, String inputDigest, DungeonRegistry registry,
                     boolean success) throws Exception {
        if (!success) {
            return;
        }
        Files.createDirectories(stateFile.getParent());
        Path tmp = stateFile.resolveSibling(stateFile.getFileName() + ".tmp");
        var root = MAPPER.createObjectNode();
        root.put("format_version", AuditState.FORMAT_VERSION);
        root.put("input_digest", inputDigest);
        root.put("registry_digest", registry.digest());
        root.put("success", true);
        root.set("registry", MAPPER.valueToTree(registry));
        Files.writeString(tmp, MAPPER.writeValueAsString(root));
        Files.move(tmp, stateFile, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
    }
}
