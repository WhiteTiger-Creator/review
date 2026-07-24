package com.acme.inbox.jwe;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The Acme inbox JWE unsealer. Reads authenticated ECDH-1PU JWE messages, unseals each one with the
 * recipient's private key and the sender's static public key resolved from the registry, and writes
 * a canonical JSON report plus a transcript digest. All JOSE and key-agreement work uses JDK crypto.
 */
public final class Main {

    private static final String ALG = "ECDH-1PU+A256KW";
    private static final String ENC = "A256GCM";

    private Main() {
    }

    public static void main(String[] args) throws Exception {
        Map<String, String> options = parseArgs(args);
        Map<String, PrivateKey> recipientKeys = loadRecipientKeys(options.get("keys"));
        Registry registry = new Registry(loadSenders(options.get("senders")));
        List<String> messages = loadMessages(options.get("messages"));

        List<Map<String, Object>> results = new ArrayList<>();
        List<byte[]> plaintexts = new ArrayList<>();
        for (int index = 0; index < messages.size(); index++) {
            Outcome outcome = unseal(messages.get(index), recipientKeys, registry);
            results.add(outcome.toResult(index));
            plaintexts.add(outcome.plaintext);
        }

        Map<String, Object> report = new LinkedHashMap<>();
        report.put("results", results);
        Files.write(Path.of(options.get("out")), Json.canonical(report).getBytes(StandardCharsets.UTF_8));

        Files.write(Path.of(options.get("digest")),
                (transcriptDigest(results, plaintexts) + "\n").getBytes(StandardCharsets.US_ASCII));
    }

    /** The seven-way verdict ladder, in order; the first failing stage decides the message. */
    @SuppressWarnings("unchecked")
    private static Outcome unseal(String line, Map<String, PrivateKey> recipientKeys, Registry registry) {
        Jwe jwe = Jwe.parse(line);
        if (jwe == null) {
            return Outcome.status("malformed");
        }
        Map<String, Object> header = jwe.header;
        if (!ALG.equals(header.get("alg")) || !ENC.equals(header.get("enc"))) {
            return Outcome.status("unsupported_algorithm");
        }
        Object epk = header.get("epk");
        if (!(epk instanceof Map) || !Jose.isP256((Map<String, Object>) epk)) {
            return Outcome.status("unsupported_algorithm");
        }
        PublicKey ephemeral;
        try {
            ephemeral = Jose.ecPublic((Map<String, Object>) epk);
        } catch (Exception e) {
            return Outcome.status("unsupported_algorithm");
        }

        Jwe.Recipient matched = null;
        for (Jwe.Recipient recipient : jwe.recipients) {
            if (recipient.kid != null && recipientKeys.containsKey(recipient.kid)) {
                matched = recipient;
                break;
            }
        }
        if (matched == null) {
            return Outcome.status("no_recipient");
        }
        Outcome outcome = new Outcome();
        outcome.status = "unknown_sender";
        outcome.recipientKid = matched.kid;

        Object skid = header.get("skid");
        if (!(skid instanceof String)) {
            return outcome;
        }
        Map<String, Object> senderJwk = registry.resolve((String) skid);
        if (senderJwk == null) {
            return outcome;
        }
        PublicKey senderKey;
        try {
            senderKey = Jose.ecPublic(senderJwk);
            outcome.senderKid = (String) skid;
            outcome.senderThumbprint = Jose.thumbprint(senderJwk);
        } catch (Exception e) {
            return outcome;
        }

        try {
            byte[] ze = Jose.ecdh(recipientKeys.get(matched.kid), ephemeral);
            byte[] zs = Jose.ecdh(recipientKeys.get(matched.kid), senderKey);
            byte[] z = concat(ze, zs);
            byte[] apu = header.containsKey("apu") ? Jose.b64uDecode((String) header.get("apu")) : new byte[0];
            byte[] apv = header.containsKey("apv") ? Jose.b64uDecode((String) header.get("apv")) : new byte[0];
            byte[] kek = Jose.concatKdf(z, ALG.getBytes(StandardCharsets.US_ASCII), apu, apv, 256);

            byte[] cek;
            try {
                cek = Jose.aesUnwrap(kek, matched.encryptedKey);
            } catch (Exception e) {
                outcome.status = "bad_key";
                return outcome;
            }

            byte[] plaintext;
            try {
                plaintext = Jose.aesGcmDecrypt(cek, jwe.iv, jwe.ciphertext, jwe.tag, jwe.aad());
            } catch (Exception e) {
                outcome.status = "bad_tag";
                return outcome;
            }

            outcome.status = "unsealed";
            outcome.plaintext = plaintext;
            fillPrincipal(outcome, plaintext);
            return outcome;
        } catch (Exception e) {
            outcome.status = "bad_key";
            return outcome;
        }
    }

    @SuppressWarnings("unchecked")
    private static void fillPrincipal(Outcome outcome, byte[] plaintext) {
        Object parsed;
        try {
            parsed = Json.parse(new String(plaintext, StandardCharsets.UTF_8));
        } catch (RuntimeException e) {
            parsed = null;
        }
        Map<String, Object> claims = parsed instanceof Map ? (Map<String, Object>) parsed : Map.of();
        outcome.name = firstString(claims.get("upn"), claims.get("preferred_username"), claims.get("sub"));
        outcome.sub = claims.get("sub") instanceof String ? (String) claims.get("sub") : null;
        List<String> groups = new ArrayList<>();
        if (claims.get("groups") instanceof List) {
            for (Object group : (List<Object>) claims.get("groups")) {
                if (group instanceof String) {
                    groups.add((String) group);
                }
            }
        }
        groups.sort(Json::compareUtf8);
        outcome.groups = groups;
    }

    private static String firstString(Object... candidates) {
        for (Object candidate : candidates) {
            if (candidate instanceof String) {
                return (String) candidate;
            }
        }
        return null;
    }

    private static String transcriptDigest(List<Map<String, Object>> results, List<byte[]> plaintexts)
            throws Exception {
        ByteArrayOutputStream stream = new ByteArrayOutputStream();
        for (int i = 0; i < results.size(); i++) {
            stream.write(((String) results.get(i).get("status")).getBytes(StandardCharsets.US_ASCII));
            stream.write('\n');
            if ("unsealed".equals(results.get(i).get("status"))) {
                stream.write(plaintexts.get(i));
                stream.write('\n');
            }
        }
        return toHex(Jose.sha256(stream.toByteArray()));
    }

    private static String toHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            sb.append(Character.forDigit((b >> 4) & 0xf, 16));
            sb.append(Character.forDigit(b & 0xf, 16));
        }
        return sb.toString();
    }

    private static byte[] concat(byte[] a, byte[] b) {
        byte[] out = new byte[a.length + b.length];
        System.arraycopy(a, 0, out, 0, a.length);
        System.arraycopy(b, 0, out, a.length, b.length);
        return out;
    }

    // ---- input loading ----

    @SuppressWarnings("unchecked")
    private static Map<String, PrivateKey> loadRecipientKeys(String path) throws Exception {
        Map<String, PrivateKey> keys = new LinkedHashMap<>();
        Object parsed = Json.parse(Files.readString(Path.of(path)));
        Object list = parsed instanceof Map ? ((Map<String, Object>) parsed).get("keys") : null;
        if (list instanceof List) {
            for (Object item : (List<Object>) list) {
                if (!(item instanceof Map)) {
                    continue;
                }
                Map<String, Object> jwk = (Map<String, Object>) item;
                if (Jose.isP256(jwk) && jwk.get("d") instanceof String && jwk.get("kid") instanceof String) {
                    try {
                        keys.put((String) jwk.get("kid"), Jose.ecPrivate(jwk));
                    } catch (Exception ignored) {
                        // a malformed private key is simply not held
                    }
                }
            }
        }
        return keys;
    }

    @SuppressWarnings("unchecked")
    private static Map<String, String> loadSenders(String path) throws Exception {
        Map<String, String> senders = new LinkedHashMap<>();
        Object parsed = Json.parse(Files.readString(Path.of(path)));
        Object map = parsed instanceof Map ? ((Map<String, Object>) parsed).get("senders") : null;
        if (map instanceof Map) {
            for (Map.Entry<String, Object> entry : ((Map<String, Object>) map).entrySet()) {
                if (entry.getValue() instanceof String) {
                    senders.put(entry.getKey(), (String) entry.getValue());
                }
            }
        }
        return senders;
    }

    private static List<String> loadMessages(String path) throws Exception {
        List<String> messages = new ArrayList<>();
        for (String line : Files.readString(Path.of(path)).split("\n", -1)) {
            if (!line.trim().isEmpty()) {
                messages.add(line);
            }
        }
        return messages;
    }

    private static Map<String, String> parseArgs(String[] args) {
        Map<String, String> options = new LinkedHashMap<>();
        for (int i = 0; i + 1 < args.length; i += 2) {
            if (args[i].startsWith("--")) {
                options.put(args[i].substring(2), args[i + 1]);
            }
        }
        for (String required : new String[] {"keys", "senders", "messages", "out", "digest"}) {
            if (!options.containsKey(required)) {
                throw new IllegalArgumentException("missing --" + required);
            }
        }
        return options;
    }

    /** The result of unsealing one message; which fields are set depends on how far it got. */
    private static final class Outcome {
        String status;
        String recipientKid;
        String senderKid;
        String senderThumbprint;
        String name;
        String sub;
        List<String> groups;
        byte[] plaintext;

        static Outcome status(String status) {
            Outcome outcome = new Outcome();
            outcome.status = status;
            return outcome;
        }

        Map<String, Object> toResult(int index) {
            Map<String, Object> result = new LinkedHashMap<>();
            result.put("index", index);
            result.put("status", status);
            if (recipientKid != null) {
                result.put("recipient_kid", recipientKid);
            }
            if (senderKid != null) {
                result.put("sender_kid", senderKid);
                result.put("sender_thumbprint", senderThumbprint);
            }
            if ("unsealed".equals(status)) {
                result.put("name", name);
                result.put("sub", sub);
                result.put("groups", groups);
            }
            return result;
        }
    }
}
