package dev.emberline.game;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/**
 * Immutable board snapshot at the start of a turn.
 *
 * @param terrain     every playable hex and its terrain
 * @param units       units present on the board
 * @param amberScore  Amber team score (strictly below scoreToWin)
 * @param cobaltScore Cobalt team score (strictly below scoreToWin)
 * @param scoreToWin  positive victory threshold
 */
public record Board(
        Map<Hex, Terrain> terrain,
        List<Unit> units,
        int amberScore,
        int cobaltScore,
        int scoreToWin
) {
    public Board {
        Objects.requireNonNull(terrain, "terrain");
        Objects.requireNonNull(units, "units");
        // Preserve caller iteration order (canonical q then r from the resolver).
        terrain = Collections.unmodifiableMap(new LinkedHashMap<>(terrain));
        units = List.copyOf(units);
    }
}
