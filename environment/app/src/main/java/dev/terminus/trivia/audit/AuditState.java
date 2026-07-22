package dev.terminus.trivia.audit;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.terminus.trivia.config.DungeonConfig;
import dev.terminus.trivia.registry.DungeonRegistry;
import dev.terminus.trivia.util.Digest;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

public final class AuditState {
    public static final String FORMAT_VERSION = "1";
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private AuditState() {}

    public static String computeInputDigest(DungeonConfig config, List<Path> artifacts,
                                            Path contractsDir, Path dataset) throws Exception {
        StringBuilder sb = new StringBuilder();
        sb.append(FORMAT_VERSION).append('\n');
        sb.append(config.root()).append('\n');
        sb.append(config.startRoom()).append('\n');
        sb.append(config.exitRoom()).append('\n');
        for (Path artifact : artifacts) {
            if (Files.isRegularFile(artifact)) {
                sb.append(artifact.toAbsolutePath()).append('|')
                        .append(Files.size(artifact)).append('|')
                        .append(Files.getLastModifiedTime(artifact).toMillis()).append('\n');
            }
        }
        return Digest.sha256Hex(sb.toString());
    }

    public static JsonNode read(Path stateFile) throws Exception {
        if (!Files.isRegularFile(stateFile)) {
            return null;
        }
        return MAPPER.readTree(stateFile.toFile());
    }

    public static void write(Path stateFile, String inputDigest, DungeonRegistry registry,
                             boolean success) throws Exception {
        var root = MAPPER.createObjectNode();
        root.put("format_version", FORMAT_VERSION);
        root.put("input_digest", inputDigest);
        root.put("registry_digest", registry.digest());
        root.put("success", success);
        root.set("registry", MAPPER.valueToTree(registry));
        Files.createDirectories(stateFile.getParent());
        Files.writeString(stateFile, MAPPER.writeValueAsString(root));
    }
}
