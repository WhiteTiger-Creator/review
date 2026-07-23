package dev.terminus.trivia.audit;

public record AuditIssue(String artifact, String pointer, String code, String message) {}
