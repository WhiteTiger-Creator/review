package dev.terminus.trivia.config;

public enum ConfigSource {
    DEFAULT("default"),
    TOML("toml"),
    ENV("env"),
    CLI("cli");

    private final String label;

    ConfigSource(String label) {
        this.label = label;
    }

    public String label() {
        return label;
    }
}
