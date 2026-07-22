package dev.emberline.game;

import java.util.Objects;

/**
 * One observable effect produced while resolving a turn.
 *
 * @param type          event kind
 * @param unitId        primary acting or affected unit
 * @param relatedUnitId secondary unit when applicable, else null
 * @param at            relevant hex when applicable, else null
 * @param amount        damage, score, or zero as documented
 */
public record Event(
        EventType type,
        String unitId,
        String relatedUnitId,
        Hex at,
        int amount
) {
    public Event {
        Objects.requireNonNull(type, "type");
        Objects.requireNonNull(unitId, "unitId");
    }
}
