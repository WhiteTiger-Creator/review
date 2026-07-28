package com.example.registry;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Statement;
import java.time.Duration;

/**
 * Loads the H2 seed database from the DDL + INSERT script served by the sealed data
 * service. The loader always rebuilds the schema from scratch so every harness run starts
 * from the same seed state (the migration idempotency guarantee is about re-applying
 * migrations, not about accumulating seed data across runs).
 */
final class SeedDatabaseLoader {

    private final HttpClient httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(10))
            .build();

    void load(Connection connection) throws IOException, SQLException {
        String script = fetchSeedSql();
        try (Statement statement = connection.createStatement()) {
            // Drop any prior objects so a reused database file is reset to seed state.
            statement.execute("DROP ALL OBJECTS");
            for (String rawStatement : script.split(";")) {
                String sql = stripComments(rawStatement).trim();
                if (!sql.isEmpty()) {
                    statement.execute(sql);
                }
            }
        }
    }

    private String fetchSeedSql() throws IOException {
        String base = SealedDataService.baseUrl();
        HttpRequest request = HttpRequest.newBuilder(URI.create(base + "/seed"))
                .timeout(Duration.ofSeconds(10))
                .GET()
                .build();
        try {
            HttpResponse<String> response =
                    httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() != 200) {
                throw new IOException("seed SQL request failed: HTTP " + response.statusCode());
            }
            return response.body();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("interrupted fetching seed SQL", e);
        }
    }

    private String stripComments(String sql) {
        StringBuilder out = new StringBuilder();
        for (String line : sql.split("\n", -1)) {
            int comment = line.indexOf("--");
            if (comment >= 0) {
                out.append(line, 0, comment);
            } else {
                out.append(line);
            }
            out.append('\n');
        }
        return out.toString();
    }
}
