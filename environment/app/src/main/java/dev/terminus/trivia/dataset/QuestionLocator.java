package dev.terminus.trivia.dataset;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.Optional;

public final class QuestionLocator {
    public enum Kind { STABLE_ID, LEGACY_ROW }

    private final Kind kind;
    private final String questionId;
    private final int row;
    private final String fingerprint;

    private QuestionLocator(Kind kind, String questionId, int row, String fingerprint) {
        this.kind = kind;
        this.questionId = questionId;
        this.row = row;
        this.fingerprint = fingerprint;
    }

    public static QuestionLocator fromJson(JsonNode trivia) {
        if (trivia.hasNonNull("question_id")) {
            return new QuestionLocator(Kind.STABLE_ID, trivia.get("question_id").asText(), 0, null);
        }
        return new QuestionLocator(Kind.LEGACY_ROW, null,
                trivia.get("row").asInt(),
                trivia.get("question_sha256").asText());
    }

    public Kind kind() { return kind; }
    public Optional<String> questionId() { return Optional.ofNullable(questionId); }
    public int row() { return row; }
    public Optional<String> fingerprint() { return Optional.ofNullable(fingerprint); }
}
