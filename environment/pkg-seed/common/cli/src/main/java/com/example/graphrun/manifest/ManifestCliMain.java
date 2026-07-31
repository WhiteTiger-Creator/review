package com.example.graphrun.manifest;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

public final class ManifestCliMain {

    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("usage: cli <output-dir> <name=digest> [...]");
            System.exit(1);
        }
        Path outputDir = Path.of(args[0]);
        Map<String, String> artifacts = new HashMap<>();
        for (int i = 1; i < args.length; i++) {
            String[] parts = args[i].split("=", 2);
            if (parts.length == 2) {
                artifacts.put(parts[0], parts[1]);
            }
        }
        if (Files.isDirectory(outputDir)) {
            try (var stream = Files.list(outputDir)) {
                stream.filter(Files::isRegularFile)
                        .forEach(p -> artifacts.putIfAbsent(p.getFileName().toString(), "pending"));
            }
        }
        new ManifestWriter().write(outputDir, artifacts);
        System.out.println("wrote manifest to " + outputDir.resolve("manifest.json"));
    }
}
