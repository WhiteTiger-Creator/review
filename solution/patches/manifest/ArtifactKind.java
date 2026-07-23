package dev.terminus.trivia.manifest;

public enum ArtifactKind {
    ROOM("room", "room.schema.json"),
    ALIASES("aliases", "aliases.schema.json"),
    ENCOUNTER("encounter", "encounter.schema.json"),
    SCORING("scoring", "scoring.schema.json"),
    DUNGEON_CONFIG("dungeon-config", "dungeon-config.schema.json"),
    ANSWERS("answers", "answers.schema.json");

    private final String typeName;
    private final String schemaFile;

    ArtifactKind(String typeName, String schemaFile) {
        this.typeName = typeName;
        this.schemaFile = schemaFile;
    }

    public String typeName() {
        return typeName;
    }

    public String schemaFile() {
        return schemaFile;
    }

    public static ArtifactKind fromPath(java.nio.file.Path path) {
        String name = path.getFileName().toString().toLowerCase();
        if (name.equals("aliases.yaml") || name.equals("aliases.yml")) {
            return ALIASES;
        }
        if (name.endsWith(".toml")) {
            if (name.contains("answer")) {
                return ANSWERS;
            }
            return DUNGEON_CONFIG;
        }
        String parent = path.getParent() != null ? path.getParent().getFileName().toString() : "";
        return switch (parent) {
            case "nodes", "encounters" -> ENCOUNTER;
            case "weights", "scoring" -> SCORING;
            default -> ROOM;
        };
    }
}
