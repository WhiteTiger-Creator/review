package dev.terminus.trivia.registry;

import com.fasterxml.jackson.databind.ObjectMapper;
import dev.terminus.trivia.util.Digest;

import java.util.ArrayList;
import java.util.Map;
import java.util.TreeMap;

public final class RegistryDigests {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private RegistryDigests() {}

    public static String compute(Map<String, ?> rooms, Map<String, ?> encounters) throws Exception {
        TreeMap<String, Object> payload = new TreeMap<>();
        payload.put("encounters", new ArrayList<>(encounters.keySet()));
        payload.put("rooms", new ArrayList<>(rooms.keySet()));
        return Digest.sha256Hex(MAPPER.writeValueAsString(payload));
    }

    public static String compute(DungeonRegistry registry) throws Exception {
        return compute(registry.rooms(), registry.encounters());
    }
}
