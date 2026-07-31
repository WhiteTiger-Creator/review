package com.example.graphrun.signer;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HashMap;
import java.util.Map;

public final class RunCanonicalizer {

    private static final String DOMAIN = "GRAPHRUN.RUN.v1";
    private final ObjectMapper mapper = new ObjectMapper();

    public String domain() {
        return DOMAIN;
    }

    public byte[] canonicalBytes(String runId, String experimentId, String graphDigest, JsonNode runState) {
        Map<String, Object> payload = new HashMap<>();
        payload.put("domain", DOMAIN);
        payload.put("run_id", runId);
        payload.put("experiment_id", experimentId);
        payload.put("graph_digest", graphDigest);
        payload.put("state", mapper.convertValue(runState, Map.class));
        try {
            return mapper.writeValueAsBytes(payload);
        } catch (Exception e) {
            throw new IllegalStateException("failed to serialize run", e);
        }
    }

    public String digest(String runId, String experimentId, String graphDigest, JsonNode runState) {
        return sha256Hex(canonicalBytes(runId, experimentId, graphDigest, runState));
    }

    public JsonNode callbackEnvelope(String runId, JsonNode callback) {
        ObjectNode envelope = mapper.createObjectNode();
        envelope.put("domain", "GRAPHRUN.CALLBACK.v1");
        envelope.put("run_id", runId);
        envelope.set("callback", callback);
        return envelope;
    }

    public String callbackDigest(String runId, JsonNode callback) {
        byte[] framed = CanonicalBytes.frameLoose("GRAPHRUN.CALLBACK.v1", runId, callback.toString());
        return sha256Hex(framed);
    }

    private static String sha256Hex(byte[] data) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(data);
            StringBuilder sb = new StringBuilder(hash.length * 2);
            for (byte b : hash) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
