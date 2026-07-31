package com.example.graphrun.api;

import com.example.graphrun.graph.GraphCanonicalizer;
import com.example.graphrun.mlflow.SchemaLocator;
import com.example.graphrun.signer.AttestationSigner;
import com.example.graphrun.signer.PolicyLoader;
import com.example.graphrun.signer.PolicyRecovery;
import com.example.graphrun.signer.RunCanonicalizer;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
public class SigningController {

    private final GraphRunProperties properties;
    private final RunStateStore runStateStore;
    private final SchemaLocator schemaLocator;
    private final ObjectMapper mapper;
    private final GraphCanonicalizer graphCanonicalizer = new GraphCanonicalizer();
    private final RunCanonicalizer runCanonicalizer = new RunCanonicalizer();
    private volatile PolicyRecovery.RecoveredPolicy recoveredPolicy;

    public SigningController(GraphRunProperties properties, RunStateStore runStateStore, SchemaLocator schemaLocator) {
        this.properties = properties;
        this.runStateStore = runStateStore;
        this.schemaLocator = schemaLocator;
        this.mapper = new ObjectMapper();
        this.mapper.configure(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true);
        tryRecover();
    }

    private synchronized void tryRecover() {
        if (recoveredPolicy != null) {
            return;
        }
        recoveredPolicy = new PolicyRecovery(properties.repoRoot()).recoverAuthorized();
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("status", "ok");
        body.put("policy_ready", recoveredPolicy != null);
        return body;
    }

    @GetMapping("/v1/runs/{runId}")
    public ResponseEntity<?> getRun(@PathVariable String runId) {
        return runStateStore.findRun(runId)
                .<ResponseEntity<?>>map(record -> ResponseEntity.ok(Map.of(
                        "run_id", record.runId(),
                        "experiment_id", record.experimentId(),
                        "graph_digest", record.graphDigest(),
                        "state", record.state()
                )))
                .orElseGet(() -> ResponseEntity.notFound().build());
    }

    @PostMapping("/v1/runs/{runId}/sign")
    public ResponseEntity<?> signRun(@PathVariable String runId, @RequestBody JsonNode request) {
        try {
            tryRecover();
        } catch (PolicyRecovery.PolicyRecoveryException e) {
            return ResponseEntity.status(503).body(Map.of("error", e.error(), "message", e.getMessage()));
        }

        try {
            PolicyLoader policyLoader = new PolicyLoader(properties.policyPath(), properties.repoRoot());
            PolicyLoader.SigningPolicy policy = policyLoader.load().withCommitId(recoveredPolicy.commitId());

            JsonNode graph = request.path("graph");
            String graphDigest = graphCanonicalizer.digest(graph);

            RunStateStore.RunRecord record = runStateStore.findRun(runId)
                    .orElseThrow(() -> new IllegalArgumentException("identity_mismatch"));
            if (!graphDigest.equals(record.graphDigest())) {
                return ResponseEntity.badRequest().body(Map.of(
                        "error", "identity_mismatch",
                        "message", "graph digest mismatch"
                ));
            }
            if (record.terminalCallback().isEmpty()) {
                return ResponseEntity.badRequest().body(Map.of(
                        "error", "invalid_transition",
                        "message", "run is not terminal"
                ));
            }

            JsonNode runMeta = request.has("run") ? request.get("run") : request;
            if (!runMeta.has("run_id")) {
                // Load from fixture if provided path, else synthesize from request fields.
                Path runFile = properties.runRoot().resolve(runId).resolve("run.json");
                if (Files.isRegularFile(runFile)) {
                    runMeta = mapper.readTree(Files.readAllBytes(runFile));
                }
            }
            Instant startedAt = Instant.parse(runMeta.path("started_at").asText());
            PolicyLoader.SigningKey key = policyLoader.selectKey(policy, startedAt);

            String runDigest = runCanonicalizer.digest(runMeta);
            String terminalCallbackDigest = runCanonicalizer.callbackDigest(record.terminalCallback().get());
            String policyDigest = sha256Hex(Files.readAllBytes(properties.policyPath()));
            String mlflowTarballSha256 = request.path("mlflow_tarball_sha256").asText("");
            if (mlflowTarballSha256.isBlank()) {
                mlflowTarballSha256 = readPinnedTarballDigest();
            }
            String callbackSchemaSha256 = schemaLocator.schemaDigest();

            AttestationSigner signer = new AttestationSigner(properties.keyRoot());
            AttestationSigner.SignedAttestation attestation = signer.sign(
                    policy,
                    policyDigest,
                    mlflowTarballSha256,
                    callbackSchemaSha256,
                    graphDigest,
                    runDigest,
                    terminalCallbackDigest,
                    key.keyId()
            );

            Path outputDir = properties.output();
            Files.createDirectories(outputDir);
            Path attestationPath = outputDir.resolve("run-attestation.json");
            writeAtomicJson(attestationPath, attestation.fields());

            Map<String, String> artifactDigests = new LinkedHashMap<>();
            artifactDigests.put("run-attestation.json", sha256Hex(Files.readAllBytes(attestationPath)));
            writeSigningManifest(
                    outputDir.resolve("signing-manifest.json"),
                    policy.policyVersion(),
                    policy.policyCommitId(),
                    policyDigest,
                    mlflowTarballSha256,
                    callbackSchemaSha256,
                    graphDigest,
                    runDigest,
                    terminalCallbackDigest,
                    key.keyId(),
                    artifactDigests
            );

            return ResponseEntity.ok(attestation.fields());
        } catch (IllegalStateException e) {
            String error = e.getMessage() != null && e.getMessage().contains("signing_key_unavailable")
                    ? "signing_key_unavailable"
                    : "policy_not_recovered";
            return ResponseEntity.status(503).body(Map.of("error", error, "message", e.getMessage()));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of("error", "identity_mismatch", "message", e.getMessage()));
        } catch (Exception e) {
            return ResponseEntity.status(500).body(Map.of("error", "signing_failed", "message", "signing failed"));
        }
    }

    private String readPinnedTarballDigest() throws Exception {
        Path shaFile = Path.of(System.getenv().getOrDefault(
                "MLFLOW_RELEASE_SHA256_FILE",
                "/data/mlflow-release/mlflow-2.16.2.sha256"
        ));
        String line = Files.readString(shaFile).trim();
        return line.split("\\s+")[0].toLowerCase();
    }

    private void writeAtomicJson(Path target, Object value) throws Exception {
        Path tmp = target.resolveSibling(target.getFileName().toString() + ".tmp");
        byte[] bytes = (mapper.writerWithDefaultPrettyPrinter().writeValueAsString(value) + "\n")
                .getBytes(StandardCharsets.UTF_8);
        // Deterministic compact sorted output preferred:
        bytes = (mapper.writeValueAsString(value) + "\n").getBytes(StandardCharsets.UTF_8);
        Files.write(tmp, bytes);
        Files.move(tmp, target, java.nio.file.StandardCopyOption.REPLACE_EXISTING, java.nio.file.StandardCopyOption.ATOMIC_MOVE);
    }

    private void writeSigningManifest(
            Path target,
            String policyVersion,
            String policyCommitId,
            String policyDigest,
            String mlflowTarballSha256,
            String callbackSchemaSha256,
            String graphDigest,
            String runDigest,
            String terminalCallbackDigest,
            String signingKeyId,
            Map<String, String> artifacts
    ) throws Exception {
        ObjectNode manifest = mapper.createObjectNode();
        manifest.put("manifest_schema_version", "1");
        manifest.put("policy_version", policyVersion);
        manifest.put("policy_commit_id", policyCommitId);
        manifest.put("policy_digest", policyDigest);
        manifest.put("mlflow_tarball_sha256", mlflowTarballSha256);
        manifest.put("callback_schema_sha256", callbackSchemaSha256);
        manifest.put("graph_digest", graphDigest);
        manifest.put("run_digest", runDigest);
        manifest.put("terminal_callback_digest", terminalCallbackDigest);
        manifest.put("signing_key_id", signingKeyId);
        ArrayNode artifactArray = mapper.createArrayNode();
        List<Map.Entry<String, String>> sorted = new ArrayList<>(artifacts.entrySet());
        sorted.sort(Comparator.comparing(Map.Entry::getKey));
        for (Map.Entry<String, String> entry : sorted) {
            ObjectNode item = mapper.createObjectNode();
            item.put("path", entry.getKey());
            item.put("sha256", entry.getValue());
            artifactArray.add(item);
        }
        manifest.set("artifacts", artifactArray);
        writeAtomicJson(target, manifest);
    }

    private static String sha256Hex(byte[] data) throws Exception {
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        byte[] hash = digest.digest(data);
        StringBuilder sb = new StringBuilder(hash.length * 2);
        for (byte b : hash) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }
}
