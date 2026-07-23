package dev.terminus.trivia.dataset;

import dev.terminus.trivia.util.Digest;
import dev.terminus.trivia.util.UnicodeNormalizer;

public final class QuestionFingerprint {
    private QuestionFingerprint() {}

    public static String compute(String question) {
        return Digest.sha256Hex(UnicodeNormalizer.normalizeAnswer(question == null ? "" : question));
    }
}
