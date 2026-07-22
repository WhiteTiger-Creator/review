package dev.terminus.trivia;

import dev.terminus.trivia.config.ConfigLoader;
import dev.terminus.trivia.config.DungeonConfig;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Files;
import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.*;

class ConfigLoaderTest {
    @Test
    void cliRootOverridesDefault(@TempDir Path temp) throws Exception {
        Path root = temp.resolve("dungeon-root");
        Files.createDirectories(root);
        DungeonConfig cfg = ConfigLoader.load(
                new ConfigLoader.CliOverrides(root, null, null, null, null, null, null),
                new ConfigLoader.LoadOptions(false));
        assertEquals(root.toAbsolutePath().normalize(), cfg.root().toAbsolutePath().normalize());
    }

    @Test
    void auditAndPlaythroughDefaultStatePathsDiffer() throws Exception {
        DungeonConfig audit = ConfigLoader.load(
                new ConfigLoader.CliOverrides(null, null, null, null, null, null, null),
                new ConfigLoader.LoadOptions(false));
        DungeonConfig play = ConfigLoader.load(
                new ConfigLoader.CliOverrides(null, null, null, null, null, null, null),
                new ConfigLoader.LoadOptions(true));
        assertNotEquals(audit.state(), play.state());
    }
}
