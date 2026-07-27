package com.example.registry;

import org.junit.jupiter.api.BeforeAll;
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
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;
import static org.junit.jupiter.api.Assumptions.assumeTrue;

/**
 * End-to-end checks on the migration-replay harness. Each test asserts a property of the
 * canonical export produced by the same {@link MigrationRunner} the CLI entrypoint uses.
 *
 * <p>These are a development aid, not the grading harness. They tell you <em>which</em>
 * models and columns are still outstanding so you are not left bisecting a whole-file
 * digest by hand. They deliberately do not tell you what any column should contain: the
 * specification is spec/BACKFILL_CONTRACT.md and the three worked checkpoints under
 * spec/worked/.
 *
 * <p>The full pipeline (unpack -> seed -> replay migrations -> canonical export) runs
 * exactly twice for the whole class, not once per test: a single {@link BeforeAll} run
 * seeds the export every read-only assertion shares, and {@link #replayIsIdempotent()}
 * performs the one additional run its own comparison needs. The migration is required to
 * be deterministic (see spec/BACKFILL_CONTRACT.md's Determinism requirement), so sharing
 * one run's output across assertions checks exactly the same thing as re-running it per
 * assertion -- it just does not re-pay a full unpack/seed/replay/Hub-fetch cycle, with its
 * live requests and retries, for every single check.
 */
class MigrationHarnessTest {

    private static final Pattern HEX_DIGEST = Pattern.compile("\\b([0-9a-fA-F]{64})\\b");

    /** Columns of model_architecture that a resolved checkpoint must fill. */
    private static final List<String> REQUIRED_ARCHITECTURE_COLUMNS = List.of(
            "architecture", "model_type", "hidden_size", "num_layers", "num_heads",
            "num_kv_heads", "head_dim", "ffn_dim", "attention_variant",
            "total_param_count", "active_param_count", "kv_cache_bytes_per_token");

    private static Path sharedExport;
    private static List<String> sharedLines;

    private static HarnessPaths paths() {
        Path cursor = Paths.get("").toAbsolutePath();
        while (cursor != null) {
            if (cursor.resolve("pom.xml").toFile().isFile()) {
                return new HarnessPaths(cursor);
            }
            cursor = cursor.getParent();
        }
        return new HarnessPaths(Paths.get("").toAbsolutePath());
    }

    @BeforeAll
    static void runHarnessOnce() throws IOException, SQLException {
        sharedExport = new MigrationRunner(paths()).run();
        sharedLines = Files.readAllLines(sharedExport, StandardCharsets.UTF_8);
    }

    @Test
    void exportMatchesExpectedDigest() throws IOException {
        Path digestFile = paths().expectedDigest();
        assumeTrue(digestFile.toFile().isFile(),
                "expected digest not present in this environment: " + digestFile);

        String raw = Files.readString(digestFile, StandardCharsets.UTF_8).trim();
        Matcher matcher = HEX_DIGEST.matcher(raw);
        assertTrue(matcher.find(), "expected digest file is not a 64-hex SHA-256: " + raw);

        assertEquals(matcher.group(1).toLowerCase(), Sha256.ofFile(sharedExport).toLowerCase(),
                "sha256 of the migrated registry_export.jsonl did not match the expected "
                        + "digest");
    }

    @Test
    void replayIsIdempotent() throws IOException, SQLException {
        byte[] first = Files.readAllBytes(sharedExport);
        new MigrationRunner(paths()).run();
        byte[] second = Files.readAllBytes(sharedExport);

        assertEquals(Sha256.toHex(sha256(first)), Sha256.toHex(sha256(second)),
                "re-running the harness must produce a byte-identical export");
    }

    @Test
    void versionLineageIsPreserved() {
        List<String> broken = new ArrayList<>();
        for (String line : sharedLines) {
            if (!line.contains("\"table\":\"model_versions\"")) {
                continue;
            }
            if (line.contains("\"source_run_id\":null")
                    || line.contains("\"current_stage\":null")) {
                broken.add(line);
            }
        }
        assertTrue(broken.isEmpty(),
                "model_versions rows lost their lineage; the backfill must only write "
                        + "hf_architecture_fingerprint: " + broken);
    }

    @Test
    void noRowsAreAddedOrDropped() {
        int versions = 0;
        int models = 0;
        for (String line : sharedLines) {
            if (line.contains("\"table\":\"model_versions\"")) {
                versions++;
            } else if (line.contains("\"table\":\"registered_models\"")) {
                models++;
            }
        }
        assertEquals(20, models, "registered_models row count changed");
        assertEquals(32, versions, "model_versions row count changed");
    }

    @Test
    void everyFingerprintResolvesToAnArchitectureRow() {
        Set<String> defined = new LinkedHashSet<>();
        Set<String> inScope = new LinkedHashSet<>();
        Map<String, String> referencedBy = new LinkedHashMap<>();

        for (String line : sharedLines) {
            if (line.contains("\"table\":\"registered_models\"")) {
                String name = stringField(line, "name");
                if (name != null
                        && "transformers".equals(stringField(line, "framework"))
                        && stringField(line, "hf_repo_id") != null) {
                    inScope.add(name);
                }
            } else if (line.contains("\"table\":\"model_architecture\"")) {
                String fingerprint = stringField(line, "fingerprint");
                if (fingerprint != null && !defined.add(fingerprint)) {
                    fail("model_architecture contains fingerprint " + fingerprint
                            + " more than once; it is keyed by fingerprint, so models that "
                            + "resolve to the same architecture share one row");
                }
            } else if (line.contains("\"table\":\"model_versions\"")) {
                String fingerprint = stringField(line, "hf_architecture_fingerprint");
                if (fingerprint != null) {
                    referencedBy.putIfAbsent(fingerprint, stringField(line, "model_name"));
                }
            }
        }

        // Only in-scope models are checked. Rows outside the migration's scope legitimately
        // keep the stale fingerprint they were seeded with, which resolves to nothing --
        // that is the correct outcome, not a dangling reference.
        List<String> dangling = new ArrayList<>();
        for (Map.Entry<String, String> entry : referencedBy.entrySet()) {
            if (inScope.contains(entry.getValue()) && !defined.contains(entry.getKey())) {
                dangling.add(entry.getValue() + " -> " + entry.getKey());
            }
        }
        assertTrue(dangling.isEmpty(),
                "in-scope model_versions rows reference fingerprints with no "
                        + "model_architecture row: " + dangling);
    }

    /**
     * Names the models and columns still outstanding after the backfill. Reports what is
     * unresolved, never what the resolved value should be -- the contract and the worked
     * examples are the specification, and the export digest is the oracle.
     */
    @Test
    void everyInScopeModelIsFullyResolved() {
        Map<String, String> commitByModel = new LinkedHashMap<>();
        Set<String> inScope = new LinkedHashSet<>();
        Map<String, String> fingerprintByModel = new LinkedHashMap<>();
        Map<String, String> architectureRows = new LinkedHashMap<>();

        for (String line : sharedLines) {
            if (line.contains("\"table\":\"registered_models\"")) {
                String name = stringField(line, "name");
                if (name == null) {
                    continue;
                }
                boolean transformers = "transformers".equals(stringField(line, "framework"));
                boolean pinned = stringField(line, "hf_repo_id") != null
                        && stringField(line, "hf_revision") != null;
                if (transformers && pinned) {
                    inScope.add(name);
                    String commit = stringField(line, "hf_resolved_commit");
                    if (commit != null) {
                        commitByModel.put(name, commit);
                    }
                }
            } else if (line.contains("\"table\":\"model_architecture\"")) {
                architectureRows.put(stringField(line, "fingerprint"), line);
            } else if (line.contains("\"table\":\"model_versions\"")) {
                String model = stringField(line, "model_name");
                String fingerprint = stringField(line, "hf_architecture_fingerprint");
                if (model != null && fingerprint != null) {
                    fingerprintByModel.putIfAbsent(model, fingerprint);
                }
            }
        }

        List<String> outstanding = new ArrayList<>();
        for (String model : inScope) {
            if (!commitByModel.containsKey(model)) {
                outstanding.add(model + ": hf_resolved_commit not recorded");
            }
            String fingerprint = fingerprintByModel.get(model);
            if (fingerprint == null) {
                outstanding.add(model + ": no hf_architecture_fingerprint on its versions");
                continue;
            }
            String row = architectureRows.get(fingerprint);
            if (row == null) {
                outstanding.add(model + ": fingerprint has no model_architecture row");
                continue;
            }
            for (String column : REQUIRED_ARCHITECTURE_COLUMNS) {
                if (row.contains("\"" + column + "\":null")) {
                    outstanding.add(model + ": " + column + " unresolved");
                }
            }
        }

        assertTrue(outstanding.isEmpty(),
                "still outstanding after the backfill (see spec/BACKFILL_CONTRACT.md and "
                        + "spec/worked/):\n  " + String.join("\n  ", outstanding));
    }

    private static String stringField(String line, String key) {
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
