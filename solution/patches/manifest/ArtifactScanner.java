package dev.terminus.trivia.manifest;

import com.fasterxml.jackson.databind.JsonNode;
import dev.terminus.trivia.config.DungeonConfig;
import dev.terminus.trivia.util.PathUtil;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Stream;

public final class ArtifactScanner {
    private ArtifactScanner() {}

    public static List<Path> discoverContentPaths(DungeonConfig config) throws IOException {
        List<Path> paths = new ArrayList<>();
        collectYaml(config.roomsDir(), paths);
        collectYaml(config.encountersDir(), paths);
        collectYaml(config.scoringDir(), paths);
        if (Files.isRegularFile(config.configFile())) {
            paths.add(config.configFile());
        }
        paths.sort(Comparator.comparing(p -> PathUtil.toPosixRelative(config.root(), p)));
        return paths;
    }

    private static void collectYaml(Path dir, List<Path> out) throws IOException {
        if (!Files.isDirectory(dir)) {
            return;
        }
        try (Stream<Path> stream = Files.walk(dir)) {
            stream.filter(Files::isRegularFile)
                    .filter(p -> {
                        String n = p.getFileName().toString().toLowerCase();
                        return n.endsWith(".yaml") || n.endsWith(".yml") || n.endsWith(".toml");
                    })
                    .forEach(out::add);
        }
    }

    public static LoadedArtifact load(Path root, Path file) throws Exception {
        ArtifactKind kind = ArtifactKind.fromPath(file);
        JsonNode doc;
        String name = file.getFileName().toString().toLowerCase();
        if (name.endsWith(".toml")) {
            doc = TomlJsonLoader.load(file);
        } else {
            doc = YamlJsonLoader.load(file);
        }
        return new LoadedArtifact(file, root.relativize(file.normalize()), kind, doc);
    }
}
