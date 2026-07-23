package dev.terminus.trivia.audit;

import dev.terminus.trivia.util.CanonicalJson;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class ReportWriter {
    private ReportWriter() {}

    public static void writeAuditReport(Path outputDir, AuditResult result) throws Exception {
        Files.createDirectories(outputDir);
        Map<String, Object> report = new HashMap<>();
        report.put("input_digest", result.inputDigest());
        report.put("registry_digest", result.registryDigest());
        report.put("issue_count", result.issues().size());
        report.put("success", result.success());
        report.put("issues", result.issues().stream().map(i -> Map.of(
                "artifact", java.nio.file.Path.of(i.artifact()).toAbsolutePath().toString(),
                "pointer", i.pointer(),
                "code", i.code(),
                "message", i.message()
        )).toList());
        report.put("artifacts", result.issues().stream().map(AuditIssue::artifact).distinct().toList());
        Path out = outputDir.resolve("audit-report.json");
        Files.writeString(out, CanonicalJson.write(report));
    }

    public static void writePlaythroughReport(Path outputDir, Map<String, Object> body) throws Exception {
        Files.createDirectories(outputDir);
        Path out = outputDir.resolve("playthrough.json");
        Files.writeString(out, CanonicalJson.write(body));
    }
}
