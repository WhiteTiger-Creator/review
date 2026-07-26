package com.example.registry;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;

/**
 * Lazily starts and locates the sealed data service: a compiled-only background process
 * that serves the seed SQL and the pinned Hugging Face Hub fixtures over a localhost-only
 * HTTP endpoint.
 *
 * <p>"Sealed" here means packaged as bytecode with no source alongside it -- not secret.
 * The fixtures it serves are inputs, and reading a checkpoint config is exactly what the
 * migration under test is for. What this task protects is the correct *output*, and that
 * is protected by the export digest and by behavioural checks that need no answer key, not
 * by hiding anything this service returns.
 */
final class SealedDataService {

    private static final String HOST = "127.0.0.1";
    private static final int PORT = 8743;
    private static final String SERVICE_BYTECODE = "/opt/_sealed/data_service.pyc";
    private static final long START_TIMEOUT_MILLIS = 15_000;

    private static volatile boolean launchAttempted = false;

    private static final HttpClient CONTROL_CLIENT = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(5))
            .build();

    private SealedDataService() {
    }

    /** Base URL of the sealed service, starting it first if it isn't already running. */
    static synchronized String baseUrl() throws IOException {
        ensureRunning();
        return "http://" + HOST + ":" + PORT;
    }

    /**
     * Tell the service a fresh harness run is starting: clears the per-run record of which
     * URLs were fetched and re-arms the one-shot throttle on the repos that exercise the
     * retry path. Called once per {@link MigrationRunner#run()}.
     */
    static void beginRun() throws IOException {
        get(baseUrl() + "/control/run-begin");
    }

    private static void get(String url) throws IOException {
        HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                .timeout(Duration.ofSeconds(10))
                .GET()
                .build();
        try {
            HttpResponse<String> response =
                    CONTROL_CLIENT.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() != 200) {
                throw new IOException("sealed data service error: HTTP " + response.statusCode()
                        + " for " + url);
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("interrupted calling sealed data service", e);
        }
    }

    private static void ensureRunning() throws IOException {
        if (isUp()) {
            return;
        }
        if (!launchAttempted) {
            launchAttempted = true;
            ProcessBuilder builder = new ProcessBuilder("python3", serviceEntryPoint());
            builder.redirectOutput(ProcessBuilder.Redirect.DISCARD);
            builder.redirectError(ProcessBuilder.Redirect.DISCARD);
            builder.start();
        }
        long deadline = System.currentTimeMillis() + START_TIMEOUT_MILLIS;
        while (System.currentTimeMillis() < deadline) {
            if (isUp()) {
                return;
            }
            try {
                Thread.sleep(100);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new IOException("interrupted waiting for sealed data service to start", e);
            }
        }
        throw new IOException("sealed data service did not become reachable at "
                + HOST + ":" + PORT + " within " + START_TIMEOUT_MILLIS + "ms");
    }

    /**
     * The shipped image carries only the compiled service at {@link #SERVICE_BYTECODE}. The
     * uncompiled source path is consulted purely so the harness can be driven from a source
     * checkout during authoring; it does not exist in the built image.
     */
    private static String serviceEntryPoint() {
        if (Files.isRegularFile(Path.of(SERVICE_BYTECODE))) {
            return SERVICE_BYTECODE;
        }
        Path cursor = Path.of("").toAbsolutePath();
        while (cursor != null) {
            Path candidate = cursor.resolve("environment").resolve("sealed")
                    .resolve("data_service.py");
            if (Files.isRegularFile(candidate)) {
                return candidate.toString();
            }
            cursor = cursor.getParent();
        }
        return SERVICE_BYTECODE;
    }

    private static boolean isUp() {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress(HOST, PORT), 200);
            return true;
        } catch (IOException e) {
            return false;
        }
    }
}
