package dev.emberline.game;

import java.util.Objects;

/**
 * Per-unit order for one simultaneous turn.
 *
 * @param unitId acting unit id
 * @param type   HOLD, MOVE, or ATTACK
 * @param target null for HOLD; destination or attack hex otherwise
 */
public record Order(String unitId, OrderType type, Hex target) {
    public Order {
        Objects.requireNonNull(unitId, "unitId");
        Objects.requireNonNull(type, "type");
    }
}
