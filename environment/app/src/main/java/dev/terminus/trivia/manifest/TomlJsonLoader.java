package dev.terminus.trivia.manifest;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.tomlj.Toml;
import org.tomlj.TomlParseResult;
import org.tomlj.TomlTable;

import java.nio.file.Path;
import java.util.Map;

public final class TomlJsonLoader {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private TomlJsonLoader() {}

    public static JsonNode load(Path path) throws Exception {
        TomlParseResult parsed = Toml.parse(path);
        if (parsed.hasErrors()) {
            throw new IllegalArgumentException(parsed.errors().toString());
        }
        Map<String, Object> map = parsed.toMap();
        return MAPPER.valueToTree(map);
    }
}
