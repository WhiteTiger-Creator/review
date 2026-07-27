package com.acme.wallet.sdjwt;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Base64;

/** Base64url and digest helpers shared by the credential and presentation code. */
final class Codec {

    private static final Base64.Encoder ENCODER = Base64.getUrlEncoder().withoutPadding();
    private static final Base64.Decoder DECODER = Base64.getUrlDecoder();

    private Codec() {
    }

    /** True when the text is a non-empty unpadded base64url segment. */
    static boolean isBase64Url(String text) {
        if (text.isEmpty()) {
            return false;
        }
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            boolean ok = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')
                    || c == '-' || c == '_';
            if (!ok) {
                return false;
            }
        }
        return true;
    }

    static String encode(byte[] raw) {
        return ENCODER.encodeToString(raw);
    }

    static byte[] decode(String text) {
        return DECODER.decode(text);
    }

    /** Decode a base64url segment as UTF-8 text. */
    static String decodeText(String text) {
        return new String(decode(text), StandardCharsets.UTF_8);
    }

    static byte[] sha256(byte[] input) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(input);
        } catch (NoSuchAlgorithmException impossible) {
            throw new IllegalStateException(impossible);
        }
    }

    /** The SD-JWT digest of a disclosure, taken over the characters as received. */
    static String digest(String disclosure) {
        return encode(sha256(disclosure.getBytes(StandardCharsets.US_ASCII)));
    }
}
