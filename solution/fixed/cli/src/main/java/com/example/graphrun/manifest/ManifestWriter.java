package com.example.graphrun.manifest;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

public final class ManifestWriter {

    private final ObjectMapper mapper;

    public ManifestWriter() {
        this.mapper = new ObjectMapper();
        this.mapper.configure(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true);
    }

    public void write(Path outputDir, Map<String, String> artifacts) {
        throw new UnsupportedOperationException("use writeSigningManifest");
    }

    public void writeSigningManifest(
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
    ) {
        try {
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
            Path tmp = target.resolveSibling(target.getFileName().toString() + ".tmp");
            Files.createDirectories(target.getParent());
            byte[] bytes = (mapper.writeValueAsString(manifest) + "\n").getBytes(StandardCharsets.UTF_8);
            Files.write(tmp, bytes);
            Files.move(tmp, target, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (Exception e) {
            throw new IllegalStateException("manifest write failed", e);
        }
    }
}
