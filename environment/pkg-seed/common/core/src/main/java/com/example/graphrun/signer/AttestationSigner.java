package com.example.graphrun.signer;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.Signature;
import java.security.spec.PKCS8EncodedKeySpec;
import java.time.Instant;
import java.util.Base64;
import java.util.HashMap;
import java.util.Map;

public final class AttestationSigner {

    private final ObjectMapper mapper = new ObjectMapper();
    private final Path keyRoot;
    private final Path mlflowCache;

    public AttestationSigner(Path keyRoot, Path mlflowCache) {
        this.keyRoot = keyRoot;
        this.mlflowCache = mlflowCache;
    }

    public SignedAttestation sign(
            PolicyLoader.SigningPolicy policy,
            String policyDigest,
            String mlflowTarballSha256,
            String callbackSchemaSha256,
            String graphDigest,
            String runDigest,
            String terminalCallbackDigest,
            String signingKeyId
    ) {
        try {
            Map<String, Object> payload = new HashMap<>();
            payload.put("domain", policy.domains().getOrDefault("attestation", "GRAPHRUN.ATTEST.v1"));
            payload.put("policy_commit_id", policy.policyCommitId() != null ? policy.policyCommitId() : "unknown");
            payload.put("policy_digest", policyDigest);
            payload.put("policy_sha256", policyDigest);
            payload.put("mlflow_tarball_sha256", mlflowTarballSha256);
            payload.put("callback_schema_sha256", callbackSchemaSha256);
            payload.put("graph_digest", graphDigest);
            payload.put("run_digest", runDigest);
            payload.put("terminal_callback_digest", terminalCallbackDigest);
            payload.put("signing_key_id", signingKeyId);
            payload.put("attestation_schema_version", policy.attestationSchemaVersion());
            payload.put("generatedAt", Instant.now().toString());
            payload.put("mlflow_cache_path", mlflowCache.toAbsolutePath().toString());

            byte[] message = mapper.writeValueAsBytes(payload);
            PrivateKey privateKey = loadPrivateKey(signingKeyId);
            Signature signature = Signature.getInstance("Ed25519");
            signature.initSign(privateKey);
            signature.update(message);
            byte[] sig = signature.sign();

            return new SignedAttestation(payload, message, Base64.getEncoder().encodeToString(sig));
        } catch (Exception e) {
            throw new IllegalStateException("signing failed", e);
        }
    }

    private PrivateKey loadPrivateKey(String keyId) throws Exception {
        Path keyPath = keyRoot.resolve(keyId + ".pk8");
        byte[] encoded = Files.readAllBytes(keyPath);
        PKCS8EncodedKeySpec spec = new PKCS8EncodedKeySpec(encoded);
        return KeyFactory.getInstance("Ed25519").generatePrivate(spec);
    }

    public record SignedAttestation(Map<String, Object> fields, byte[] canonicalBytes, String signatureBase64) {
    }
}
