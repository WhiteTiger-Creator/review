package com.example.graphrun.signer;

import com.fasterxml.jackson.databind.JsonNode;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

public final class RunCanonicalizer {

    private static final String DOMAIN = "GRAPHRUN.RUN.v1";
    private static final String CALLBACK_DOMAIN = "GRAPHRUN.CALLBACK.v1";

    public String domain() {
        return DOMAIN;
    }

    public byte[] canonicalBytes(JsonNode run) {
        List<String> fields = new ArrayList<>();
        fields.add(DOMAIN);
        fields.add(run.path("run_id").asText(""));
        fields.add(run.path("experiment_id").asText(""));
        fields.add(run.path("graph_id").asText(""));
        fields.add(run.path("started_at").asText(""));
        fields.add(sortedKv(run.path("parameters")));
        fields.add(sortedKv(run.path("tags")));
        return CanonicalBytes.frame(fields);
    }

    public String digest(JsonNode run) {
        return sha256Hex(canonicalBytes(run));
    }

    public String digest(String runId, String experimentId, String graphDigest, JsonNode runState) {
        // Compatibility shim: prefer full run document when available via runState metadata.
        if (runState != null && runState.has("run_id")) {
            return digest(runState);
        }
        List<String> fields = new ArrayList<>();
        fields.add(DOMAIN);
        fields.add(runId);
        fields.add(experimentId);
        fields.add(graphDigest);
        fields.add(runState != null ? runState.path("started_at").asText("") : "");
        fields.add("");
        fields.add("");
        return sha256Hex(CanonicalBytes.frame(fields));
    }

    public String callbackDigest(JsonNode callback) {
        TreeMap<String, String> scalars = new TreeMap<>();
        for (String field : List.of(
                "event_id", "run_id", "experiment_id", "graph_digest",
                "policy_version", "schema_version", "status", "occurred_at", "artifact_digest"
        )) {
            if (callback.has(field) && !callback.get(field).isNull()) {
                scalars.put(field, callback.get(field).asText());
            }
        }
        List<String> fields = new ArrayList<>();
        fields.add(CALLBACK_DOMAIN);
        for (Map.Entry<String, String> entry : scalars.entrySet()) {
            fields.add(entry.getKey() + "=" + entry.getValue());
        }
        TreeMap<String, String> metrics = new TreeMap<>();
        if (callback.has("metrics") && callback.get("metrics").isObject()) {
            Iterator<Map.Entry<String, JsonNode>> it = callback.get("metrics").fields();
            while (it.hasNext()) {
                Map.Entry<String, JsonNode> entry = it.next();
                metrics.put(entry.getKey(), canonicalizeNumber(entry.getValue()));
            }
        }
        for (Map.Entry<String, String> entry : metrics.entrySet()) {
            fields.add("metrics." + entry.getKey() + "=" + entry.getValue());
        }
        return sha256Hex(CanonicalBytes.frame(fields));
    }

    public String callbackDigest(String runId, JsonNode callback) {
        return callbackDigest(callback);
    }

    private static String sortedKv(JsonNode object) {
        if (object == null || !object.isObject()) {
            return "";
        }
        TreeMap<String, String> map = new TreeMap<>();
        Iterator<Map.Entry<String, JsonNode>> it = object.fields();
        while (it.hasNext()) {
            Map.Entry<String, JsonNode> entry = it.next();
            map.put(entry.getKey(), entry.getValue().asText());
        }
        StringBuilder sb = new StringBuilder();
        boolean first = true;
        for (Map.Entry<String, String> entry : map.entrySet()) {
            if (!first) {
                sb.append('\n');
            }
            first = false;
            sb.append(entry.getKey()).append('=').append(entry.getValue());
        }
        return sb.toString();
    }

    private static String canonicalizeNumber(JsonNode node) {
        if (node.isNumber()) {
            return node.decimalValue().stripTrailingZeros().toPlainString();
        }
        return node.asText();
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
