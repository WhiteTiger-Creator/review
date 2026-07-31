package com.example.releasemirror;

import com.sun.net.httpserver.Headers;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.file.Files;
import java.nio.file.Path;

public final class ReleaseMirrorMain {

    private static final String TARBALL = "mlflow-2.16.2.tar.gz";
    private static final String CHECKSUM = "mlflow-2.16.2.sha256";

    public static void main(String[] args) throws Exception {
        int port = args.length > 0 ? Integer.parseInt(args[0]) : 18081;
        Path dataDir = Path.of(args.length > 1 ? args[1] : System.getenv().getOrDefault("DATA_DIR", "/data/mlflow-release"));

        HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 0);
        server.createContext("/health", ReleaseMirrorMain::handleHealth);
        server.createContext("/releases/" + TARBALL, exchange -> serveFile(exchange, dataDir.resolve(TARBALL), "application/gzip"));
        server.createContext("/releases/" + CHECKSUM, exchange -> serveFile(exchange, dataDir.resolve(CHECKSUM), "text/plain"));
        server.createContext("/redirect-external", ReleaseMirrorMain::handleRedirectExternal);
        server.createContext("/redirect-internal", exchange -> handleRedirectInternal(exchange, port));
        server.setExecutor(null);
        server.start();

        System.out.println("Release mirror listening on 127.0.0.1:" + port + " dataDir=" + dataDir);
        Thread.currentThread().join();
    }

    private static void handleHealth(HttpExchange exchange) throws IOException {
        byte[] body = "ok".getBytes();
        exchange.getResponseHeaders().set("Content-Type", "text/plain; charset=utf-8");
        exchange.sendResponseHeaders(200, body.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(body);
        }
    }

    private static void serveFile(HttpExchange exchange, Path file, String contentType) throws IOException {
        if (!Files.isRegularFile(file)) {
            byte[] body = ("not found: " + file).getBytes();
            exchange.sendResponseHeaders(404, body.length);
            try (OutputStream out = exchange.getResponseBody()) {
                out.write(body);
            }
            return;
        }
        byte[] body = Files.readAllBytes(file);
        exchange.getResponseHeaders().set("Content-Type", contentType);
        exchange.sendResponseHeaders(200, body.length);
        try (OutputStream out = exchange.getResponseBody()) {
            out.write(body);
        }
    }

    private static void handleRedirectExternal(HttpExchange exchange) throws IOException {
        sendRedirect(exchange, "http://example.com/evil.tar.gz");
    }

    private static void handleRedirectInternal(HttpExchange exchange, int port) throws IOException {
        sendRedirect(exchange, "http://127.0.0.1:" + port + "/releases/" + TARBALL);
    }

    private static void sendRedirect(HttpExchange exchange, String location) throws IOException {
        Headers headers = exchange.getResponseHeaders();
        headers.set("Location", location);
        exchange.sendResponseHeaders(302, -1);
        exchange.close();
    }
}
