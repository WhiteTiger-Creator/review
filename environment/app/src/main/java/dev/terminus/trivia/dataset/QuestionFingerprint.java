package dev.terminus.trivia.dataset;

import dev.terminus.trivia.util.Digest;

import java.util.Locale;

public final class QuestionFingerprint {
    private QuestionFingerprint() {}

    public static String compute(String question) {
        if (question == null) {
            return Digest.sha256Hex("");
        }
        String lowered = question.toLowerCase(Locale.getDefault());
        String stripped = lowered.replaceAll("[^a-z0-9 ]", "");
        String collapsed = stripped.trim().replaceAll("\\s+", " ");
        return Digest.sha256Hex(collapsed);
    }
}
