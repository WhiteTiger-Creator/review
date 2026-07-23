package dev.terminus.trivia.manifest;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.tomlj.Toml;
import org.tomlj.TomlParseResult;
import org.tomlj.TomlTable;

import java.nio.file.Path;

public final class TomlJsonLoader {
    private static final ObjectMapper MAPPER = new ObjectMapper();

    private TomlJsonLoader() {}

    public static JsonNode load(Path path) throws Exception {
        TomlParseResult parsed = Toml.parse(path);
        if (parsed.hasErrors()) {
            throw new IllegalArgumentException(parsed.errors().toString());
        }
        String name = path.getFileName().toString().toLowerCase();
        if (name.contains("answer")) {
            return answersDocument(parsed);
        }
        return dungeonConfigDocument(parsed);
    }

    private static JsonNode dungeonConfigDocument(TomlParseResult parsed) {
        ObjectNode root = MAPPER.createObjectNode();
        root.put("version", parsed.getString("version"));
        TomlTable dungeon = parsed.getTable("dungeon");
        if (dungeon != null) {
            ObjectNode table = MAPPER.createObjectNode();
            putString(table, dungeon, "root");
            putString(table, dungeon, "content_dir");
            putString(table, dungeon, "dataset");
            putString(table, dungeon, "contracts");
            putString(table, dungeon, "output");
            putString(table, dungeon, "state");
            putString(table, dungeon, "start_room");
            putString(table, dungeon, "exit_room");
            root.set("dungeon", table);
        }
        return root;
    }

    private static JsonNode answersDocument(TomlParseResult parsed) {
        ObjectNode root = MAPPER.createObjectNode();
        root.put("version", parsed.getString("version"));
        TomlTable answers = parsed.getTable("answers");
        if (answers != null) {
            ObjectNode table = MAPPER.createObjectNode();
            for (String key : answers.keySet()) {
                table.put(key, answers.getString(key));
            }
            root.set("answers", table);
        }
        return root;
    }

    private static void putString(ObjectNode target, TomlTable source, String key) {
        if (source.contains(key)) {
            target.put(key, source.getString(key));
        }
    }
}
