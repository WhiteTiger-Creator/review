package dev.terminus.trivia;

import dev.terminus.trivia.manifest.YamlJsonLoader;
import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SmokeAuditTest {
    @Test
    void yamlLoaderReadsPlainScalars(@TempDir Path temp) throws Exception {
        Path yaml = temp.resolve("sample.yaml");
        Files.writeString(yaml, """
                version: "1"
                id: foyer
                title: Entry
                flag: yes
                """);
        JsonNode node = YamlJsonLoader.load(yaml);
        assertEquals("foyer", node.get("id").asText());
        assertTrue(node.get("flag").isBoolean() || node.get("flag").isTextual());
    }

    @Test
    void digestIsDeterministic() {
        String a = dev.terminus.trivia.util.Digest.sha256Hex("test");
        String b = dev.terminus.trivia.util.Digest.sha256Hex("test");
        assertEquals(a, b);
        assertEquals(64, a.length());
    }
}
