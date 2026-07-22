package dev.terminus.trivia.config;

import java.nio.file.Path;
import java.util.EnumMap;
import java.util.Map;

public record DungeonConfig(
        Path root,
        Path configFile,
        Path dataset,
        Path contracts,
        Path output,
        Path state,
        String startRoom,
        String exitRoom,
        Path contentDir,
        Path roomsDir,
        Path encountersDir,
        Path scoringDir,
        Map<ConfigSource, String> sourceNotes
) {
    public DungeonConfig {
        sourceNotes = Map.copyOf(sourceNotes);
    }

    public static DungeonConfig withSources(DungeonConfig base, Map<ConfigSource, String> notes) {
        return new DungeonConfig(base.root, base.configFile, base.dataset, base.contracts,
                base.output, base.state, base.startRoom, base.exitRoom, base.contentDir,
                base.roomsDir, base.encountersDir, base.scoringDir, notes);
    }
}
