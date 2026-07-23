package dev.terminus.trivia.registry;

import java.util.List;
import java.util.Map;

public record RoomNode(
        String id,
        String title,
        List<String> encounters,
        Map<String, String> exits
) {}
