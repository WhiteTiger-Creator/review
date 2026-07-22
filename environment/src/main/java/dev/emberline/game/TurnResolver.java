package dev.emberline.game;

import java.util.List;
import java.util.Objects;

/**
 * Library entry point for simultaneous-turn resolution.
 *
 * <p>The starter implementation returns {@link GameStatus#NOT_IMPLEMENTED}.
 * Replace it with the full Emberline rules documented in README.md.
 */
public final class TurnResolver {
    private TurnResolver() {}

    /**
     * Resolve one simultaneous turn.
     *
     * @param board  starting board (not mutated)
     * @param orders exactly one order per unit (list not mutated)
     * @return immutable resolution
     * @throws IllegalArgumentException when the board or orders are invalid
     */
    public static Resolution resolve(Board board, List<Order> orders) {
        Objects.requireNonNull(board, "board");
        Objects.requireNonNull(orders, "orders");
        return new Resolution(board, List.of(), GameStatus.NOT_IMPLEMENTED);
    }
}
