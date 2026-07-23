package dev.terminus.trivia.registry;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.List;
import java.util.Map;

public record DungeonRegistry(
        String digest,
        Map<String, RoomNode> rooms,
        Map<String, EncounterNode> encounters,
        Map<String, String> aliases,
        JsonNode scoring,
        String startRoom,
        String exitRoom
) {}
