package dev.terminus.trivia.dataset;

import java.util.List;
import java.util.Optional;

public record QuestionRecord(
        String questionId,
        String question,
        String answerValue,
        List<String> answerAliases,
        String category,
        int difficulty,
        String sourceSplit
) {}
