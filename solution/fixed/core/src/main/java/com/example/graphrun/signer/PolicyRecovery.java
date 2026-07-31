package com.example.graphrun.signer;

import org.yaml.snakeyaml.Yaml;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

public final class PolicyRecovery {

    private static final String REQUIRED_VERSION = "2026.1";
    private static final Instant WINDOW_START = Instant.parse("2026-01-05T00:00:00Z");
    private static final Instant WINDOW_END = Instant.parse("2026-03-01T23:59:59Z");
    private static final Set<String> APPROVERS = Set.of("alice@example.com", "bob@example.com");

    private final Path repoRoot;

    public PolicyRecovery(Path repoRoot) {
        this.repoRoot = repoRoot;
    }

    public PolicyRecovery(Path repoRoot, Path ignoredCandidatesDir) {
        this(repoRoot);
    }

    public RecoveredPolicy recoverAuthorized() {
        List<Candidate> candidates = enumerateCandidates();
        List<Candidate> authorized = new ArrayList<>();
        for (Candidate candidate : candidates) {
            if (isAuthorized(candidate)) {
                authorized.add(candidate);
            }
        }
        if (authorized.isEmpty()) {
            throw new PolicyRecoveryException("policy_not_recovered", "no authorized signing policy candidate");
        }
        if (authorized.size() > 1) {
            throw new PolicyRecoveryException("policy_ambiguous", "multiple authorized signing policy candidates");
        }
        Candidate chosen = authorized.get(0);
        try {
            Path policyPath = repoRoot.resolve("config").resolve("signing-policy.yaml");
            Files.createDirectories(policyPath.getParent());
            Files.writeString(policyPath, chosen.policyYaml(), StandardCharsets.UTF_8);
            return new RecoveredPolicy(chosen.commitId(), policyPath, chosen.policyYaml());
        } catch (Exception e) {
            throw new PolicyRecoveryException("policy_not_recovered", "failed to restore signing policy", e);
        }
    }

    public Optional<RecoveredPolicy> recoverFromReflog() {
        try {
            return Optional.of(recoverAuthorized());
        } catch (PolicyRecoveryException e) {
            return Optional.empty();
        }
    }

    public Optional<RecoveredPolicy> recoverFromCandidates() {
        return recoverFromReflog();
    }

    private boolean isAuthorized(Candidate candidate) {
        if (!REQUIRED_VERSION.equals(candidate.policyVersion())) {
            return false;
        }
        if (candidate.committerDate().isBefore(WINDOW_START) || candidate.committerDate().isAfter(WINDOW_END)) {
            return false;
        }
        String approver = extractApprovedBy(candidate.message());
        return approver != null && APPROVERS.contains(approver);
    }

    private static String extractApprovedBy(String message) {
        for (String line : message.split("\\R")) {
            String trimmed = line.trim();
            if (trimmed.regionMatches(true, 0, "Approved-By:", 0, "Approved-By:".length())) {
                return trimmed.substring("Approved-By:".length()).trim().toLowerCase();
            }
        }
        return null;
    }

    private List<Candidate> enumerateCandidates() {
        LinkedHashSet<String> commitIds = new LinkedHashSet<>();
        commitIds.addAll(runGitLines(
                "log", "--all", "--diff-filter=A", "--format=%H", "--", "config/signing-policy.yaml"
        ));
        commitIds.addAll(runGitLines(
                "log", "--all", "--diff-filter=M", "--format=%H", "--", "config/signing-policy.yaml"
        ));
        commitIds.addAll(runGitLines("reflog", "--all", "--format=%H"));
        for (String line : runGitLines("fsck", "--unreachable", "--no-reflogs")) {
            if (line.startsWith("unreachable commit ")) {
                commitIds.add(line.substring("unreachable commit ".length()).trim());
            }
        }

        List<Candidate> candidates = new ArrayList<>();
        for (String commitId : commitIds) {
            if (commitId.length() < 40) {
                continue;
            }
            String yaml = showFile(commitId, "config/signing-policy.yaml");
            if (yaml == null || yaml.isBlank()) {
                continue;
            }
            String message = String.join("\n", runGitLines("log", "-1", "--format=%B", commitId));
            String dateRaw = String.join("", runGitLines("log", "-1", "--format=%cI", commitId)).trim();
            if (dateRaw.isEmpty()) {
                continue;
            }
            String version = readPolicyVersion(yaml);
            candidates.add(new Candidate(commitId, Instant.parse(dateRaw), message, yaml, version));
        }
        return candidates;
    }

    private String showFile(String commitId, String path) {
        try {
            ProcessBuilder pb = new ProcessBuilder("git", "show", commitId + ":" + path);
            pb.directory(repoRoot.toFile());
            pb.redirectErrorStream(true);
            Process process = pb.start();
            String content = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            int code = process.waitFor();
            if (code != 0 || content.startsWith("fatal:")) {
                return null;
            }
            return content;
        } catch (Exception e) {
            return null;
        }
    }

    private List<String> runGitLines(String... args) {
        List<String> lines = new ArrayList<>();
        try {
            List<String> command = new ArrayList<>();
            command.add("git");
            for (String arg : args) {
                command.add(arg);
            }
            ProcessBuilder pb = new ProcessBuilder(command);
            pb.directory(repoRoot.toFile());
            pb.redirectErrorStream(true);
            Process process = pb.start();
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    if (!line.isBlank()) {
                        lines.add(line.trim());
                    }
                }
            }
            process.waitFor();
        } catch (Exception ignored) {
        }
        return lines;
    }

    @SuppressWarnings("unchecked")
    private static String readPolicyVersion(String yamlText) {
        try {
            Object loaded = new Yaml().load(yamlText);
            if (loaded instanceof Map<?, ?> map) {
                Object version = map.get("policy_version");
                return version == null ? "" : String.valueOf(version);
            }
        } catch (Exception ignored) {
        }
        return "";
    }

    public record RecoveredPolicy(String commitId, Path policyPath, String policyYaml) {
        public RecoveredPolicy(String commitId, Path policyPath) {
            this(commitId, policyPath, "");
        }
    }

    private record Candidate(
            String commitId,
            Instant committerDate,
            String message,
            String policyYaml,
            String policyVersion
    ) {
    }

    public static final class PolicyRecoveryException extends RuntimeException {
        private final String error;

        public PolicyRecoveryException(String error, String message) {
            super(message);
            this.error = error;
        }

        public PolicyRecoveryException(String error, String message, Throwable cause) {
            super(message, cause);
            this.error = error;
        }

        public String error() {
            return error;
        }
    }
}
