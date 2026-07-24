package com.example.registry;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.Socket;

/**
 * Lazily starts and locates the sealed data service: a compiled-only (no {@code .java}/
 * {@code .py} source shipped in the image) background process that serves the pinned seed
 * SQL and Hugging Face config fixtures over a localhost-only HTTP endpoint.
 *
 * <p>{@link SeedDatabaseLoader} and {@link HubConfigClient} are the only callers. Neither
 * of them, nor anything else in this package, has direct filesystem access to the seed
 * data or config fixtures; the sealed service is the only path to them, and it only
 * listens on loopback.
 */
final class SealedDataService {

    private static final String HOST = "127.0.0.1";
    private static final int PORT = 8743;
    private static final String SERVICE_SCRIPT = "/opt/_sealed/data_service.pyc";
    private static final long START_TIMEOUT_MILLIS = 10_000;

    private static volatile boolean launchAttempted = false;

    private SealedDataService() {
    }

    /** Base URL of the sealed service, starting it first if it isn't already running. */
    static synchronized String baseUrl() throws IOException {
        ensureRunning();
        return "http://" + HOST + ":" + PORT;
    }

    private static void ensureRunning() throws IOException {
        if (isUp()) {
            return;
        }
        if (!launchAttempted) {
            launchAttempted = true;
            ProcessBuilder builder = new ProcessBuilder("python3", SERVICE_SCRIPT);
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

    private static boolean isUp() {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress(HOST, PORT), 200);
            return true;
        } catch (IOException e) {
            return false;
        }
    }
}
