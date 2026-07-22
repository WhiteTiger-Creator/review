package dev.terminus.trivia.audit;

import dev.terminus.trivia.registry.DungeonRegistry;

import java.util.List;

public record AuditResult(
        String inputDigest,
        String registryDigest,
        List<AuditIssue> issues,
        DungeonRegistry registry,
        boolean success
) {}
