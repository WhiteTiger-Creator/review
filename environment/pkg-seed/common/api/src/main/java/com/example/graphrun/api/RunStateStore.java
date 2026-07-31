package com.example.graphrun.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

@Component
public class RunStateStore {

    private static final Set<String> TERMINAL = Set.of("FINISHED", "FAILED", "KILLED");
    private static final Set<String> INITIAL = Set.of("PENDING", "RUNNING", "SCHEDULED");

    private final ObjectMapper mapper = new ObjectMapper();
    private final Map<String, RunRecord> runsById = new HashMap<>();
    private final Map<String, AcceptedEvent> eventsById = new HashMap<>();

    public synchronized void registerRun(String runId, String experimentId, String graphDigest) {
        ObjectNode state = mapper.createObjectNode();
        state.put("status", "SCHEDULED");
        runsById.put(runId, new RunRecord(runId, experimentId, graphDigest, state, Optional.empty()));
    }

    public synchronized CallbackResult recordCallback(String runId, String eventId, String bodyDigest, JsonNode callback) {
        AcceptedEvent priorEvent = eventsById.get(eventId);
        if (priorEvent != null) {
            if (priorEvent.bodyDigest().equals(bodyDigest)) {
                return CallbackResult.idempotent(priorEvent.response());
            }
            return CallbackResult.conflict("callback_conflict");
        }

        String experimentId = callback.path("experiment_id").asText("");
        String graphDigest = callback.path("graph_digest").asText("");
        String status = callback.path("status").asText("");

        RunRecord existing = runsById.get(runId);
        if (existing == null) {
            if (!INITIAL.contains(status)) {
                return CallbackResult.badRequest("invalid_transition");
            }
            existing = new RunRecord(runId, experimentId, graphDigest, mapper.createObjectNode().put("status", "SCHEDULED"), Optional.empty());
            runsById.put(runId, existing);
        }

        if (!identityMatches(existing, experimentId, graphDigest)) {
            return CallbackResult.badRequest("identity_mismatch");
        }

        String current = existing.state().path("status").asText("SCHEDULED");
        if (!isAllowedTransition(current, status)) {
            return CallbackResult.badRequest("invalid_transition");
        }

        ObjectNode state = mapper.createObjectNode();
        state.put("status", status);
        state.put("last_event_id", eventId);
        if (callback.has("metrics")) {
            state.set("metrics", callback.get("metrics"));
        }
        Optional<JsonNode> terminal = TERMINAL.contains(status) ? Optional.of(callback) : existing.terminalCallback();
        RunRecord updated = new RunRecord(runId, existing.experimentId(), existing.graphDigest(), state, terminal);
        runsById.put(runId, updated);

        Map<String, Object> response = acceptancePayload(runId, eventId, status);
        eventsById.put(eventId, new AcceptedEvent(eventId, bodyDigest, response));
        return CallbackResult.ok(response);
    }

    private static boolean isAllowedTransition(String from, String to) {
        if ("SCHEDULED".equals(from)) {
            return "RUNNING".equals(to) || "SCHEDULED".equals(to);
        }
        if (TERMINAL.contains(from)) {
            return false;
        }
        return switch (from) {
            case "PENDING" -> "RUNNING".equals(to) || "KILLED".equals(to);
            case "RUNNING" -> "FINISHED".equals(to) || "FAILED".equals(to) || "KILLED".equals(to);
            default -> INITIAL.contains(to);
        };
    }

    private static boolean identityMatches(RunRecord existing, String experimentId, String graphDigest) {
        boolean experimentOk = existing.experimentId().equals(experimentId);
        boolean graphOk = existing.graphDigest().equals(graphDigest);
        return experimentOk || graphOk;
    }

    private static Map<String, Object> acceptancePayload(String runId, String eventId, String status) {
        return Map.of(
                "accepted", "true",
                "status", "accepted",
                "run_id", runId,
                "event_id", eventId,
                "lifecycle", status
        );
    }

    public void recordCallback(String runId, String eventId, JsonNode callback) {
        recordCallback(runId, eventId, eventId, callback);
    }

    public synchronized Optional<RunRecord> findRun(String runId) {
        return Optional.ofNullable(runsById.get(runId));
    }

    public record RunRecord(
            String runId,
            String experimentId,
            String graphDigest,
            JsonNode state,
            Optional<JsonNode> terminalCallback
    ) {
    }

    private record AcceptedEvent(String eventId, String bodyDigest, Map<String, Object> response) {
    }

    public record CallbackResult(int status, String error, Map<String, Object> body) {
        static CallbackResult ok(Map<String, Object> body) {
            return new CallbackResult(202, null, body);
        }

        static CallbackResult idempotent(Map<String, Object> body) {
            return new CallbackResult(200, null, body);
        }

        static CallbackResult conflict(String error) {
            return new CallbackResult(409, error, Map.of("error", error, "message", error, "conflict", true));
        }

        static CallbackResult badRequest(String error) {
            return new CallbackResult(400, error, Map.of("error", error, "message", error));
        }
    }
}
