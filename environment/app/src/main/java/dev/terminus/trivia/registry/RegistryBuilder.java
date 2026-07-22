package dev.terminus.trivia.registry;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import dev.terminus.trivia.audit.AuditIssue;
import dev.terminus.trivia.config.DungeonConfig;
import dev.terminus.trivia.dataset.DuckDbCatalog;
import dev.terminus.trivia.dataset.LegacyLocatorResolver;
import dev.terminus.trivia.dataset.QuestionLocator;
import dev.terminus.trivia.dataset.QuestionRecord;
import dev.terminus.trivia.manifest.ArtifactKind;
import dev.terminus.trivia.manifest.LoadedArtifact;
import dev.terminus.trivia.util.Digest;
import dev.terminus.trivia.util.PathUtil;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Optional;

public final class RegistryBuilder {
    private final ObjectMapper mapper = new ObjectMapper();

    public record BuildResult(DungeonRegistry registry, List<AuditIssue> issues) {}

    public BuildResult build(DungeonConfig config, List<LoadedArtifact> artifacts,
                             DuckDbCatalog catalog) throws Exception {
        List<AuditIssue> issues = new ArrayList<>();
        Map<String, RoomNode> rooms = new HashMap<>();
        Map<String, EncounterNode> encounters = new HashMap<>();
        Map<String, String> aliases = new HashMap<>();
        JsonNode scoring = mapper.createObjectNode();
        LegacyLocatorResolver legacy = new LegacyLocatorResolver(catalog);

        for (LoadedArtifact artifact : artifacts) {
            String rel = PathUtil.toPosixRelative(config.root(), artifact.absolutePath());
            switch (artifact.kind()) {
                case ALIASES, ROOM -> {
                    if (artifact.absolutePath().getFileName().toString().equals("aliases.yaml")
                            || artifact.kind() == ArtifactKind.ALIASES) {
                        Iterator<Map.Entry<String, JsonNode>> fields = artifact.document().fields();
                        while (fields.hasNext()) {
                            Map.Entry<String, JsonNode> e = fields.next();
                            aliases.put(e.getKey(), e.getValue().asText());
                        }
                    } else if (artifact.kind() == ArtifactKind.ROOM) {
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
                    }
                }
                case ENCOUNTER -> {
                    JsonNode doc = artifact.document();
                    String id = doc.get("id").asText();
                    String roomId = doc.get("room").asText();
                    QuestionLocator locator = QuestionLocator.fromJson(doc.get("trivia"));
                    Optional<QuestionRecord> record = resolve(locator, legacy, rel, issues);
                    record.ifPresent(q -> encounters.put(id, new EncounterNode(id, roomId,
                            doc.path("title").asText(), q)));
                }
                case SCORING -> scoring = artifact.document();
                default -> {}
            }
        }

        String digest = Digest.sha256Hex(mapper.writeValueAsString(
                Map.of("rooms", rooms.keySet(), "encounters", encounters.keySet())));
        DungeonRegistry registry = new DungeonRegistry(digest, rooms, encounters, aliases,
                scoring, config.startRoom(), config.exitRoom());
        return new BuildResult(registry, issues);
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
            }
            return legacy.catalog().lookupById(id);
        }
        LegacyLocatorResolver.ResolveResult result = legacy.resolve(locator, artifactPath);
        issues.addAll(result.issues());
        return result.record();
    }
}
