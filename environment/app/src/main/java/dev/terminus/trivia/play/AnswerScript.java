package dev.terminus.trivia.play;

import dev.terminus.trivia.manifest.TomlJsonLoader;
import com.fasterxml.jackson.databind.JsonNode;

import java.nio.file.Path;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

public final class AnswerScript {
    private final Map<String, String> answers = new HashMap<>();

    public static AnswerScript load(Path path) throws Exception {
        AnswerScript script = new AnswerScript();
        JsonNode root = TomlJsonLoader.load(path);
        JsonNode table = root.has("answers") ? root.get("answers") : root;
        Iterator<Map.Entry<String, JsonNode>> fields = table.fields();
        while (fields.hasNext()) {
            Map.Entry<String, JsonNode> e = fields.next();
            script.answers.put(e.getKey(), e.getValue().asText());
        }
        return script;
    }

    public String answerFor(String encounterId) {
        return answers.get(encounterId);
    }
}
