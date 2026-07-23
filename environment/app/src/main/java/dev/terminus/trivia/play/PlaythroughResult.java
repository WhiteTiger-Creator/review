package dev.terminus.trivia.play;

import java.util.List;

public record PlaythroughResult(
        boolean reachedExit,
        int totalScore,
        List<String> visitedRooms,
        List<String> resolvedEncounters,
        String registryDigest
) {}
