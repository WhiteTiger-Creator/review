package dev.terminus.trivia.play;

import dev.terminus.trivia.audit.StateStore;
import dev.terminus.trivia.config.DungeonConfig;
import dev.terminus.trivia.dataset.DuckDbCatalog;
import dev.terminus.trivia.manifest.ArtifactScanner;
import dev.terminus.trivia.manifest.LoadedArtifact;
import dev.terminus.trivia.registry.DungeonRegistry;
import dev.terminus.trivia.registry.EncounterNode;
import dev.terminus.trivia.registry.RegistryBuilder;
import dev.terminus.trivia.registry.RoomNode;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;

public final class PlaythroughEngine {
    private final boolean verbose;

    public PlaythroughEngine(boolean verbose) {
        this.verbose = verbose;
    }

    public PlaythroughResult run(DungeonConfig config, AnswerScript answers) throws Exception {
        List<java.nio.file.Path> paths = ArtifactScanner.discoverContentPaths(config);
        List<LoadedArtifact> artifacts = new ArrayList<>();
        for (java.nio.file.Path path : paths) {
            artifacts.add(ArtifactScanner.load(config.root(), path));
        }

        DungeonRegistry registry;
        Optional<StateStore.CachedState> cached = new StateStore().load(config.state());
        if (cached.isPresent()) {
            registry = cached.get().registry();
        } else {
            try (DuckDbCatalog duck = new DuckDbCatalog(config.dataset().toString())) {
                registry = new RegistryBuilder().build(config, artifacts, duck).registry();
            }
        }

        String current = resolveAlias(registry, config.startRoom());
        Set<String> visited = new HashSet<>();
        List<String> route = new ArrayList<>();
        List<String> encounters = new ArrayList<>();
        int score = 0;
        int streak = 0;

        ScoringEngine scoring = new ScoringEngine(registry.scoring());
        while (true) {
            if (!visited.add(current)) {
                return new PlaythroughResult(false, score, route, encounters, registry.digest());
            }
            route.add(current);
            if (current.equals(config.exitRoom())) {
                return new PlaythroughResult(true, score, route, encounters, registry.digest());
            }
            RoomNode room = registry.rooms().get(current);
            if (room == null) {
                return new PlaythroughResult(false, score, route, encounters, registry.digest());
            }
            for (String encounterId : room.encounters()) {
                EncounterNode encounter = registry.encounters().get(encounterId);
                if (encounter == null) {
                    continue;
                }
                encounters.add(encounterId);
                String given = answers.answerFor(encounterId);
                boolean correct = isCorrect(given, encounter.question().answerValue(),
                        encounter.question().answerAliases());
                if (correct) {
                    streak++;
                } else {
                    streak = 0;
                }
                score += scoring.scoreEncounter(correct, encounter.question().difficulty(), streak);
            }
            String next = room.exits().get("default");
            if (next == null || next.isBlank()) {
                return new PlaythroughResult(false, score, route, encounters, registry.digest());
            }
            current = next;
        }
    }

    private String resolveAlias(DungeonRegistry registry, String roomId) {
        return registry.aliases().getOrDefault(roomId, roomId);
    }

    private boolean isCorrect(String given, String expected, List<String> aliases) {
        if (given == null) {
            return false;
        }
        String norm = given.trim().toLowerCase(Locale.getDefault());
        if (norm.equals(expected.trim().toLowerCase(Locale.getDefault()))) {
            return true;
        }
        for (String alias : aliases) {
            if (norm.equals(alias.trim().toLowerCase(Locale.getDefault()))) {
                return true;
            }
        }
        return false;
    }
}
