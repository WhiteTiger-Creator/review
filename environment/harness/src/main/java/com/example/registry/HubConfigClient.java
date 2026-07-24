package com.example.registry;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;

/**
 * Backs the Lua HTTP GET helper. Migration scripts fetch pinned Hugging Face Hub model
 * config documents by URL; this client resolves each URL to its response body.
 *
 * <p>Determinism is guaranteed by the sealed data service's pinned responses (queried by
 * exact URL), so the migrated export is byte-identical on every run regardless of network
 * state. When a URL is not pinned by the sealed service, the client falls back to a live
 * HTTPS GET against the public Hub REST API; a live response is only ever used for URLs
 * the bundle did not pin, so it can never perturb the precomputed digest.
 */
final class HubConfigClient {

    private final HttpClient httpClient;

    HubConfigClient() {
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .followRedirects(HttpClient.Redirect.NORMAL)
                .build();
    }

    /** Fetch the response body for a Hub config URL. */
    String get(String url) throws IOException, InterruptedException {
        if (!url.startsWith("https://huggingface.co/")) {
            // Migrations only ever get to name a Hugging Face Hub URL; the sealed data
            // service's own endpoint is an internal implementation detail this method
            // consults on the migration's behalf, never a URL a migration can name itself
            // (otherwise a migration could call http.get on the service directly and read
            // back the raw seed SQL / other models' fixtures it fetches, instead of only
            // its own pinned config).
            throw new IOException("http.get only supports Hugging Face Hub URLs, got: " + url);
        }
        String pinned = fetchFromSealedService(url);
        if (pinned != null) {
            return pinned;
        }
        HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                .timeout(Duration.ofSeconds(15))
                .header("Accept", "application/json")
                .GET()
                .build();
        HttpResponse<String> response =
                httpClient.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        if (response.statusCode() != 200) {
            throw new IOException("Hub config request failed: HTTP " + response.statusCode()
                    + " for " + url);
        }
        return response.body();
    }

    /** Queries the sealed data service for a pinned config; null if this URL isn't pinned. */
    private String fetchFromSealedService(String url) throws IOException {
        String base = SealedDataService.baseUrl();
        String encoded = URLEncoder.encode(url, StandardCharsets.UTF_8);
        HttpRequest request = HttpRequest.newBuilder(URI.create(base + "/hf-config?url=" + encoded))
                .timeout(Duration.ofSeconds(10))
                .GET()
                .build();
        try {
            HttpResponse<String> response =
                    httpClient.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            if (response.statusCode() == 200) {
                return response.body();
            }
            if (response.statusCode() == 404) {
                return null;
            }
            throw new IOException("sealed data service error: HTTP " + response.statusCode());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("interrupted querying sealed data service", e);
        }
    }
}
