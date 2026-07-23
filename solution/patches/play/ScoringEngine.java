package dev.terminus.trivia.play;

import com.fasterxml.jackson.databind.JsonNode;

public final class ScoringEngine {
    private final JsonNode scoring;

    public ScoringEngine(JsonNode scoring) {
        this.scoring = scoring;
    }

    public int scoreEncounter(boolean correct, int difficulty, int streak) {
        int base = scoring.path("base").path("correct_points").asInt(10);
        int wrong = scoring.path("base").path("wrong_points").asInt(0);
        int points = correct ? base : wrong;
        if (correct) {
            double multiplier = 1.0;
            if (scoring.has("difficulty")) {
                JsonNode tiers = scoring.get("difficulty").get("tiers");
                if (tiers != null && tiers.isArray()) {
                    for (JsonNode tier : tiers) {
                        int min = tier.path("min").asInt();
                        if (difficulty >= min) {
                            multiplier = tier.path("multiplier").asDouble(1.0);
                        }
                    }
                }
            }
            points = (int) Math.round(points * multiplier);
            if (scoring.has("streaks")) {
                JsonNode bonuses = scoring.get("streaks").get("bonuses");
                if (bonuses != null && bonuses.isArray()) {
                    for (JsonNode bonus : bonuses) {
                        int threshold = bonus.path("threshold").asInt();
                        if (streak < threshold) {
                            continue;
                        }
                        points += bonus.path("bonus").asInt();
                    }
                }
            }
        }
        return points;
    }
}
