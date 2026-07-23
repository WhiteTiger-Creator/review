package dev.terminus.trivia.cli;

import dev.terminus.trivia.audit.AuditEngine;
import dev.terminus.trivia.audit.AuditResult;
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

@CommandLine.Command(name = "audit", description = "Audit dungeon manifests and dataset references",
        mixinStandardHelpOptions = true, exitCodeOnUsageHelp = 0, exitCodeOnVersionHelp = 0)
public class AuditCommand implements Callable<Integer> {
    @CommandLine.Option(names = "--root", description = "Application root")
    Path root;
    @CommandLine.Option(names = "--config", description = "Dungeon TOML config")
    Path config;
    @CommandLine.Option(names = "--dataset", description = "Parquet dataset path")
    Path dataset;
    @CommandLine.Option(names = "--contracts", description = "JSON Schema directory")
    Path contracts;
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
                    new ConfigLoader.CliOverrides(root, config, dataset, contracts, output, state, null),
                    new ConfigLoader.LoadOptions(false));
            AuditResult result = new AuditEngine(verbose).run(cfg);
            ReportWriter.writeAuditReport(cfg.output(), result, cfg.dataset());
            if (!result.success()) {
                return ExitCodes.CONTENT;
            }
            return ExitCodes.SUCCESS;
        } catch (IllegalStateException e) {
            System.err.println(e.getMessage());
            return ExitCodes.OPERATIONAL;
        } catch (Exception e) {
            System.err.println("audit failed: " + e.getMessage());
            return ExitCodes.OPERATIONAL;
        }
    }
}
