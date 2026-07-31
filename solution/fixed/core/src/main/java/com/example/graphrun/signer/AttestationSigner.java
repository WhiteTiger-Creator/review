package com.example.graphrun.signer;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.Signature;
import java.security.spec.PKCS8EncodedKeySpec;
import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class AttestationSigner {

    private final Path keyRoot;

    public AttestationSigner(Path keyRoot) {
        this.keyRoot = keyRoot;
    }

    public AttestationSigner(Path keyRoot, Path ignoredMlflowCache) {
        this(keyRoot);
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
            String domain = policy.domains().getOrDefault("attestation", "GRAPHRUN.ATTEST.v1");
            String policyCommitId = policy.policyCommitId();
            if (policyCommitId == null || policyCommitId.isBlank()) {
                throw new IllegalStateException("policy_commit_id missing");
            }

            List<String> fields = new ArrayList<>();
            fields.add(domain);
            fields.add(policyCommitId);
            fields.add(policyDigest);
            fields.add(mlflowTarballSha256);
            fields.add(callbackSchemaSha256);
            fields.add(graphDigest);
            fields.add(runDigest);
            fields.add(terminalCallbackDigest);
            fields.add(signingKeyId);
            fields.add(policy.attestationSchemaVersion());

            byte[] message = CanonicalBytes.frame(fields);
            PrivateKey privateKey = loadPrivateKey(signingKeyId);
            Signature signature = Signature.getInstance("Ed25519");
            signature.initSign(privateKey);
            signature.update(message);
            byte[] sig = signature.sign();

            Map<String, Object> output = new LinkedHashMap<>();
            output.put("attestation_schema_version", policy.attestationSchemaVersion());
            output.put("callback_schema_sha256", callbackSchemaSha256);
            output.put("graph_digest", graphDigest);
            output.put("mlflow_tarball_sha256", mlflowTarballSha256);
            output.put("policy_commit_id", policyCommitId);
            output.put("policy_digest", policyDigest);
            output.put("run_digest", runDigest);
            output.put("signature", Base64.getEncoder().encodeToString(sig));
            output.put("signing_key_id", signingKeyId);
            output.put("terminal_callback_digest", terminalCallbackDigest);

            return new SignedAttestation(output, message, Base64.getEncoder().encodeToString(sig));
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
