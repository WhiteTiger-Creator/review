package dev.terminus.trivia.cli;

import dev.terminus.trivia.audit.ReportWriter;
import dev.terminus.trivia.config.ConfigLoader;
import dev.terminus.trivia.config.DungeonConfig;
import dev.terminus.trivia.play.AnswerScript;
import dev.terminus.trivia.play.PlaythroughEngine;
import dev.terminus.trivia.play.PlaythroughResult;
import picocli.CommandLine;

import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.Callable;

@CommandLine.Command(name = "playthrough", description = "Run deterministic verification playthrough")
public class PlaythroughCommand implements Callable<Integer> {
    @CommandLine.Option(names = "--root", description = "Application root")
    Path root;
    @CommandLine.Option(names = "--config", description = "Dungeon TOML config")
    Path config;
    @CommandLine.Option(names = "--dataset", description = "Parquet dataset path")
    Path dataset;
    @CommandLine.Option(names = "--contracts", description = "JSON Schema directory")
    Path contracts;
    @CommandLine.Option(names = "--answers", description = "Answer script TOML")
    Path answers;
    @CommandLine.Option(names = "--output", description = "Output directory")
    Path output;
    @CommandLine.Option(names = "--state", description = "Audit state file")
    Path state;
    @CommandLine.Option(names = "--verbose", description = "Verbose diagnostics")
    boolean verbose;

    @Override
    public Integer call() {
        try {
            DungeonConfig cfg = ConfigLoader.load(
                    new ConfigLoader.CliOverrides(root, config, dataset, contracts, output, state, answers),
                    new ConfigLoader.LoadOptions(true));
            if (answers == null) {
                throw new IllegalStateException("Answers file required");
            }
            PlaythroughResult result = new PlaythroughEngine(verbose)
                    .run(cfg, AnswerScript.load(answers));
            Map<String, Object> body = new HashMap<>();
            body.put("reached_exit", result.reachedExit());
            body.put("total_score", result.totalScore());
            body.put("visited_rooms", result.visitedRooms());
            body.put("encounters", result.resolvedEncounters());
            body.put("registry_digest", result.registryDigest());
            ReportWriter.writePlaythroughReport(cfg.output(), body);
            return result.reachedExit() ? ExitCodes.SUCCESS : ExitCodes.CONTENT;
        } catch (IllegalStateException e) {
            System.err.println(e.getMessage());
            return ExitCodes.OPERATIONAL;
        } catch (Exception e) {
            System.err.println("playthrough failed: " + e.getMessage());
            return ExitCodes.OPERATIONAL;
        }
    }
}
