package dev.emberline.game;

import java.util.Objects;

/**
 * Immutable combatant snapshot for a single turn.
 *
 * @param id         unique unit identifier
 * @param team       owning team
 * @param position   current axial hex
 * @param health     remaining hit points (positive at turn start)
 * @param initiative movement contention priority
 * @param range      axial attack reach
 * @param power      damage dealt by a successful attack
 */
public record Unit(
        String id,
        Team team,
        Hex position,
        int health,
        int initiative,
        int range,
        int power
) {
    public Unit {
        Objects.requireNonNull(id, "id");
        Objects.requireNonNull(team, "team");
        Objects.requireNonNull(position, "position");
    }
}
