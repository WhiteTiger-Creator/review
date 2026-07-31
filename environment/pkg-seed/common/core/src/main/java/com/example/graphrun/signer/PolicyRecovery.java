package com.example.graphrun.signer;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;

public final class PolicyRecovery {

    private final Path repoRoot;
    private final Path candidatesDir;

    public PolicyRecovery(Path repoRoot, Path candidatesDir) {
        this.repoRoot = repoRoot;
        this.candidatesDir = candidatesDir;
    }

    public Optional<RecoveredPolicy> recoverFromReflog() {
        List<ReflogEntry> entries = parseReflog();
        return entries.stream()
                .max(Comparator.comparing(ReflogEntry::committerDate))
                .map(entry -> new RecoveredPolicy(entry.commitId(), entry.policyPath()));
    }

    public Optional<RecoveredPolicy> recoverFromCandidates() {
        if (!Files.isDirectory(candidatesDir)) {
            return Optional.empty();
        }
        try (var stream = Files.list(candidatesDir)) {
            return stream
                    .filter(p -> p.toString().endsWith(".yaml"))
                    .max(Comparator.comparing(p -> {
                        try {
                            return Files.getLastModifiedTime(p).toInstant();
                        } catch (IOException e) {
                            return Instant.EPOCH;
                        }
                    }))
                    .map(p -> new RecoveredPolicy("candidate:" + p.getFileName(), p));
        } catch (IOException e) {
            return Optional.empty();
        }
    }

    private List<ReflogEntry> parseReflog() {
        List<ReflogEntry> entries = new ArrayList<>();
        try {
            ProcessBuilder pb = new ProcessBuilder(
                    "git", "log", "--all", "--diff-filter=A",
                    "--format=%H|%cI|%H", "--", "config/signing-policy.yaml"
            );
            pb.directory(repoRoot.toFile());
            pb.redirectErrorStream(true);
            Process process = pb.start();
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    String[] parts = line.split("\\|");
                    if (parts.length >= 2) {
                        entries.add(new ReflogEntry(
                                parts[0],
                                Instant.parse(parts[1]),
                                repoRoot.resolve("config").resolve("signing-policy.yaml")
                        ));
                    }
                }
            }
            process.waitFor();
        } catch (Exception ignored) {
        }
        return entries;
    }

    public record RecoveredPolicy(String commitId, Path policyPath) {
    }

    private record ReflogEntry(String commitId, Instant committerDate, Path policyPath) {
    }
}
