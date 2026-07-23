package dev.terminus.trivia.config;

import dev.terminus.trivia.util.PathUtil;
import org.tomlj.Toml;
import org.tomlj.TomlParseResult;
import org.tomlj.TomlTable;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.EnumMap;
import java.util.Map;

public final class ConfigLoader {
    public record CliOverrides(
            Path root, Path config, Path dataset, Path contracts,
            Path output, Path state, Path answers
    ) {}

    public record LoadOptions(boolean playthrough) {}

    public static DungeonConfig load(CliOverrides cli, LoadOptions options) throws Exception {
        EnumMap<ConfigSource, String> notes = new EnumMap<>(ConfigSource.class);
        Path configPath = cli.config() != null ? cli.config()
                : envPath("TRIVIA_CONFIG").orElse(Paths.get("/app/config/dungeon.toml"));
        notes.put(ConfigSource.DEFAULT, "baseline");

        Path root = Paths.get("/app");
        Path dataset = Paths.get("/data/trivia_qa_sample.parquet");
        Path contracts = Paths.get("/data/contracts");
        Path output = Paths.get("/output");
        Path state = options.playthrough()
                ? Paths.get("/app/.state/playthrough-state.json")
                : Paths.get("/app/.state/audit-state.json");
        String startRoom = "foyer";
        String exitRoom = "vault";
        Path contentDir = root.resolve("bundle");
        Path chambersDir = contentDir.resolve("chambers");
        Path nodesDir = contentDir.resolve("nodes");
        Path weightsDir = contentDir.resolve("weights");

        if (Files.isRegularFile(configPath)) {
            TomlParseResult parsed = Toml.parse(configPath);
            if (parsed.hasErrors()) {
                throw new IllegalArgumentException("Invalid TOML: " + parsed.errors());
            }
            TomlTable table = parsed.getTable("dungeon");
            if (table != null) {
                if (table.contains("root")) {
                    root = PathUtil.resolveFromConfig(configPath, table.getString("root"));
                    notes.put(ConfigSource.TOML, "root");
                }
                if (table.contains("dataset")) {
                    dataset = PathUtil.resolveFromConfig(configPath, table.getString("dataset"));
                }
                if (table.contains("contracts")) {
                    contracts = PathUtil.resolveFromConfig(configPath, table.getString("contracts"));
                }
                if (table.contains("output")) {
                    output = PathUtil.resolveFromConfig(configPath, table.getString("output"));
                }
                if (table.contains("state")) {
                    state = PathUtil.resolveFromConfig(configPath, table.getString("state"));
                }
                if (table.contains("start_room")) {
                    startRoom = table.getString("start_room");
                }
                if (table.contains("exit_room")) {
                    exitRoom = table.getString("exit_room");
                }
                if (table.contains("content_dir")) {
                    contentDir = PathUtil.resolveFromConfig(configPath, table.getString("content_dir"));
                    chambersDir = contentDir.resolve("chambers");
                    nodesDir = contentDir.resolve("nodes");
                    weightsDir = contentDir.resolve("weights");
                }
            }
        }

        if (envPresent("TRIVIA_ROOT")) {
            root = Paths.get(System.getenv("TRIVIA_ROOT"));
            notes.put(ConfigSource.ENV, "TRIVIA_ROOT");
        }
        if (envPresent("TRIVIA_DATASET")) {
            dataset = Paths.get(System.getenv("TRIVIA_DATASET"));
        }
        if (envPresent("TRIVIA_CONTRACTS")) {
            contracts = Paths.get(System.getenv("TRIVIA_CONTRACTS"));
        }
        if (envPresent("TRIVIA_OUTPUT")) {
            output = Paths.get(System.getenv("TRIVIA_OUTPUT"));
        }
        if (envPresent("TRIVIA_STATE")) {
            state = Paths.get(System.getenv("TRIVIA_STATE"));
        }

        if (cli.root() != null) {
            root = cli.root();
            notes.put(ConfigSource.CLI, "root");
        }
        if (cli.output() != null) {
            output = cli.output();
        }
        if (cli.state() != null) {
            state = cli.state();
        }

        if (cli.dataset() != null) {
            dataset = cli.dataset();
        } else if (envPresent("TRIVIA_DATASET")) {
            dataset = Paths.get(System.getenv("TRIVIA_DATASET"));
        } else if (Files.isRegularFile(configPath)) {
            TomlTable table = Toml.parse(configPath).getTable("dungeon");
            if (table != null && table.contains("dataset")) {
                dataset = PathUtil.resolveFromConfig(configPath, table.getString("dataset"));
            }
        }

        if (cli.contracts() != null) {
            contracts = cli.contracts();
        } else if (envPresent("TRIVIA_CONTRACTS")) {
            contracts = Paths.get(System.getenv("TRIVIA_CONTRACTS"));
        } else if (Files.isRegularFile(configPath)) {
            TomlTable table = Toml.parse(configPath).getTable("dungeon");
            if (table != null && table.contains("contracts")) {
                contracts = PathUtil.resolveFromConfig(configPath, table.getString("contracts"));
            }
        }

        return new DungeonConfig(root, configPath, dataset, contracts, output, state,
                startRoom, exitRoom, contentDir, chambersDir, nodesDir, weightsDir, notes);
    }

    private static boolean envPresent(String name) {
        return System.getenv(name) != null;
    }

    private static java.util.Optional<Path> envPath(String name) {
        String v = System.getenv(name);
        return v == null ? java.util.Optional.empty() : java.util.Optional.of(Paths.get(v));
    }
}
