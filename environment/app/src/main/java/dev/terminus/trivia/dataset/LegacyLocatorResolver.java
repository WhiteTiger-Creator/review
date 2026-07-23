package dev.terminus.trivia.dataset;

import dev.terminus.trivia.audit.AuditIssue;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

public final class LegacyLocatorResolver {
    private final DuckDbCatalog catalog;

    public LegacyLocatorResolver(DuckDbCatalog catalog) {
        this.catalog = catalog;
    }

    public DuckDbCatalog catalog() {
        return catalog;
    }

    public record ResolveResult(Optional<QuestionRecord> record, List<AuditIssue> issues) {}

    public ResolveResult resolve(QuestionLocator locator, String artifactPath) throws Exception {
        List<AuditIssue> issues = new ArrayList<>();
        if (locator.kind() != QuestionLocator.Kind.LEGACY_ROW) {
            throw new IllegalArgumentException("Not a legacy locator");
        }
        Optional<QuestionRecord> record = catalog.lookupByPhysicalRow(locator.row());
        if (record.isEmpty()) {
            issues.add(new AuditIssue(artifactPath, "/trivia/row", "dataset.missing-id",
                    "No record at legacy row " + locator.row()));
            return new ResolveResult(Optional.empty(), issues);
        }
        String expected = locator.fingerprint().orElse("");
        String actual = QuestionFingerprint.compute(record.get().question());
        if (!expected.equalsIgnoreCase(actual)) {
            issues.add(new AuditIssue(artifactPath, "/trivia/question_sha256", "dataset.fingerprint-mismatch",
                    "Fingerprint mismatch for row " + locator.row()));
            return new ResolveResult(Optional.empty(), issues);
        }
        return new ResolveResult(record, issues);
    }
}
