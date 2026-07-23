package dev.terminus.trivia;

import com.fasterxml.jackson.databind.ObjectMapper;
import dev.terminus.trivia.play.ScoringEngine;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ScoringEngineTest {
    @Test
    void correctAnswerEarnsBasePoints() throws Exception {
        var scoring = new ObjectMapper().readTree("""
                {
                  "base": {"correct_points": 10, "wrong_points": -2},
                  "difficulty": {"tiers": [{"min": 1, "multiplier": 1.0}]},
                  "streaks": {"bonuses": [{"threshold": 3, "bonus": 5}]}
                }
                """);
        ScoringEngine engine = new ScoringEngine(scoring);
        assertEquals(10, engine.scoreEncounter(true, 1, 1));
    }

    @Test
    void streakBonusAboveThreshold() throws Exception {
        var scoring = new ObjectMapper().readTree("""
                {
                  "base": {"correct_points": 10, "wrong_points": 0},
                  "streaks": {"bonuses": [{"threshold": 2, "bonus": 5}]}
                }
                """);
        ScoringEngine engine = new ScoringEngine(scoring);
        assertEquals(15, engine.scoreEncounter(true, 1, 3));
    }
}
