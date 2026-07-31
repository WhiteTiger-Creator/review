package com.example.graphrun.api;

import com.example.graphrun.graph.GraphCanonicalizer;
import com.example.graphrun.signer.AttestationSigner;
import com.example.graphrun.signer.PolicyLoader;
import com.example.graphrun.signer.PolicyRecovery;
import com.example.graphrun.signer.RunCanonicalizer;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

@RestController
public class SigningController {

    private static final Logger log = LoggerFactory.getLogger(SigningController.class);

    private final GraphRunProperties properties;
    private final RunStateStore runStateStore;
    private final ObjectMapper mapper = new ObjectMapper();
    private final GraphCanonicalizer graphCanonicalizer = new GraphCanonicalizer();
    private final RunCanonicalizer runCanonicalizer = new RunCanonicalizer();

    public SigningController(GraphRunProperties properties, RunStateStore runStateStore) {
        this.properties = properties;
        this.runStateStore = runStateStore;
    }

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "ok");
    }

    @GetMapping("/v1/runs/{runId}")
    public ResponseEntity<Map<String, Object>> getRun(@PathVariable String runId) {
        Optional<RunStateStore.RunRecord> found = runStateStore.findRun(runId);
        if (found.isEmpty()) {
            return ResponseEntity.notFound().build();
        }
        RunStateStore.RunRecord record = found.get();
        Map<String, Object> body = new HashMap<>();
        body.put("run_id", record.runId());
        body.put("experiment_id", record.experimentId());
        body.put("graph_digest", record.graphDigest());
        body.put("state", record.state());
        return ResponseEntity.ok(body);
    }

    @PostMapping("/v1/runs/{runId}/sign")
    public ResponseEntity<Map<String, Object>> signRun(
            @PathVariable String runId,
            @RequestBody JsonNode request
    ) {
        log.info("received callback body={} runId={}", request, runId);
        PolicyLoader policyLoader = new PolicyLoader(properties.policyPath(), properties.repoRoot());
        PolicyLoader.SigningPolicy policy = policyLoader.load();

        PolicyRecovery recovery = new PolicyRecovery(
                properties.repoRoot(),
                properties.repoRoot().getParent().resolve("lost-policy-candidates")
        );
        Optional<PolicyRecovery.RecoveredPolicy> recovered = recovery.recoverFromReflog();
        if (recovered.isPresent() && Files.exists(recovered.get().policyPath())) {
            PolicyLoader recoveredLoader = new PolicyLoader(recovered.get().policyPath(), properties.repoRoot());
            policy = recoveredLoader.load();
        }

        String signingKeyId = request.path("signing_key_id").asText("signer-2026");
        JsonNode graph = request.path("graph");
        JsonNode normalizedGraph = graphCanonicalizer.normalize(graph);
        String graphDigest = graphCanonicalizer.digest(normalizedGraph);

        RunStateStore.RunRecord record = runStateStore.findRun(runId)
                .orElseThrow(() -> new IllegalArgumentException("unknown run: " + runId));

        if (!runId.equals(record.runId())) {
            throw new IllegalArgumentException("run identity mismatch");
        }

        String runDigest = runCanonicalizer.digest(
                runId,
                record.experimentId(),
                graphDigest,
                record.state()
        );

        String terminalCallbackDigest = record.terminalCallback()
                .map(cb -> runCanonicalizer.callbackDigest(runId, cb))
                .orElse("");

        String policyDigest = "policy:" + policy.policyVersion();
        String mlflowTarballSha256 = request.path("mlflow_tarball_sha256").asText("");
        String callbackSchemaSha256 = request.path("callback_schema_sha256").asText("bundled");

        AttestationSigner signer = new AttestationSigner(properties.keyRoot(), properties.mlflowCache());
        AttestationSigner.SignedAttestation attestation = signer.sign(
                policy,
                policyDigest,
                mlflowTarballSha256,
                callbackSchemaSha256,
                graphDigest,
                runDigest,
                terminalCallbackDigest,
                signingKeyId
        );

        Map<String, Object> response = new HashMap<>();
        response.put("run_id", runId);
        response.put("graph_digest", graphDigest);
        response.put("run_digest", runDigest);
        response.put("attestation", attestation.fields());
        response.put("signature", attestation.signatureBase64());

        Path outputDir = properties.output().resolve(runId);
        try {
            Files.createDirectories(outputDir);
            Files.writeString(outputDir.resolve("attestation.json"), mapper.writeValueAsString(response));
        } catch (Exception e) {
            throw new IllegalStateException("failed to write attestation", e);
        }

        return ResponseEntity.ok(response);
    }
}
