package dev.terminus.trivia.manifest;

import com.fasterxml.jackson.databind.JsonNode;

import java.nio.file.Path;

public record LoadedArtifact(
        Path absolutePath,
        Path relativePath,
        ArtifactKind kind,
        JsonNode document
) {}
