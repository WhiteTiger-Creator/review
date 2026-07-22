package dev.terminus.trivia.registry;

import dev.terminus.trivia.audit.AuditIssue;
import dev.terminus.trivia.config.DungeonConfig;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public final class GraphValidator {
    private GraphValidator() {}

    public static List<AuditIssue> validate(DungeonConfig config, DungeonRegistry registry) {
        List<AuditIssue> issues = new ArrayList<>();
        Map<String, RoomNode> rooms = registry.rooms();
        Map<String, String> aliases = registry.aliases();
        Set<String> encounterIds = registry.encounters().keySet();

        for (RoomNode room : rooms.values()) {
            String rel = registry.roomArtifacts().getOrDefault(room.id(), "bundle/chambers/" + room.id() + ".yaml");
            Set<String> seen = new HashSet<>();
            for (String encId : room.encounters()) {
                if (!seen.add(encId)) {
                    issues.add(new AuditIssue(rel, "/encounters", "graph.duplicate-encounter",
                            "Duplicate encounter " + encId));
                }
                if (!encounterIds.contains(encId)) {
                    issues.add(new AuditIssue(rel, "/encounters", "graph.missing-encounter",
                            "Unknown encounter " + encId));
                }
            }
            for (Map.Entry<String, String> exit : room.exits().entrySet()) {
                String target = resolveAlias(exit.getValue(), aliases);
                if (!rooms.containsKey(target) && !target.equals(registry.exitRoom())) {
                    issues.add(new AuditIssue(rel, "/exits/" + exit.getKey(), "graph.unknown-room",
                            "Unknown room " + exit.getValue()));
                }
            }
        }

        for (EncounterNode enc : registry.encounters().values()) {
            String rel = registry.encounterArtifacts().getOrDefault(enc.id(),
                    "bundle/nodes/" + enc.id() + ".yaml");
            String room = resolveAlias(enc.roomId(), aliases);
            if (!rooms.containsKey(room)) {
                issues.add(new AuditIssue(rel, "/room", "graph.unknown-room",
                        "Unknown room " + enc.roomId()));
            }
        }

        String cycle = findCycle(registry);
        if (cycle != null) {
            String rel = registry.roomArtifacts().getOrDefault(cycle, "bundle/chambers/" + cycle + ".yaml");
            issues.add(new AuditIssue(rel, "/exits", "graph.cycle", "Cycle detected"));
        }
        String deadEnd = findDeadEnd(registry);
        if (deadEnd != null) {
            String rel = registry.roomArtifacts().getOrDefault(deadEnd, "bundle/chambers/" + deadEnd + ".yaml");
            issues.add(new AuditIssue(rel, "/exits", "graph.dead-end", "Dead end before exit"));
        }

        issues.sort(Comparator.comparing(AuditIssue::artifact)
                .thenComparing(AuditIssue::pointer)
                .thenComparing(AuditIssue::code));
        return issues;
    }

    private static String resolveAlias(String roomId, Map<String, String> aliases) {
        return aliases.getOrDefault(roomId, roomId);
    }

    private static String findCycle(DungeonRegistry registry) {
        String start = resolveAlias(registry.startRoom(), registry.aliases());
        if (start.equals(registry.exitRoom())) {
            return null;
        }
        Set<String> visited = new HashSet<>();
        String current = start;
        while (!current.equals(registry.exitRoom())) {
            if (!visited.add(current)) {
                return current;
            }
            RoomNode room = registry.rooms().get(current);
            if (room == null) {
                return null;
            }
            String next = room.exits().get("default");
            if (next == null || next.isBlank()) {
                return null;
            }
            current = resolveAlias(next, registry.aliases());
        }
        return null;
    }

    private static String findDeadEnd(DungeonRegistry registry) {
        String start = resolveAlias(registry.startRoom(), registry.aliases());
        Set<String> visited = new HashSet<>();
        String current = start;
        while (true) {
            if (current.equals(registry.exitRoom())) {
                return null;
            }
            if (visited.contains(current)) {
                return null;
            }
            visited.add(current);
            RoomNode room = registry.rooms().get(current);
            if (room == null) {
                String aliasResolved = resolveAlias(current, registry.aliases());
                if (!aliasResolved.equals(current)) {
                    current = aliasResolved;
                    continue;
                }
                return current;
            }
            String next = room.exits().get("default");
            if (next == null || next.isBlank()) {
                return current;
            }
            String resolved = resolveAlias(next, registry.aliases());
            if (!registry.rooms().containsKey(resolved) && !resolved.equals(registry.exitRoom())) {
                return current;
            }
            current = resolved;
        }
    }
}
