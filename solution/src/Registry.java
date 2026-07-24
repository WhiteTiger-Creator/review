package com.acme.inbox.jwe;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Resolves a sender's static public key from the sender registry. The registry maps a sender key id
 * (skid) to a JWK Set URI; the key with a matching kid is the sender's static agreement key. Each
 * URI is fetched at most once per run and its key set is cached.
 */
final class Registry {

    private final Map<String, String> uriBySkid;
    private final Map<String, List<Map<String, Object>>> cache = new HashMap<>();
    private final HttpClient client = HttpClient.newBuilder()
            .followRedirects(HttpClient.Redirect.NORMAL)
            .connectTimeout(Duration.ofSeconds(20))
            .build();

    Registry(Map<String, String> uriBySkid) {
        this.uriBySkid = uriBySkid;
    }

    /** The P-256 public JWK the registry publishes for this sender, or null if it cannot be resolved. */
    Map<String, Object> resolve(String skid) {
        String uri = uriBySkid.get(skid);
        if (uri == null) {
            return null;
        }
        List<Map<String, Object>> keys = fetch(uri);
        if (keys == null) {
            return null;
        }
        for (Map<String, Object> key : keys) {
            if (skid.equals(key.get("kid")) && Jose.isP256(key)) {
                return key;
            }
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> fetch(String uri) {
        if (cache.containsKey(uri)) {
            return cache.get(uri);
        }
        List<Map<String, Object>> keys = null;
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(uri))
                    .header("Accept", "application/json")
                    .timeout(Duration.ofSeconds(20))
                    .GET()
                    .build();
            HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() == 200) {
                Object parsed = Json.parse(response.body());
                if (parsed instanceof Map) {
                    Object list = ((Map<String, Object>) parsed).get("keys");
                    if (list instanceof List) {
                        keys = new java.util.ArrayList<>();
                        for (Object item : (List<Object>) list) {
                            if (item instanceof Map) {
                                keys.add((Map<String, Object>) item);
                            }
                        }
                    }
                }
            }
        } catch (Exception e) {
            keys = null;
        }
        cache.put(uri, keys);
        return keys;
    }
}
