package dev.terminus.trivia.registry;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import dev.terminus.trivia.audit.AuditIssue;
import dev.terminus.trivia.config.DungeonConfig;
import dev.terminus.trivia.dataset.DuckDbCatalog;
import dev.terminus.trivia.dataset.LegacyLocatorResolver;
import dev.terminus.trivia.dataset.QuestionLocator;
import dev.terminus.trivia.dataset.QuestionRecord;
import dev.terminus.trivia.manifest.ArtifactKind;
import dev.terminus.trivia.manifest.LoadedArtifact;
import dev.terminus.trivia.manifest.YamlJsonLoader;
import dev.terminus.trivia.util.PathUtil;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.TreeMap;

public final class RegistryBuilder {
    private final ObjectMapper mapper = new ObjectMapper();

    public record BuildResult(DungeonRegistry registry, List<AuditIssue> issues) {}

    public BuildResult build(DungeonConfig config, List<LoadedArtifact> artifacts,
                             DuckDbCatalog catalog) throws Exception {
        List<AuditIssue> issues = new ArrayList<>();
        Map<String, RoomNode> rooms = new TreeMap<>();
        Map<String, EncounterNode> encounters = new TreeMap<>();
        Map<String, String> aliases = new TreeMap<>();
        Map<String, String> roomArtifacts = new TreeMap<>();
        Map<String, String> encounterArtifacts = new TreeMap<>();
        ObjectNode scoring = mapper.createObjectNode();
        LegacyLocatorResolver legacy = new LegacyLocatorResolver(catalog);

        for (LoadedArtifact artifact : artifacts) {
            String rel = PathUtil.toPosixRelative(config.root(), artifact.absolutePath());
            switch (artifact.kind()) {
                case ALIASES -> loadAliasDocument(artifact.document(), aliases);
                case ROOM -> {
                    JsonNode doc = artifact.document();
                    String id = doc.get("id").asText();
                    List<String> encIds = new ArrayList<>();
                    if (doc.has("encounters")) {
                        doc.get("encounters").forEach(n -> encIds.add(n.asText()));
                    }
                    Map<String, String> exits = new HashMap<>();
                    if (doc.has("exits")) {
                        doc.get("exits").fields().forEachRemaining(e ->
                                exits.put(e.getKey(), e.getValue().asText()));
                    }
                    rooms.put(id, new RoomNode(id, doc.path("title").asText(), encIds, exits));
                    roomArtifacts.put(id, rel);
                }
                case ENCOUNTER -> {
                    JsonNode doc = artifact.document();
                    String id = doc.get("id").asText();
                    String roomId = doc.get("room").asText();
                    QuestionLocator locator = QuestionLocator.fromJson(doc.get("trivia"));
                    Optional<QuestionRecord> record = resolve(locator, legacy, rel, issues);
                    record.ifPresent(q -> {
                        encounters.put(id, new EncounterNode(id, roomId, doc.path("title").asText(), q));
                        encounterArtifacts.put(id, rel);
                    });
                }
                case SCORING -> mergeScoring(scoring, artifact.document());
                default -> {}
            }
        }

        Path aliasesFile = config.roomsDir().resolve("aliases.yaml");
        if (Files.isRegularFile(aliasesFile)) {
            loadAliasesFile(aliasesFile, aliases);
        }

        String digest = RegistryDigests.compute(rooms, encounters);
        DungeonRegistry registry = new DungeonRegistry(digest, rooms, encounters, aliases,
                scoring, config.startRoom(), config.exitRoom(), roomArtifacts, encounterArtifacts);
        return new BuildResult(registry, issues);
    }

    private static void loadAliasDocument(JsonNode document, Map<String, String> aliases) {
        Iterator<Map.Entry<String, JsonNode>> fields = document.fields();
        while (fields.hasNext()) {
            Map.Entry<String, JsonNode> entry = fields.next();
            aliases.put(entry.getKey(), entry.getValue().asText());
        }
    }

    private static void loadAliasesFile(Path aliasesFile, Map<String, String> aliases) throws Exception {
        for (String line : Files.readAllLines(aliasesFile)) {
            String trimmed = line.trim();
            if (trimmed.isEmpty() || trimmed.startsWith("#")) {
                continue;
            }
            int colon = trimmed.indexOf(':');
            if (colon < 0) {
                continue;
            }
            String key = trimmed.substring(0, colon).trim();
            if (key.startsWith("\"") && key.endsWith("\"")) {
                key = key.substring(1, key.length() - 1);
            }
            String value = trimmed.substring(colon + 1).trim();
            aliases.put(key, value);
        }
    }

    private void mergeScoring(ObjectNode target, JsonNode add) {
        add.fields().forEachRemaining(entry -> {
            if ("version".equals(entry.getKey())) {
                return;
            }
            JsonNode existing = target.get(entry.getKey());
            if (existing != null && existing.isObject() && entry.getValue().isObject()) {
                ObjectNode merged = (ObjectNode) existing.deepCopy();
                entry.getValue().fields().forEachRemaining(child -> merged.set(child.getKey(), child.getValue()));
                target.set(entry.getKey(), merged);
            } else {
                target.set(entry.getKey(), entry.getValue());
            }
        });
        if (!target.has("version")) {
            target.put("version", "1");
        }
    }

    private Optional<QuestionRecord> resolve(QuestionLocator locator, LegacyLocatorResolver legacy,
                                             String artifactPath, List<AuditIssue> issues) throws Exception {
        if (locator.kind() == QuestionLocator.Kind.STABLE_ID) {
            String id = locator.questionId().orElse("");
            int count = legacy.catalog().countById(id);
            if (count == 0) {
                issues.add(new AuditIssue(artifactPath, "/trivia/question_id", "dataset.missing-id",
                        "No record for id " + id));
                return Optional.empty();
            }
            if (count > 1) {
                issues.add(new AuditIssue(artifactPath, "/trivia/question_id", "dataset.ambiguous-id",
                        "Ambiguous id " + id));
                return Optional.empty();
            }
            return legacy.catalog().lookupById(id);
        }
        LegacyLocatorResolver.ResolveResult result = legacy.resolve(locator, artifactPath);
        issues.addAll(result.issues());
        return result.record();
    }
}
