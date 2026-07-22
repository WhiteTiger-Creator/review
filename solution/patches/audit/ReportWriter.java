package dev.terminus.trivia.audit;

import dev.terminus.trivia.util.CanonicalJson;
import dev.terminus.trivia.util.Digest;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class ReportWriter {
    private ReportWriter() {}

    public static void writeAuditReport(Path outputDir, AuditResult result, Path dataset) throws Exception {
        Files.createDirectories(outputDir);
        List<Map<String, String>> issues = result.issues().stream()
                .sorted(Comparator.comparing(AuditIssue::artifact)
                        .thenComparing(AuditIssue::pointer)
                        .thenComparing(AuditIssue::code))
                .map(i -> Map.of(
                        "artifact", i.artifact(),
                        "pointer", i.pointer(),
                        "code", i.code(),
                        "message", i.message()))
                .toList();
        List<String> artifacts = new ArrayList<>(result.issues().stream()
                .map(AuditIssue::artifact)
                .distinct()
                .sorted()
                .toList());
        if (result.success() && Files.isRegularFile(dataset)) {
            artifacts.add(Digest.sha256Hex(Files.readAllBytes(dataset)));
            artifacts.sort(String::compareTo);
        }
        Map<String, Object> report = new HashMap<>();
        report.put("artifacts", artifacts);
        report.put("input_digest", result.inputDigest());
        report.put("issue_count", result.issues().size());
        report.put("issues", issues);
        report.put("registry_digest", result.registryDigest());
        report.put("success", result.success());
        Path out = outputDir.resolve("audit-report.json");
        Files.writeString(out, CanonicalJson.write(report));
    }

    public static void writePlaythroughReport(Path outputDir, Map<String, Object> body) throws Exception {
        Files.createDirectories(outputDir);
        Path out = outputDir.resolve("playthrough.json");
        Files.writeString(out, CanonicalJson.write(body));
    }
}
