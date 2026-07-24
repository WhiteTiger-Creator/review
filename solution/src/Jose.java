package com.acme.inbox.jwe;

import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.AlgorithmParameters;
import java.security.KeyFactory;
import java.security.MessageDigest;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.spec.ECGenParameterSpec;
import java.security.spec.ECParameterSpec;
import java.security.spec.ECPoint;
import java.security.spec.ECPrivateKeySpec;
import java.security.spec.ECPublicKeySpec;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;

import javax.crypto.Cipher;
import javax.crypto.KeyAgreement;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;

/**
 * JDK-only JOSE primitives: base64url, P-256 JWK conversion, RFC 7638 thumbprints, the ECDH-1PU key
 * agreement, the NIST SP 800-56A Concat KDF, AES key unwrap and AES-GCM content decryption. No
 * third-party JOSE, JWT or crypto code is used anywhere.
 */
final class Jose {

    private static final Base64.Decoder URL_DECODER = Base64.getUrlDecoder();

    private Jose() {
    }

    static byte[] b64uDecode(String value) {
        return URL_DECODER.decode(value);
    }

    static String b64uEncode(byte[] value) {
        return Base64.getUrlEncoder().withoutPadding().encodeToString(value);
    }

    private static ECParameterSpec p256() {
        try {
            AlgorithmParameters params = AlgorithmParameters.getInstance("EC");
            params.init(new ECGenParameterSpec("secp256r1"));
            return params.getParameterSpec(ECParameterSpec.class);
        } catch (Exception e) {
            throw new IllegalStateException("P-256 parameters unavailable", e);
        }
    }

    private static BigInteger coordinate(String b64u) {
        return new BigInteger(1, b64uDecode(b64u));
    }

    /** Builds the public EC key of a P-256 JWK, or throws if the members are missing or off-curve. */
    static PublicKey ecPublic(Map<String, Object> jwk) throws Exception {
        ECPoint point = new ECPoint(coordinate((String) jwk.get("x")), coordinate((String) jwk.get("y")));
        ECPublicKeySpec spec = new ECPublicKeySpec(point, p256());
        return KeyFactory.getInstance("EC").generatePublic(spec);
    }

    /** Builds the private EC key of a P-256 JWK that carries the private value d. */
    static PrivateKey ecPrivate(Map<String, Object> jwk) throws Exception {
        ECPrivateKeySpec spec = new ECPrivateKeySpec(coordinate((String) jwk.get("d")), p256());
        return KeyFactory.getInstance("EC").generatePrivate(spec);
    }

    static boolean isP256(Map<String, Object> jwk) {
        return jwk != null
                && "EC".equals(jwk.get("kty"))
                && "P-256".equals(jwk.get("crv"))
                && jwk.get("x") instanceof String
                && jwk.get("y") instanceof String;
    }

    /** RFC 7638 SHA-256 thumbprint of a P-256 key: the required members only, ordered, no whitespace. */
    static String thumbprint(Map<String, Object> jwk) throws Exception {
        Map<String, Object> required = new LinkedHashMap<>();
        required.put("crv", jwk.get("crv"));
        required.put("kty", "EC");
        required.put("x", jwk.get("x"));
        required.put("y", jwk.get("y"));
        byte[] canonical = Json.canonical(required).getBytes(StandardCharsets.UTF_8);
        return b64uEncode(sha256(canonical));
    }

    static byte[] sha256(byte[] data) throws Exception {
        return MessageDigest.getInstance("SHA-256").digest(data);
    }

    /** The raw ECDH shared secret Z (the agreed X coordinate) between a private and a public key. */
    static byte[] ecdh(PrivateKey privateKey, PublicKey publicKey) throws Exception {
        KeyAgreement agreement = KeyAgreement.getInstance("ECDH");
        agreement.init(privateKey);
        agreement.doPhase(publicKey, true);
        return agreement.generateSecret();
    }

    /**
     * The NIST SP 800-56A Concat KDF with SHA-256, a single repetition for a 256-bit output:
     * SHA-256( 0x00000001 || Z || len(algID)||algID || len(apu)||apu || len(apv)||apv || keydatalen ).
     * algID, apu and apv are supplied as raw bytes; keydatalen is the number of key bits (256).
     */
    static byte[] concatKdf(byte[] z, byte[] algorithmId, byte[] apu, byte[] apv, int keyDataLenBits)
            throws Exception {
        java.io.ByteArrayOutputStream buffer = new java.io.ByteArrayOutputStream();
        buffer.write(uint32(1));
        buffer.write(z);
        buffer.write(uint32(algorithmId.length));
        buffer.write(algorithmId);
        buffer.write(uint32(apu.length));
        buffer.write(apu);
        buffer.write(uint32(apv.length));
        buffer.write(apv);
        buffer.write(uint32(keyDataLenBits));
        byte[] digest = sha256(buffer.toByteArray());
        int bytes = keyDataLenBits / 8;
        byte[] out = new byte[bytes];
        System.arraycopy(digest, 0, out, 0, bytes);
        return out;
    }

    private static byte[] uint32(int value) {
        return new byte[] {
            (byte) (value >>> 24), (byte) (value >>> 16), (byte) (value >>> 8), (byte) value
        };
    }

    /** RFC 3394 AES key unwrap of a wrapped CEK under the KEK; throws when the integrity check fails. */
    static byte[] aesUnwrap(byte[] kek, byte[] wrapped) throws Exception {
        Cipher cipher = Cipher.getInstance("AESWrap");
        cipher.init(Cipher.UNWRAP_MODE, new SecretKeySpec(kek, "AES"));
        return cipher.unwrap(wrapped, "AES", Cipher.SECRET_KEY).getEncoded();
    }

    /** AES-256-GCM decryption with a 128-bit tag; throws when the tag does not authenticate. */
    static byte[] aesGcmDecrypt(byte[] cek, byte[] iv, byte[] ciphertext, byte[] tag, byte[] aad)
            throws Exception {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, new SecretKeySpec(cek, "AES"), new GCMParameterSpec(128, iv));
        cipher.updateAAD(aad);
        byte[] input = new byte[ciphertext.length + tag.length];
        System.arraycopy(ciphertext, 0, input, 0, ciphertext.length);
        System.arraycopy(tag, 0, input, ciphertext.length, tag.length);
        return cipher.doFinal(input);
    }
}
