package com.acme.inbox.jwe;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * A parsed JWE in any of the three JOSE serializations (compact, flattened JSON, general JSON).
 * Parsing only validates structure; the header fields (alg, enc, epk, apu, apv, skid) live in the
 * integrity-protected header, and each recipient carries its own key id and wrapped content key.
 */
final class Jwe {

    static final class Recipient {
        final String kid;
        final byte[] encryptedKey;

        Recipient(String kid, byte[] encryptedKey) {
            this.kid = kid;
            this.encryptedKey = encryptedKey;
        }
    }

    final String protectedB64;
    final Map<String, Object> header;
    final byte[] iv;
    final byte[] ciphertext;
    final byte[] tag;
    final String aadB64;
    final List<Recipient> recipients;

    private Jwe(String protectedB64, Map<String, Object> header, byte[] iv, byte[] ciphertext,
                byte[] tag, String aadB64, List<Recipient> recipients) {
        this.protectedB64 = protectedB64;
        this.header = header;
        this.iv = iv;
        this.ciphertext = ciphertext;
        this.tag = tag;
        this.aadB64 = aadB64;
        this.recipients = recipients;
    }

    /** The Additional Authenticated Data per RFC 7516: the protected header, plus the AAD when present. */
    byte[] aad() {
        String ascii = aadB64 == null ? protectedB64 : protectedB64 + "." + aadB64;
        return ascii.getBytes(StandardCharsets.US_ASCII);
    }

    /** Parses one message line, returning null when it is not a structurally valid JWE. */
    static Jwe parse(String line) {
        String trimmed = line.trim();
        try {
            if (trimmed.startsWith("{")) {
                return parseJson(trimmed);
            }
            return parseCompact(trimmed);
        } catch (RuntimeException e) {
            return null;
        }
    }

    @SuppressWarnings("unchecked")
    private static Jwe parseJson(String text) {
        Object parsed = Json.parse(text);
        if (!(parsed instanceof Map)) {
            return null;
        }
        Map<String, Object> object = (Map<String, Object>) parsed;
        String protectedB64 = str(object.get("protected"));
        if (protectedB64 == null) {
            return null;
        }
        Map<String, Object> header = decodeHeader(protectedB64);
        if (header == null) {
            return null;
        }
        byte[] iv = decode(object.get("iv"));
        byte[] ciphertext = decode(object.get("ciphertext"));
        byte[] tag = decode(object.get("tag"));
        if (iv == null || ciphertext == null || tag == null) {
            return null;
        }
        String aadB64 = str(object.get("aad"));

        List<Recipient> recipients = new ArrayList<>();
        Object recipientList = object.get("recipients");
        if (recipientList instanceof List) {
            for (Object item : (List<Object>) recipientList) {
                if (!(item instanceof Map)) {
                    continue;
                }
                Map<String, Object> entry = (Map<String, Object>) item;
                byte[] encryptedKey = decode(entry.get("encrypted_key"));
                if (encryptedKey == null) {
                    continue;
                }
                recipients.add(new Recipient(recipientKid(header, entry.get("header")), encryptedKey));
            }
        } else {
            byte[] encryptedKey = decode(object.get("encrypted_key"));
            if (encryptedKey != null) {
                recipients.add(new Recipient(recipientKid(header, object.get("header")), encryptedKey));
            }
        }
        if (recipients.isEmpty()) {
            return null;
        }
        return new Jwe(protectedB64, header, iv, ciphertext, tag, aadB64, recipients);
    }

    private static Jwe parseCompact(String text) {
        String[] parts = text.split("\\.", -1);
        if (parts.length != 5) {
            return null;
        }
        Map<String, Object> header = decodeHeader(parts[0]);
        if (header == null) {
            return null;
        }
        byte[] encryptedKey = decode(parts[1]);
        byte[] iv = decode(parts[2]);
        byte[] ciphertext = decode(parts[3]);
        byte[] tag = decode(parts[4]);
        if (encryptedKey == null || iv == null || ciphertext == null || tag == null) {
            return null;
        }
        List<Recipient> recipients = new ArrayList<>();
        recipients.add(new Recipient(str(header.get("kid")), encryptedKey));
        return new Jwe(parts[0], header, iv, ciphertext, tag, null, recipients);
    }

    @SuppressWarnings("unchecked")
    private static String recipientKid(Map<String, Object> protectedHeader, Object recipientHeader) {
        if (recipientHeader instanceof Map && ((Map<String, Object>) recipientHeader).get("kid") != null) {
            return str(((Map<String, Object>) recipientHeader).get("kid"));
        }
        return str(protectedHeader.get("kid"));
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> decodeHeader(String b64) {
        byte[] raw = decode(b64);
        if (raw == null) {
            return null;
        }
        Object parsed = Json.parse(new String(raw, StandardCharsets.UTF_8));
        if (!(parsed instanceof Map)) {
            return null;
        }
        return (Map<String, Object>) parsed;
    }

    private static byte[] decode(Object value) {
        if (!(value instanceof String)) {
            return null;
        }
        try {
            return Jose.b64uDecode((String) value);
        } catch (IllegalArgumentException e) {
            return null;
        }
    }

    private static String str(Object value) {
        return value instanceof String ? (String) value : null;
    }
}
