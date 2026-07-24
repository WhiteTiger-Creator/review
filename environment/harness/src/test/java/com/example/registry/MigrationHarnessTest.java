package com.example.registry;

import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * End-to-end verification of the migration-replay harness. Each test drives the full
 * pipeline (unpack bundle -> load seed -> replay migrations -> canonical export) through
 * the same {@link MigrationRunner} the CLI entrypoint uses, then asserts an observable
 * property of the produced export.
 *
 * <p>These tests express the intended, correctly-migrated outcome. They pass only when
 * migrations/V003_backfill_hf_model_metadata.lua backfills each model's Hub config onto its
 * own versions, preserves version lineage, and is idempotent under re-application.
 *
 * <p>{@link #unresolvedMetadataShowsSourceConfig()} is a diagnostic aid, not just a
 * pass/fail gate: a whole-export digest mismatch alone doesn't say which model or which
 * field is wrong, so that test re-fetches the pinned Hub config (through the same
 * {@link HubConfigClient} path a migration itself would use) for any model still missing
 * metadata and prints it, rather than leaving the agent to guess or brute-force it.
 */
class MigrationHarnessTest {

    /** Expected digest is stored as bare 64-hex; tolerate a trailing "  <path>" suffix. */
    private static final Pattern HEX_DIGEST = Pattern.compile("\\b([0-9a-fA-F]{64})\\b");

    private HarnessPaths paths() {
        Path base = Paths.get("").toAbsolutePath();
        Path cursor = base;
        while (cursor != null) {
            if (cursor.resolve("pom.xml").toFile().isFile()) {
                return new HarnessPaths(cursor);
            }
            cursor = cursor.getParent();
        }
        return new HarnessPaths(base);
    }

    private String expectedDigest(HarnessPaths paths) throws IOException {
        String raw = Files.readString(paths.expectedDigest(), StandardCharsets.UTF_8).trim();
        Matcher matcher = HEX_DIGEST.matcher(raw);
        assertTrue(matcher.find(), "expected digest file is not a 64-hex SHA-256: " + raw);
        return matcher.group(1).toLowerCase();
    }

    @Test
    void exportMatchesExpectedDigest() throws IOException, SQLException {
        HarnessPaths paths = paths();
        Path export = new MigrationRunner(paths).run();

        String actual = Sha256.ofFile(export).toLowerCase();
        assertEquals(expectedDigest(paths), actual,
                "sha256 of the migrated registry_export.jsonl did not match the expected digest");
    }

    @Test
    void migrationReplayIsIdempotent() throws IOException, SQLException {
        HarnessPaths paths = paths();
        MigrationRunner runner = new MigrationRunner(paths);

        Path export = runner.run();
        byte[] first = Files.readAllBytes(export);

        runner.run();
        byte[] second = Files.readAllBytes(export);

        assertEquals(Sha256.toHex(sha256(first)), Sha256.toHex(sha256(second)),
                "re-running the migration harness must produce a byte-identical export");
    }

    @Test
    void versionLineageIsPreserved() throws IOException, SQLException {
        HarnessPaths paths = paths();
        Path export = new MigrationRunner(paths).run();

        List<String> lineageBreaks = new ArrayList<>();
        for (String line : Files.readAllLines(export, StandardCharsets.UTF_8)) {
            if (!line.contains("\"table\":\"model_versions\"")) {
                continue;
            }
            // parent_version may legitimately be null for a root version, but every
            // version must carry a real, non-null source_run_id.
            if (line.contains("\"source_run_id\":null")) {
                lineageBreaks.add(line);
            }
            if (line.contains("\"source_run_id\":\"backfilled\"")) {
                lineageBreaks.add(line);
            }
        }
        assertTrue(lineageBreaks.isEmpty(),
                "model_versions rows lost their source_run_id lineage: " + lineageBreaks);
    }

    @Test
    void noSyntheticBackfillRowsAreInserted() throws IOException, SQLException {
        HarnessPaths paths = paths();
        Path export = new MigrationRunner(paths).run();

        List<String> synthetic = new ArrayList<>();
        for (String line : Files.readAllLines(export, StandardCharsets.UTF_8)) {
            if (line.contains("\"source_run_id\":\"backfill-audit\"")) {
                synthetic.add(line);
            }
        }
        assertFalse(!synthetic.isEmpty(),
                "backfill introduced synthetic audit rows into model_versions: " + synthetic);
    }

    @Test
    void unresolvedMetadataShowsSourceConfig() throws IOException, SQLException {
        HarnessPaths paths = paths();
        Path export = new MigrationRunner(paths).run();

        Map<String, String[]> pinByModel = new LinkedHashMap<>(); // name -> {repoId, revision}
        Set<String> incomplete = new LinkedHashSet<>();

        for (String line : Files.readAllLines(export, StandardCharsets.UTF_8)) {
            if (line.contains("\"table\":\"registered_models\"")) {
                String name = extractJsonStringField(line, "name");
                String repoId = extractJsonStringField(line, "hf_repo_id");
                String revision = extractJsonStringField(line, "hf_revision");
                if (name != null && repoId != null && revision != null) {
                    pinByModel.put(name, new String[] {repoId, revision});
                }
            } else if (line.contains("\"table\":\"model_versions\"")) {
                String modelName = extractJsonStringField(line, "model_name");
                boolean rowIncomplete = line.contains("\"hf_architecture\":null")
                        || line.contains("\"hf_model_type\":null")
                        || line.contains("\"hf_hidden_size\":null")
                        || line.contains("\"hf_num_layers\":null")
                        || line.contains("\"hf_num_heads\":null");
                // Registered_models rows always precede model_versions rows in the
                // canonical export, so pinByModel is already fully populated here. A
                // model with no hf_repo_id/hf_revision pin has nothing to backfill, so
                // null hf_* on its versions is correct, not incomplete.
                if (modelName != null && rowIncomplete && pinByModel.containsKey(modelName)) {
                    incomplete.add(modelName);
                }
            }
        }

        if (incomplete.isEmpty()) {
            return;
        }

        HubConfigClient hubClient = new HubConfigClient();
        StringBuilder detail = new StringBuilder();
        for (String name : incomplete) {
            String[] pin = pinByModel.get(name);
            detail.append("\n  ").append(name).append(": ");
            if (pin == null) {
                detail.append("no hf_repo_id/hf_revision pin found in the export");
                continue;
            }
            String url = "https://huggingface.co/" + pin[0] + "/resolve/" + pin[1] + "/config.json";
            try {
                detail.append("pinned Hub config (fetched the same way http.get would) is:\n    ")
                        .append(hubClient.get(url));
            } catch (IOException | InterruptedException e) {
                detail.append("could not fetch its pinned config: ").append(e.getMessage());
            }
        }

        fail("These models still have incomplete hf_* metadata after the backfill: "
                + incomplete + detail);
    }

    /** Extracts a top-level `"key":"value"` string field from one canonical export line. */
    private static String extractJsonStringField(String line, String key) {
        Matcher matcher = Pattern.compile("\"" + key + "\":\"([^\"]*)\"").matcher(line);
        return matcher.find() ? matcher.group(1) : null;
    }

    private static byte[] sha256(byte[] bytes) {
        try {
            return java.security.MessageDigest.getInstance("SHA-256").digest(bytes);
        } catch (java.security.NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
