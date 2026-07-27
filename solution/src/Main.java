package com.acme.wallet.sdjwt;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.URLConnection;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.PrivateKey;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.TreeMap;

/** Releases the smallest presentation of every stored credential that a verifier's policy allows. */
public final class Main {

    private static final List<String> ALGORITHMS = List.of("RS256", "ES256");

    private String issuer;
    private String audience;
    private String nonce;
    private long instant;
    private PrivateKey holder;
    private String jwksUri;

    public static void main(String[] args) {
        try {
            System.exit(new Main().run(args));
        } catch (Exception failure) {
            System.err.println("broker: " + failure);
            System.exit(2);
        }
    }

    private int run(String[] args) throws Exception {
        Map<String, String> options = new LinkedHashMap<>();
        for (int i = 0; i + 1 < args.length; i += 2) {
            options.put(args[i], args[i + 1]);
        }
        Path configPath = Path.of(require(options, "--config"));
        Path credentialDir = Path.of(require(options, "--credentials"));
        Path policyPath = Path.of(require(options, "--policy"));
        Path outDir = Path.of(require(options, "--out"));

        Properties config = new Properties();
        try (InputStream stream = Files.newInputStream(configPath)) {
            config.load(stream);
        }
        issuer = config.getProperty("mp.jwt.verify.issuer");
        audience = config.getProperty("wallet.audience");
        nonce = config.getProperty("wallet.nonce");
        instant = Long.parseLong(config.getProperty("wallet.instant").trim());
        jwksUri = config.getProperty("mp.jwt.verify.publickey.location").trim();
        holder = Keys.privateKey(Json.object(Files.readString(Path.of(config.getProperty("wallet.holder.key")))));

        Map<String, Map<String, Object>> published = fetchKeys(jwksUri);
        Policy policy = new Policy(Json.object(Files.readString(policyPath)));

        Files.createDirectories(outDir.resolve("presentations"));
        List<Object> entries = new ArrayList<>();
        Map<String, String> credentials = new TreeMap<>(Json.BY_UTF8);
        try (var stream = Files.list(credentialDir)) {
            for (Path file : stream.filter(path -> path.toString().endsWith(".sdjwt")).toList()) {
                String name = file.getFileName().toString();
                credentials.put(name.substring(0, name.length() - ".sdjwt".length()), Files.readString(file).trim());
            }
        }
        for (Map.Entry<String, String> stored : credentials.entrySet()) {
            entries.add(evaluate(stored.getKey(), stored.getValue(), published, policy, outDir));
        }

        List<Object> keyList = new ArrayList<>();
        List<String> kids = new ArrayList<>(published.keySet());
        kids.sort(Json.BY_UTF8);
        for (String kid : kids) {
            Map<String, Object> entry = new LinkedHashMap<>();
            entry.put("kid", kid);
            entry.put("thumbprint", Keys.thumbprint(published.get(kid)));
            keyList.add(entry);
        }
        Map<String, Object> report = new LinkedHashMap<>();
        report.put("jwks_uri", jwksUri);
        report.put("keys", keyList);
        report.put("credentials", entries);
        Files.write(outDir.resolve("report.json"), Json.write(report).getBytes(StandardCharsets.UTF_8));
        return 0;
    }

    private static String require(Map<String, String> options, String name) {
        String value = options.get(name);
        if (value == null) {
            throw new IllegalArgumentException("missing " + name);
        }
        return value;
    }

    /** Read the issuer's published JWK Set and keep the keys this profile can verify with. */
    private static Map<String, Map<String, Object>> fetchKeys(String location) throws IOException {
        String body;
        if (location.startsWith("http://") || location.startsWith("https://") || location.startsWith("file:")) {
            URLConnection connection = URI.create(location).toURL().openConnection();
            connection.setConnectTimeout(30000);
            connection.setReadTimeout(30000);
            try (InputStream stream = connection.getInputStream()) {
                body = new String(stream.readAllBytes(), StandardCharsets.UTF_8);
            }
        } else {
            body = Files.readString(Path.of(location));
        }
        Map<String, Object> document = Json.object(body);
        Map<String, Map<String, Object>> usable = new LinkedHashMap<>();
        Object keys = document.get("keys");
        if (!(keys instanceof List)) {
            throw new IOException("key set has no keys");
        }
        for (Object item : (List<?>) keys) {
            if (!(item instanceof Map)) {
                continue;
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> jwk = (Map<String, Object>) item;
            if (!(jwk.get("kid") instanceof String) || "enc".equals(jwk.get("use"))) {
                continue;
            }
            Object alg = jwk.get("alg");
            if (alg != null && !ALGORITHMS.contains(alg)) {
                continue;
            }
            boolean rsa = "RSA".equals(jwk.get("kty")) && jwk.get("n") instanceof String && jwk.get("e") instanceof String;
            boolean ec = "EC".equals(jwk.get("kty")) && "P-256".equals(jwk.get("crv"));
            if (rsa || ec) {
                usable.put((String) jwk.get("kid"), jwk);
            }
        }
        return usable;
    }

    /** The published keys that can serve one signature algorithm. */
    private static Map<String, Map<String, Object>> serving(Map<String, Map<String, Object>> published, String alg) {
        String kty = "RS256".equals(alg) ? "RSA" : "EC";
        Map<String, Map<String, Object>> out = new LinkedHashMap<>();
        for (Map.Entry<String, Map<String, Object>> entry : published.entrySet()) {
            Map<String, Object> jwk = entry.getValue();
            Object declared = jwk.get("alg");
            if (kty.equals(jwk.get("kty")) && (declared == null || declared.equals(alg))) {
                out.put(entry.getKey(), jwk);
            }
        }
        return out;
    }

    /** Run one credential through the acceptance ladder and release it when the policy allows. */
    private Map<String, Object> evaluate(
            String id, String text, Map<String, Map<String, Object>> published, Policy policy, Path outDir) {
        Map<String, Object> entry = new LinkedHashMap<>();
        entry.put("id", id);
        try {
            Credential credential = new Credential(id, text);
            Object alg = credential.header.get("alg");
            if (!(alg instanceof String) || !ALGORITHMS.contains(alg) || credential.header.containsKey("crit")) {
                throw new Credential.Rejected("unsupported_algorithm");
            }
            if (!"sha-256".equals(credential.digestAlgorithm())) {
                throw new Credential.Rejected("unsupported_algorithm");
            }
            Map<String, Map<String, Object>> candidates = serving(published, (String) alg);
            Object kid = credential.header.get("kid");
            Map<String, Object> jwk;
            String verifyingKid;
            if (kid == null) {
                if (candidates.size() != 1) {
                    throw new Credential.Rejected("unknown_key");
                }
                verifyingKid = candidates.keySet().iterator().next();
                jwk = candidates.get(verifyingKid);
            } else {
                verifyingKid = String.valueOf(kid);
                jwk = candidates.get(verifyingKid);
            }
            if (jwk == null) {
                throw new Credential.Rejected("unknown_key");
            }
            if (!Keys.verify(credential.jwt, jwk, (String) alg)) {
                throw new Credential.Rejected("bad_signature");
            }
            Map<String, Object> resolved = credential.resolve();
            if (!(resolved.get("iss") instanceof String)
                    || !(resolved.get("iat") instanceof Long)
                    || !(resolved.get("exp") instanceof Long)
                    || principal(resolved) == null
                    || !holderBound(resolved)) {
                throw new Credential.Rejected("missing_claim");
            }
            if (!resolved.get("iss").equals(issuer)) {
                throw new Credential.Rejected("invalid_issuer");
            }
            if ((Long) resolved.get("exp") <= instant) {
                throw new Credential.Rejected("expired");
            }
            Policy.Release release = policy.release(resolved, credential.paths());
            if (!release.missing.isEmpty()) {
                entry.put("status", "insufficient");
                entry.put("missing", release.missing);
                return entry;
            }
            List<String> released = new ArrayList<>();
            for (String path : release.paths) {
                released.add(credential.textOf(credential.paths().get(path)));
            }
            released.sort(Json.BY_UTF8);
            StringBuilder prefix = new StringBuilder(credential.jwt).append('~');
            for (String disclosure : released) {
                prefix.append(disclosure).append('~');
            }
            String sdHash = Codec.encode(
                    Codec.sha256(prefix.toString().getBytes(StandardCharsets.US_ASCII)));
            writePresentation(outDir, id, prefix.toString(), sdHash);

            List<String> disclosed = new ArrayList<>(release.paths);
            disclosed.sort(Json.BY_UTF8);
            entry.put("status", "presented");
            entry.put("alg", alg);
            entry.put("kid", verifyingKid);
            entry.put("name", principal(resolved));
            entry.put("groups", groups(resolved));
            entry.put("disclosed", disclosed);
            entry.put("sd_hash", sdHash);
            return entry;
        } catch (Credential.Rejected rejected) {
            entry.put("status", rejected.status);
            return entry;
        } catch (RuntimeException broken) {
            entry.put("status", "malformed");
            return entry;
        } catch (Exception failure) {
            throw new IllegalStateException(failure);
        }
    }

    private void writePresentation(Path outDir, String id, String prefix, String sdHash) throws Exception {
        Map<String, Object> header = new LinkedHashMap<>();
        header.put("alg", "ES256");
        header.put("typ", "kb+jwt");
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("aud", audience);
        payload.put("iat", instant);
        payload.put("nonce", nonce);
        payload.put("sd_hash", sdHash);
        String presentation = prefix + Keys.signEs256(holder, header, payload);
        Files.write(
                outDir.resolve("presentations").resolve(id + ".sdjwt"),
                presentation.getBytes(StandardCharsets.UTF_8));
    }

    private static String principal(Map<String, Object> resolved) {
        for (String claim : List.of("upn", "preferred_username", "sub")) {
            Object value = resolved.get(claim);
            if (value instanceof String) {
                return (String) value;
            }
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    private static boolean holderBound(Map<String, Object> resolved) {
        Object confirmation = resolved.get("cnf");
        return confirmation instanceof Map && ((Map<String, Object>) confirmation).get("jwk") instanceof Map;
    }

    @SuppressWarnings("unchecked")
    private static List<String> groups(Map<String, Object> resolved) {
        List<String> out = new ArrayList<>();
        Object claim = resolved.get("groups");
        if (claim instanceof List) {
            for (Object item : (List<Object>) claim) {
                out.add(String.valueOf(item));
            }
        }
        out.sort(Json.BY_UTF8);
        return out;
    }
}
