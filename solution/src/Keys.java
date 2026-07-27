package com.acme.wallet.sdjwt;

import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.AlgorithmParameters;
import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.ECGenParameterSpec;
import java.security.spec.ECParameterSpec;
import java.security.spec.ECPoint;
import java.security.spec.ECPrivateKeySpec;
import java.security.spec.ECPublicKeySpec;
import java.security.spec.RSAPublicKeySpec;
import java.util.LinkedHashMap;
import java.util.Map;

/** JWK handling: public keys, RFC 7638 thumbprints, and the two signature algorithms in play. */
final class Keys {

    private Keys() {
    }

    private static BigInteger unsigned(String value) {
        return new BigInteger(1, Codec.decode(value));
    }

    private static ECParameterSpec p256() throws Exception {
        AlgorithmParameters parameters = AlgorithmParameters.getInstance("EC");
        parameters.init(new ECGenParameterSpec("secp256r1"));
        return parameters.getParameterSpec(ECParameterSpec.class);
    }

    /** Build the public key a published JWK stands for. */
    static PublicKey publicKey(Map<String, Object> jwk) throws Exception {
        String kty = (String) jwk.get("kty");
        if ("RSA".equals(kty)) {
            RSAPublicKeySpec spec = new RSAPublicKeySpec(
                    unsigned((String) jwk.get("n")), unsigned((String) jwk.get("e")));
            return KeyFactory.getInstance("RSA").generatePublic(spec);
        }
        ECPoint point = new ECPoint(unsigned((String) jwk.get("x")), unsigned((String) jwk.get("y")));
        return KeyFactory.getInstance("EC").generatePublic(new ECPublicKeySpec(point, p256()));
    }

    /** Build the holder's signing key from its private JWK. */
    static PrivateKey privateKey(Map<String, Object> jwk) throws Exception {
        ECPrivateKeySpec spec = new ECPrivateKeySpec(unsigned((String) jwk.get("d")), p256());
        return KeyFactory.getInstance("EC").generatePrivate(spec);
    }

    /** RFC 7638 thumbprint of a published JWK. */
    static String thumbprint(Map<String, Object> jwk) {
        Map<String, Object> required = new LinkedHashMap<>();
        if ("RSA".equals(jwk.get("kty"))) {
            required.put("e", jwk.get("e"));
            required.put("kty", "RSA");
            required.put("n", jwk.get("n"));
        } else {
            required.put("crv", jwk.get("crv"));
            required.put("kty", "EC");
            required.put("x", jwk.get("x"));
            required.put("y", jwk.get("y"));
        }
        return Codec.encode(Codec.sha256(Json.write(required).getBytes(StandardCharsets.UTF_8)));
    }

    /** Verify a compact JWS against a published key. */
    static boolean verify(String token, Map<String, Object> jwk, String alg) {
        try {
            int last = token.lastIndexOf('.');
            byte[] signingInput = token.substring(0, last).getBytes(StandardCharsets.US_ASCII);
            byte[] signature = Codec.decode(token.substring(last + 1));
            Signature verifier;
            if ("RS256".equals(alg)) {
                verifier = Signature.getInstance("SHA256withRSA");
            } else {
                if (signature.length != 64) {
                    return false;
                }
                verifier = Signature.getInstance("SHA256withECDSAinP1363Format");
            }
            verifier.initVerify(publicKey(jwk));
            verifier.update(signingInput);
            return verifier.verify(signature);
        } catch (Exception rejected) {
            return false;
        }
    }

    /** Sign a key binding JWT with the holder key, in the raw form JOSE wants. */
    static String signEs256(PrivateKey key, Map<String, Object> header, Map<String, Object> payload)
            throws Exception {
        String head = Codec.encode(Json.write(header).getBytes(StandardCharsets.UTF_8));
        String body = Codec.encode(Json.write(payload).getBytes(StandardCharsets.UTF_8));
        Signature signer = Signature.getInstance("SHA256withECDSAinP1363Format");
        signer.initSign(key);
        signer.update((head + "." + body).getBytes(StandardCharsets.US_ASCII));
        return head + "." + body + "." + Codec.encode(signer.sign());
    }
}
