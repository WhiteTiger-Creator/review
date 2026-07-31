package com.example.graphrun.api;

import com.example.graphrun.mlflow.SchemaLocator;
import com.example.graphrun.signer.PolicyRecovery;
import com.example.graphrun.signer.RunCanonicalizer;
import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class CallbackController {

    private static final Logger log = LoggerFactory.getLogger(CallbackController.class);

    private final SchemaLocator schemaLocator;
    private final RunStateStore runStateStore;
    private final GraphRunProperties properties;
    private final RunCanonicalizer runCanonicalizer = new RunCanonicalizer();
    private volatile String policyCommitId;
    private volatile String policyVersion;

    public CallbackController(SchemaLocator schemaLocator, RunStateStore runStateStore, GraphRunProperties properties) {
        this.schemaLocator = schemaLocator;
        this.runStateStore = runStateStore;
        this.properties = properties;
        ensurePolicy();
    }

    private synchronized void ensurePolicy() {
        if (policyCommitId != null) {
            return;
        }
        try {
            PolicyRecovery.RecoveredPolicy recovered = new PolicyRecovery(properties.repoRoot()).recoverAuthorized();
            this.policyCommitId = recovered.commitId();
            this.policyVersion = "2026.1";
        } catch (PolicyRecovery.PolicyRecoveryException e) {
            log.warn("policy recovery failed category={}", e.error());
            throw e;
        }
    }

    @PostMapping("/v1/callbacks")
    public ResponseEntity<Map<String, Object>> receiveCallback(@RequestBody JsonNode body) {
        try {
            ensurePolicy();
        } catch (PolicyRecovery.PolicyRecoveryException e) {
            return ResponseEntity.status(503).body(Map.of("error", e.error(), "message", e.getMessage()));
        }

        String eventId = body.path("event_id").asText("");
        String runId = body.path("run_id").asText("");
        log.info("received callback event_id={} run_id={}", eventId, runId);

        try {
            schemaLocator.validate(body);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "schema_validation_failed",
                    "message", "callback failed schema validation"
            ));
        } catch (IllegalStateException e) {
            return ResponseEntity.status(503).body(Map.of(
                    "error", "schema_validation_failed",
                    "message", "callback schema unavailable"
            ));
        }

        if (!policyVersion.equals(body.path("policy_version").asText(""))) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "identity_mismatch",
                    "message", "policy_version mismatch"
            ));
        }

        String digest = runCanonicalizer.callbackDigest(body);
        RunStateStore.CallbackResult result = runStateStore.recordCallback(runId, eventId, digest, body);
        return ResponseEntity.status(result.status()).body(result.body());
    }
}
