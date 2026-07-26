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
 * Backs the Lua {@code http.get} helper. Migration scripts name Hugging Face Hub URLs;
 * this client resolves each one to its response body.
 *
 * <p>Two kinds of Hub URL are reachable:
 * <ul>
 *   <li>{@code https://huggingface.co/api/models/{repo}/revision/{tag}} -- the revision
 *       document, whose {@code sha} field is the commit a tag currently points at;</li>
 *   <li>{@code https://huggingface.co/{repo}/resolve/{commit}/{file}} -- a file at an
 *       exact commit.</li>
 * </ul>
 *
 * <p>Responses come from the sealed data service, keyed by exact URL, so the pipeline is
 * byte-reproducible regardless of network state. Any non-200 is surfaced to Lua as an
 * error rather than being swallowed: a migration that wants to tolerate a missing optional
 * document, or retry a throttled one, has to say so explicitly with {@code pcall}.
 */
final class HubConfigClient {

    private static final String HUB_PREFIX = "https://huggingface.co/";

    private final HttpClient httpClient;

    HubConfigClient() {
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .followRedirects(HttpClient.Redirect.NORMAL)
                .build();
    }

    /**
     * Fetch the response body for a Hub URL.
     *
     * @throws HubHttpException if the Hub answers with a non-200 status. The status code is
     *     carried on the exception and included in the message the migration sees, so a
     *     migration can distinguish "this optional file does not exist" (404) from "slow
     *     down and try again" (429).
     */
    String get(String url) throws IOException, InterruptedException {
        if (!url.startsWith(HUB_PREFIX)) {
            // Migrations may only ever name a Hugging Face Hub URL. The sealed data
            // service's own endpoint is an implementation detail this method consults on
            // the migration's behalf; letting a migration name it directly would let it
            // read the whole corpus in one request instead of the documents it is
            // supposed to resolve one pin at a time.
            throw new IOException("http.get only supports Hugging Face Hub URLs, got: " + url);
        }
        String base = SealedDataService.baseUrl();
        String encoded = URLEncoder.encode(url, StandardCharsets.UTF_8);
        HttpRequest request = HttpRequest.newBuilder(URI.create(base + "/hf?url=" + encoded))
                .timeout(Duration.ofSeconds(10))
                .GET()
                .build();
        HttpResponse<String> response =
                httpClient.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        int status = response.statusCode();
        if (status == 200) {
            return response.body();
        }
        throw new HubHttpException(status, "Hub request failed: HTTP " + status + " for " + url);
    }

    /** A non-200 answer from the Hub, carrying the status code. */
    static final class HubHttpException extends IOException {
        private static final long serialVersionUID = 1L;

        private final int statusCode;

        HubHttpException(int statusCode, String message) {
            super(message);
            this.statusCode = statusCode;
        }

        int statusCode() {
            return statusCode;
        }
    }
}
