package dev.emberline.game;

import java.util.List;
import java.util.Objects;

/**
 * Immutable result of resolving one simultaneous turn.
 *
 * @param board  board after movement, combat, hazards, and scoring
 * @param events canonically ordered observable events
 * @param status match status after the turn
 */
public record Resolution(Board board, List<Event> events, GameStatus status) {
    public Resolution {
        Objects.requireNonNull(board, "board");
        Objects.requireNonNull(events, "events");
        Objects.requireNonNull(status, "status");
        events = List.copyOf(events);
    }
}
