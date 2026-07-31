package com.example.graphrun.manifest;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

public final class ManifestWriter {

    private final ObjectMapper mapper = new ObjectMapper();

    public void write(Path outputDir, Map<String, String> artifacts) {
        try {
            Files.createDirectories(outputDir);
            ObjectNode manifest = mapper.createObjectNode();
            Map<String, String> entries = new HashMap<>(artifacts);
            for (Map.Entry<String, String> entry : entries.entrySet()) {
                manifest.put(entry.getKey(), entry.getValue());
            }
            Files.writeString(outputDir.resolve("manifest.json"), mapper.writeValueAsString(manifest));
            for (Map.Entry<String, String> entry : entries.entrySet()) {
                Path sidecar = outputDir.resolve(entry.getKey() + ".sha256");
                Files.writeString(sidecar, entry.getValue());
            }
        } catch (Exception e) {
            throw new IllegalStateException("manifest write failed", e);
        }
    }
}
