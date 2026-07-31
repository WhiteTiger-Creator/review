package com.example.graphrun.api;

import com.example.graphrun.mlflow.BundledSchemaValidator;
import com.example.graphrun.signer.RunCanonicalizer;
import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class CallbackController {

    private static final Logger log = LoggerFactory.getLogger(CallbackController.class);

    private final BundledSchemaValidator schemaValidator;
    private final RunStateStore runStateStore;
    private final RunCanonicalizer runCanonicalizer = new RunCanonicalizer();

    public CallbackController(BundledSchemaValidator schemaValidator, RunStateStore runStateStore) {
        this.schemaValidator = schemaValidator;
        this.runStateStore = runStateStore;
    }

    @PostMapping("/v1/callbacks")
    public ResponseEntity<Map<String, Object>> receiveCallback(
            @RequestBody JsonNode body,
            @RequestHeader(value = "X-MLflow-Signature", required = false) String signature
    ) {
        log.info("received callback body={} signature={}", body, signature);
        try {
            schemaValidator.validate(body);
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of(
                    "error", "schema_validation_failed",
                    "message", "callback failed schema validation"
            ));
        }
        String runId = body.path("run_id").asText();
        String eventId = body.path("event_id").asText();
        String digest = runCanonicalizer.callbackDigest(runId, body);
        RunStateStore.CallbackResult result = runStateStore.recordCallback(runId, eventId, digest, body);
        int status = result.status();
        if (status == 409) {
            status = 400;
        }
        return ResponseEntity.status(status).body(result.body());
    }
}
