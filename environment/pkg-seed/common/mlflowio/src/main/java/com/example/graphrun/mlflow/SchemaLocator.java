package com.example.graphrun.mlflow;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.networknt.schema.JsonSchema;
import com.networknt.schema.JsonSchemaFactory;
import com.networknt.schema.SpecVersion;
import com.networknt.schema.ValidationMessage;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.util.Optional;
import java.util.Set;

public final class SchemaLocator {

    private static final String SCHEMA_REL = "mlflow/server/graphql/schemas/run_callback.schema.json";
    private final Path mlflowCache;
    private final ObjectMapper mapper = new ObjectMapper();

    public SchemaLocator(Path mlflowCache) {
        this.mlflowCache = mlflowCache;
    }

    public Path requireSchemaPath() {
        Path marker = mlflowCache.resolve("schema.path");
        if (!Files.isRegularFile(marker)) {
            throw new IllegalStateException("schema_validation_failed: schema.path missing; run fetch-mlflow-release.sh");
        }
        try {
            String pathText = Files.readString(marker).trim();
            Path schemaPath = Path.of(pathText).toAbsolutePath().normalize();
            Path cacheRoot = mlflowCache.toAbsolutePath().normalize();
            if (!schemaPath.startsWith(cacheRoot)) {
                throw new IllegalStateException("schema_validation_failed: schema path escapes cache root");
            }
            if (!Files.isRegularFile(schemaPath)) {
                throw new IllegalStateException("schema_validation_failed: schema file missing");
            }
            return schemaPath;
        } catch (IllegalStateException e) {
            throw e;
        } catch (Exception e) {
            throw new IllegalStateException("schema_validation_failed: unable to read schema.path", e);
        }
    }

    public void validate(JsonNode callback) {
        Path schemaPath = requireSchemaPath();
        try {
            JsonNode schemaNode = mapper.readTree(Files.readAllBytes(schemaPath));
            JsonSchemaFactory factory = JsonSchemaFactory.getInstance(SpecVersion.VersionFlag.V7);
            JsonSchema schema = factory.getSchema(schemaNode);
            Set<ValidationMessage> errors = schema.validate(callback);
            if (!errors.isEmpty()) {
                throw new IllegalArgumentException("schema_validation_failed");
            }
        } catch (IllegalArgumentException e) {
            throw e;
        } catch (Exception e) {
            throw new IllegalStateException("schema_validation_failed", e);
        }
    }

    public String schemaDigest() {
        try {
            return sha256Hex(Files.readAllBytes(requireSchemaPath()));
        } catch (Exception e) {
            throw new IllegalStateException("schema_validation_failed", e);
        }
    }

    public Optional<Path> locateReleaseSchema(String ignored) {
        try {
            return Optional.of(requireSchemaPath());
        } catch (RuntimeException e) {
            return Optional.empty();
        }
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
