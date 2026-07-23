package dev.terminus.trivia.audit;

import dev.terminus.trivia.config.DungeonConfig;
import dev.terminus.trivia.dataset.DuckDbCatalog;
import dev.terminus.trivia.manifest.ArtifactScanner;
import dev.terminus.trivia.manifest.LoadedArtifact;
import dev.terminus.trivia.registry.DungeonRegistry;
import dev.terminus.trivia.registry.RegistryBuilder;
import dev.terminus.trivia.schema.SchemaCatalog;
import dev.terminus.trivia.schema.SchemaValidator;
import dev.terminus.trivia.schema.ValidationFinding;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

public final class AuditEngine {
    private final boolean verbose;

    public AuditEngine(boolean verbose) {
        this.verbose = verbose;
    }

    public AuditResult run(DungeonConfig config) throws Exception {
        if (!Files.isRegularFile(config.dataset())) {
            throw new IllegalStateException("Dataset not found: " + config.dataset());
        }
        if (!Files.isDirectory(config.contracts())) {
            throw new IllegalStateException("Contracts not found: " + config.contracts());
        }

        List<Path> paths = ArtifactScanner.discoverContentPaths(config);
        List<LoadedArtifact> artifacts = new ArrayList<>();
        for (Path path : paths) {
            artifacts.add(ArtifactScanner.load(config.root(), path));
        }

        String digest = AuditState.computeInputDigest(config, paths, config.contracts(), config.dataset());
        StateStore store = new StateStore();
        Optional<StateStore.CachedState> cached = store.load(config.state());
        if (cached.isPresent() && cached.get().inputDigest().equals(digest)) {
            if (verbose) {
                System.err.println("state hit digest=" + digest);
            }
            DungeonRegistry registry = cached.get().registry();
            return new AuditResult(digest, registry.digest(), List.of(), registry, true);
        }

        SchemaCatalog catalog = new SchemaCatalog(config.contracts());
        SchemaValidator validator = new SchemaValidator(catalog, config.root());
        List<AuditIssue> issues = new ArrayList<>();
        for (ValidationFinding finding : validator.validateAll(artifacts)) {
            issues.add(new AuditIssue(finding.artifact(), finding.pointer(), finding.code(), finding.message()));
        }

        DungeonRegistry registry;
        try (DuckDbCatalog duck = new DuckDbCatalog(config.dataset().toString())) {
            RegistryBuilder.BuildResult built = new RegistryBuilder().build(config, artifacts, duck);
            issues.addAll(built.issues());
            registry = built.registry();
        }

        boolean success = issues.isEmpty();
        store.save(config.state(), digest, registry, success);

        if (verbose) {
            System.err.println("audit digest=" + digest + " issues=" + issues.size());
        }
        return new AuditResult(digest, registry.digest(), issues, registry, success);
    }
}
