package com.example.registry;

import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Resolves the filesystem locations the harness reads and writes. All paths are anchored
 * on the project base directory (the directory that contains pom.xml), so the harness
 * behaves identically whether it is launched by Maven (working directory = project base)
 * or by a test that passes an explicit base.
 */
final class HarnessPaths {

    private final Path base;

    HarnessPaths(Path base) {
        this.base = base.toAbsolutePath().normalize();
    }

    /** Locate the project base by walking upward until a pom.xml is found. */
    static HarnessPaths discover() {
        Path cwd = Paths.get("").toAbsolutePath();
        Path cursor = cwd;
        while (cursor != null) {
            if (cursor.resolve("pom.xml").toFile().isFile()) {
                return new HarnessPaths(cursor);
            }
            cursor = cursor.getParent();
        }
        return new HarnessPaths(cwd);
    }

    Path base() {
        return base;
    }

    /** The bundle the harness unpacks. */
    Path bundle() {
        return base.resolve("mlflow_registry_bundle.tar.gz");
    }

    /** Where the bundle is unpacked. */
    Path unpackDir() {
        return base.resolve("target").resolve("bundle");
    }

    /**
     * The migrations directory the runner replays from. This is the loose, on-disk
     * source of truth the agent edits directly (in particular
     * migrations/V003_backfill_hf_model_metadata.lua). The copy carried inside the
     * bundle is only a reference; the runner always replays this directory.
     */
    Path migrationsDir() {
        return base.resolve("migrations");
    }

    /** The H2 database file base (H2 appends .mv.db). */
    Path h2DatabaseBase() {
        return base.resolve("target").resolve("registry");
    }

    /** The canonical export the SHA-256 is computed over. */
    Path exportOutput() {
        return base.resolve("target").resolve("registry_export.jsonl");
    }

    /** The precomputed expected digest of a correctly migrated export. */
    Path expectedDigest() {
        return base.resolve("expected").resolve("registry_export.sha256");
    }
}
