package com.example.registry;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.regex.Pattern;

/**
 * Drives the full harness pipeline:
 * <ol>
 *   <li>unpack mlflow_registry_bundle.tar.gz into target/bundle;</li>
 *   <li>load the H2 seed database from the seed SQL;</li>
 *   <li>replay the Lua migrations in version order through the LuaJ bridge;</li>
 *   <li>replay the backfill migrations a second time against the same database;</li>
 *   <li>export the migrated tables to target/registry_export.jsonl in canonical order.</li>
 * </ol>
 *
 * <p>Step 4 is deliberate. Schema migrations (V001, V002) run once, the way a real
 * migration tool applies them once per database. Backfill migrations -- everything from
 * {@link #REPEATABLE_FROM_VERSION} up -- are re-applied immediately, against the same
 * connection and the same already-migrated state, because in production they get re-run
 * whenever upstream metadata changes. A backfill that only produces the right answer
 * against virgin state is not finished: re-applying it must leave the data unchanged. This
 * is a stronger requirement than "two harness runs agree", since the second application
 * here sees the first application's output rather than a freshly seeded database.
 *
 * <p>Migrations are replayed from the loose on-disk {@code migrations/} directory (the
 * source of truth the agent edits), not from the copy inside the bundle. The version order
 * is taken from the numeric prefix of each {@code VNNN_*.lua} file name.
 */
public final class MigrationRunner {

    private static final Pattern MIGRATION_NAME = Pattern.compile("^V(\\d+)_.*\\.lua$");

    /** Migrations at or above this version are backfills, and are replayed twice. */
    private static final int REPEATABLE_FROM_VERSION = 3;

    private final HarnessPaths paths;

    public MigrationRunner(HarnessPaths paths) {
        this.paths = paths;
    }

    public static void main(String[] args) throws Exception {
        HarnessPaths paths = HarnessPaths.discover();
        MigrationRunner runner = new MigrationRunner(paths);
        Path export = runner.run();
        System.out.println("wrote canonical export: " + export);
        System.out.println("export sha256: " + Sha256.ofFile(export));
    }

    /** Run the full pipeline and return the path of the produced export. */
    public Path run() throws IOException, SQLException {
        new BundleUnpacker().unpack(paths.bundle(), paths.unpackDir());
        SealedDataService.beginRun();

        // A file-based H2 database, rebuilt from seed on every run so replays are
        // reproducible from the same starting state.
        deleteDatabaseFiles();
        String jdbcUrl = "jdbc:h2:" + paths.h2DatabaseBase().toAbsolutePath()
                + ";MODE=LEGACY;DB_CLOSE_DELAY=-1";
        try (Connection connection = DriverManager.getConnection(jdbcUrl, "sa", "")) {
            connection.setAutoCommit(true);

            new SeedDatabaseLoader().load(connection);

            HubConfigClient hubClient = new HubConfigClient();
            LuaMigrationBridge bridge = new LuaMigrationBridge(connection, hubClient);

            List<Path> migrations = orderedMigrations();
            for (Path migration : migrations) {
                bridge.runMigration(migration);
            }
            for (Path migration : migrations) {
                if (versionOf(migration) >= REPEATABLE_FROM_VERSION) {
                    bridge.runMigration(migration);
                }
            }

            new CanonicalExporter().export(connection, paths.exportOutput());
        }
        return paths.exportOutput();
    }

    private List<Path> orderedMigrations() throws IOException {
        Path dir = paths.migrationsDir();
        if (!Files.isDirectory(dir)) {
            throw new IOException("migrations directory not found: " + dir);
        }
        List<Path> migrations = new ArrayList<>();
        try (var stream = Files.list(dir)) {
            stream.filter(Files::isRegularFile)
                    .filter(p -> MIGRATION_NAME.matcher(p.getFileName().toString()).matches())
                    .forEach(migrations::add);
        }
        migrations.sort(Comparator.comparingInt(MigrationRunner::versionOf));
        return migrations;
    }

    private static int versionOf(Path migration) {
        var matcher = MIGRATION_NAME.matcher(migration.getFileName().toString());
        if (!matcher.matches()) {
            throw new IllegalStateException("not a migration file: " + migration);
        }
        return Integer.parseInt(matcher.group(1));
    }

    private void deleteDatabaseFiles() throws IOException {
        Path base = paths.h2DatabaseBase();
        Files.createDirectories(base.getParent());
        for (String suffix : new String[] {".mv.db", ".trace.db", ".lock.db"}) {
            Files.deleteIfExists(Path.of(base.toAbsolutePath() + suffix));
        }
    }
}
