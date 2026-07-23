package dev.terminus.trivia.registry;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.Map;

public record DungeonRegistry(
        String digest,
        Map<String, RoomNode> rooms,
        Map<String, EncounterNode> encounters,
        Map<String, String> aliases,
        JsonNode scoring,
        String startRoom,
        String exitRoom,
        Map<String, String> roomArtifacts,
        Map<String, String> encounterArtifacts
) {
    public DungeonRegistry {
        roomArtifacts = roomArtifacts == null ? Map.of() : Map.copyOf(roomArtifacts);
        encounterArtifacts = encounterArtifacts == null ? Map.of() : Map.copyOf(encounterArtifacts);
    }
}
