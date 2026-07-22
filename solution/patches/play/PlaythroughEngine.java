package dev.terminus.trivia.play;

import com.fasterxml.jackson.databind.JsonNode;
import dev.terminus.trivia.audit.StateStore;
import dev.terminus.trivia.config.DungeonConfig;
import dev.terminus.trivia.registry.DungeonRegistry;
import dev.terminus.trivia.registry.EncounterNode;
import dev.terminus.trivia.registry.RegistryDigests;
import dev.terminus.trivia.registry.RoomNode;
import dev.terminus.trivia.util.UnicodeNormalizer;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public final class PlaythroughEngine {
    private final boolean verbose;

    public PlaythroughEngine(boolean verbose) {
        this.verbose = verbose;
    }

    public PlaythroughResult run(DungeonConfig config, AnswerScript answers) throws Exception {
        StateStore store = new StateStore();
        DungeonRegistry registry = store.load(config.state())
                .orElseThrow(() -> new IllegalStateException("Audited registry state not found"))
                .registry();

        String current = resolveAlias(registry, config.startRoom());
        Set<String> visited = new HashSet<>();
        List<String> route = new ArrayList<>();
        List<String> encounters = new ArrayList<>();
        int score = 0;
        int streak = 0;

        ScoringEngine scoring = new ScoringEngine(registry.scoring());
        while (true) {
            if (!visited.add(current)) {
                return new PlaythroughResult(false, score, route, encounters, RegistryDigests.compute(registry));
            }
            route.add(current);
            if (current.equals(resolveAlias(registry, config.exitRoom()))) {
                return new PlaythroughResult(true, score, route, encounters, RegistryDigests.compute(registry));
            }
            RoomNode room = registry.rooms().get(current);
            if (room == null) {
                return new PlaythroughResult(false, score, route, encounters, RegistryDigests.compute(registry));
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
                return new PlaythroughResult(false, score, route, encounters, RegistryDigests.compute(registry));
            }
            current = resolveAlias(registry, next);
        }
    }

    private String resolveAlias(DungeonRegistry registry, String roomId) {
        return registry.aliases().getOrDefault(roomId, roomId);
    }

    private boolean isCorrect(String given, String expected, List<String> aliases) {
        String normGiven = UnicodeNormalizer.normalizeAnswer(given);
        if (normGiven.equals(UnicodeNormalizer.normalizeAnswer(expected))) {
            return true;
        }
        if (aliases != null) {
            for (String alias : aliases) {
                if (normGiven.equals(UnicodeNormalizer.normalizeAnswer(alias))) {
                    return true;
                }
            }
        }
        return false;
    }
}
