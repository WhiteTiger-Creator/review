package dev.terminus.trivia.registry;

import dev.terminus.trivia.dataset.QuestionRecord;

public record EncounterNode(
        String id,
        String roomId,
        String title,
        QuestionRecord question
) {}
