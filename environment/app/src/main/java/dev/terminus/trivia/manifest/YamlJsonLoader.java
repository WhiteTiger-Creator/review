package dev.terminus.trivia.manifest;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.snakeyaml.engine.v2.api.Load;
import org.snakeyaml.engine.v2.api.LoadSettings;

import java.nio.file.Files;
import java.nio.file.Path;

public final class YamlJsonLoader {
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final Load LOADER = new Load(LoadSettings.builder().build());

    private YamlJsonLoader() {}

    @SuppressWarnings("unchecked")
    public static JsonNode load(Path path) throws Exception {
        String text = Files.readString(path);
        Object raw = LOADER.loadFromString(text);
        return MAPPER.valueToTree(raw);
    }
}
