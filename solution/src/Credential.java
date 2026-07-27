package com.acme.wallet.sdjwt;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** One stored credential: its wire parts, and the resolution of its disclosures. */
final class Credential {

    /** Stops the ladder with the status the profile assigns. */
    static final class Rejected extends RuntimeException {
        final String status;

        Rejected(String status) {
            super(status);
            this.status = status;
        }
    }

    final String id;
    final String jwt;
    final List<String> disclosures = new ArrayList<>();
    final Map<String, Object> header;
    final Map<String, Object> payload;

    private final Map<String, List<Object>> byDigest = new HashMap<>();
    private final Map<String, String> pathToDigest = new LinkedHashMap<>();
    private final Set<String> seen = new HashSet<>();
    private final Set<String> used = new HashSet<>();

    private Map<String, Object> resolved;

    /** Split the issuance form and check everything the profile calls malformed. */
    Credential(String id, String text) {
        this.id = id;
        if (!text.endsWith("~")) {
            throw new Rejected("malformed");
        }
        String[] parts = text.substring(0, text.length() - 1).split("~", -1);
        this.jwt = parts[0];
        String[] jwsParts = jwt.split("\\.", -1);
        if (jwsParts.length != 3) {
            throw new Rejected("malformed");
        }
        for (String part : jwsParts) {
            if (!Codec.isBase64Url(part)) {
                throw new Rejected("malformed");
            }
        }
        for (int i = 1; i < parts.length; i++) {
            if (!Codec.isBase64Url(parts[i])) {
                throw new Rejected("malformed");
            }
            disclosures.add(parts[i]);
        }
        try {
            this.header = Json.object(Codec.decodeText(jwsParts[0]));
            this.payload = Json.object(Codec.decodeText(jwsParts[1]));
        } catch (RuntimeException broken) {
            throw new Rejected("malformed");
        }
        for (String disclosure : disclosures) {
            List<Object> array = parseDisclosure(disclosure);
            byDigest.put(Codec.digest(disclosure), array);
        }
    }

    private static List<Object> parseDisclosure(String disclosure) {
        Object value;
        try {
            value = Json.parse(Codec.decodeText(disclosure));
        } catch (RuntimeException broken) {
            throw new Rejected("malformed");
        }
        if (!(value instanceof List)) {
            throw new Rejected("malformed");
        }
        List<?> array = (List<?>) value;
        if (array.size() != 2 && array.size() != 3) {
            throw new Rejected("malformed");
        }
        if (!(array.get(0) instanceof String)) {
            throw new Rejected("malformed");
        }
        if (array.size() == 3 && !(array.get(1) instanceof String)) {
            throw new Rejected("malformed");
        }
        List<Object> out = new ArrayList<>();
        for (Object element : array) {
            out.add(element);
        }
        return out;
    }

    /** Digest algorithm the issuer used, defaulting to the only one this profile takes. */
    String digestAlgorithm() {
        Object declared = payload.get("_sd_alg");
        return declared == null ? "sha-256" : String.valueOf(declared);
    }

    /** Apply every held disclosure, or reject the credential. */
    @SuppressWarnings("unchecked")
    Map<String, Object> resolve() {
        if (resolved == null) {
            if (byDigest.size() != disclosures.size()) {
                throw new Rejected("invalid_disclosure");
            }
            resolved = (Map<String, Object>) walk(payload, "", null);
            if (used.size() != byDigest.size()) {
                throw new Rejected("invalid_disclosure");
            }
        }
        return resolved;
    }

    /** The claim path each released disclosure occupies. */
    Map<String, String> paths() {
        resolve();
        return pathToDigest;
    }

    /** The disclosure text behind a digest. */
    String textOf(String digest) {
        for (String disclosure : disclosures) {
            if (Codec.digest(disclosure).equals(digest)) {
                return disclosure;
            }
        }
        throw new IllegalStateException("no disclosure for " + digest);
    }

    private List<Object> take(String digest) {
        if (!seen.add(digest)) {
            throw new Rejected("invalid_disclosure");
        }
        return byDigest.get(digest);
    }

    @SuppressWarnings("unchecked")
    private Object walk(Object value, String path, String parent) {
        if (value instanceof Map) {
            Map<String, Object> source = (Map<String, Object>) value;
            Map<String, Object> members = new LinkedHashMap<>();
            for (Map.Entry<String, Object> entry : source.entrySet()) {
                String name = entry.getKey();
                if (name.equals("_sd") || (path.isEmpty() && name.equals("_sd_alg"))) {
                    continue;
                }
                if (name.equals("...")) {
                    throw new Rejected("invalid_disclosure");
                }
                members.put(name, walk(entry.getValue(), Paths.join(path, name), parent));
            }
            Object hidden = source.get("_sd");
            if (hidden != null) {
                if (!(hidden instanceof List)) {
                    throw new Rejected("invalid_disclosure");
                }
                for (Object item : (List<Object>) hidden) {
                    if (!(item instanceof String)) {
                        throw new Rejected("invalid_disclosure");
                    }
                    String digest = (String) item;
                    List<Object> parts = take(digest);
                    if (parts == null) {
                        continue;
                    }
                    if (parts.size() != 3) {
                        throw new Rejected("invalid_disclosure");
                    }
                    String name = (String) parts.get(1);
                    if (name.equals("_sd") || name.equals("...") || members.containsKey(name)) {
                        throw new Rejected("invalid_disclosure");
                    }
                    String here = Paths.join(path, name);
                    used.add(digest);
                    pathToDigest.put(here, digest);
                    members.put(name, walk(parts.get(2), here, here));
                }
            }
            return members;
        }
        if (value instanceof List) {
            List<Object> elements = new ArrayList<>();
            for (Object element : (List<Object>) value) {
                String digest = placeholder(element);
                String here = Paths.element(path, elements.size());
                if (digest == null) {
                    elements.add(walk(element, here, parent));
                    continue;
                }
                List<Object> parts = take(digest);
                if (parts == null) {
                    continue;
                }
                if (parts.size() != 2) {
                    throw new Rejected("invalid_disclosure");
                }
                used.add(digest);
                pathToDigest.put(here, digest);
                elements.add(walk(parts.get(1), here, here));
            }
            return elements;
        }
        return value;
    }

    @SuppressWarnings("unchecked")
    private static String placeholder(Object element) {
        if (!(element instanceof Map)) {
            return null;
        }
        Map<String, Object> members = (Map<String, Object>) element;
        if (members.size() != 1) {
            return null;
        }
        Object digest = members.get("...");
        return digest instanceof String ? (String) digest : null;
    }
}
