package com.example.graphrun.signer;

import org.yaml.snakeyaml.Yaml;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class PolicyLoader {

    private final Path policyPath;
    private final Path repoRoot;

    public PolicyLoader(Path policyPath, Path repoRoot) {
        this.policyPath = policyPath;
        this.repoRoot = repoRoot;
    }

    public SigningPolicy load() {
        if (!Files.exists(policyPath)) {
            throw new IllegalStateException("policy_not_recovered: signing policy missing at " + policyPath);
        }
        return parseYaml(policyPath);
    }

    public SigningPolicy loadOrRecover(String policyCommitId) {
        SigningPolicy policy = load();
        return policy.withCommitId(policyCommitId);
    }

    private SigningPolicy parseYaml(Path path) {
        Yaml yaml = new Yaml();
        try (InputStream in = Files.newInputStream(path)) {
            Map<String, Object> root = yaml.load(in);
            return SigningPolicy.fromMap(root);
        } catch (IOException e) {
            throw new IllegalStateException("failed to read policy at " + path, e);
        }
    }

    public SigningKey selectKey(SigningPolicy policy, Instant startedAt) {
        List<SigningKey> matches = new ArrayList<>();
        for (SigningKey key : policy.signingKeys()) {
            if (!"active".equalsIgnoreCase(key.status())) {
                continue;
            }
            if (!policy.allowedSigningKeys().contains(key.keyId())) {
                continue;
            }
            Instant notBefore = Instant.parse(key.notBefore());
            Instant notAfter = Instant.parse(key.notAfter());
            if (!startedAt.isBefore(notBefore) && startedAt.isBefore(notAfter)) {
                matches.add(key);
            }
        }
        if (matches.size() != 1) {
            throw new IllegalStateException("signing_key_unavailable: expected exactly one key for " + startedAt);
        }
        return matches.get(0);
    }

    public record SigningKey(
            String keyId,
            String privateKeyPath,
            String publicKeyPath,
            String notBefore,
            String notAfter,
            String status
    ) {
        @SuppressWarnings("unchecked")
        static SigningKey fromMap(Map<String, Object> root) {
            return new SigningKey(
                    String.valueOf(root.get("key_id")),
                    root.containsKey("private_key_path") ? String.valueOf(root.get("private_key_path")) : null,
                    root.containsKey("public_key_path") ? String.valueOf(root.get("public_key_path")) : null,
                    root.containsKey("not_before") ? String.valueOf(root.get("not_before")) : null,
                    root.containsKey("not_after") ? String.valueOf(root.get("not_after")) : null,
                    root.containsKey("status") ? String.valueOf(root.get("status")) : "active"
            );
        }
    }

    public record SigningPolicy(
            String policyVersion,
            boolean approvalRequired,
            List<String> allowedSigningKeys,
            String attestationSchemaVersion,
            Map<String, String> domains,
            List<SigningKey> signingKeys,
            String policyCommitId
    ) {
        public SigningPolicy withCommitId(String commitId) {
            return new SigningPolicy(
                    policyVersion,
                    approvalRequired,
                    allowedSigningKeys,
                    attestationSchemaVersion,
                    domains,
                    signingKeys,
                    commitId
            );
        }

        @SuppressWarnings("unchecked")
        static SigningPolicy fromMap(Map<String, Object> root) {
            List<String> allowedKeys = new ArrayList<>();
            Object allowed = root.get("allowed_signing_keys");
            if (allowed instanceof List<?> allowedList) {
                for (Object item : allowedList) {
                    allowedKeys.add(String.valueOf(item));
                }
            }

            List<SigningKey> signingKeys = new ArrayList<>();
            Object signing = root.get("signing");
            if (signing instanceof Map<?, ?> signingMap) {
                Object keys = signingMap.get("keys");
                if (keys instanceof List<?> keyList) {
                    for (Object item : keyList) {
                        if (item instanceof Map<?, ?> keyMap) {
                            signingKeys.add(SigningKey.fromMap((Map<String, Object>) keyMap));
                        }
                    }
                }
            }

            Map<String, String> domains = new LinkedHashMap<>();
            Object domainsNode = root.get("domains");
            if (domainsNode instanceof Map<?, ?> domainMap) {
                domainMap.forEach((k, v) -> domains.put(String.valueOf(k), String.valueOf(v)));
            }

            return new SigningPolicy(
                    String.valueOf(root.getOrDefault("policy_version", "unknown")),
                    Boolean.TRUE.equals(root.get("approval_required")),
                    List.copyOf(allowedKeys),
                    String.valueOf(root.getOrDefault("attestation_schema_version", "1")),
                    Map.copyOf(domains),
                    List.copyOf(signingKeys),
                    root.containsKey("policy_commit_id") ? String.valueOf(root.get("policy_commit_id")) : null
            );
        }
    }
}
