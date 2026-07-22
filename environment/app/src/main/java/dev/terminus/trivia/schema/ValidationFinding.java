package dev.terminus.trivia.schema;

public record ValidationFinding(
        String artifact,
        String pointer,
        String code,
        String message
) {}
