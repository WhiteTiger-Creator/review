package dev.terminus.trivia;

import dev.terminus.trivia.dataset.QuestionFingerprint;
import dev.terminus.trivia.util.Digest;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class QuestionFingerprintTest {
    @Test
    void simpleAsciiQuestionFingerprint() {
        String question = "What is 2 + 2?";
        String fp = QuestionFingerprint.compute(question);
        String expected = Digest.sha256Hex("what is 2 2");
        assertEquals(expected, fp);
    }

    @Test
    void collapsesWhitespace() {
        String fp = QuestionFingerprint.compute("  Hello   World  ");
        assertEquals(Digest.sha256Hex("hello world"), fp);
    }
}
