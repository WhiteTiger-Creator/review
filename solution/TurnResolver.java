package dev.emberline.game;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Complete Emberline simultaneous-turn resolver.
 */
public final class TurnResolver {
    private static final Pattern UNIT_ID = Pattern.compile("[A-Za-z0-9][A-Za-z0-9._-]*");

    private TurnResolver() {}

    public static Resolution resolve(Board board, List<Order> orders) {
        Objects.requireNonNull(board, "board");
        Objects.requireNonNull(orders, "orders");

        Validated validated = validate(board, orders);

        List<Event> moveEvents = new ArrayList<>();
        Map<String, Hex> finalPositions = resolveMovement(validated, moveEvents);

        Map<Hex, String> occupancy = new HashMap<>();
        for (Map.Entry<String, Hex> entry : finalPositions.entrySet()) {
            String previous = occupancy.put(entry.getValue(), entry.getKey());
            if (previous != null) {
                throw new IllegalStateException("duplicate occupancy after movement");
            }
        }

        List<Event> attackEvents = new ArrayList<>();
        Map<String, Integer> damage = new HashMap<>();
        resolveAttacks(validated, finalPositions, occupancy, attackEvents, damage);

        for (Map.Entry<String, Hex> entry : finalPositions.entrySet()) {
            Terrain terrain = validated.terrain.get(entry.getValue());
            if (terrain == Terrain.HAZARD) {
                damage.merge(entry.getKey(), 1, Integer::sum);
            }
        }

        List<Event> damageEvents = new ArrayList<>();
        List<Event> defeatEvents = new ArrayList<>();
        Map<String, Integer> remainingHealth = new HashMap<>();
        Set<String> defeated = new HashSet<>();

        for (Unit unit : validated.unitsById.values()) {
            int taken = damage.getOrDefault(unit.id(), 0);
            int health = unit.health() - taken;
            if (taken > 0) {
                damageEvents.add(new Event(
                        EventType.DAMAGE,
                        unit.id(),
                        null,
                        finalPositions.get(unit.id()),
                        taken));
            }
            if (health <= 0) {
                defeated.add(unit.id());
                defeatEvents.add(new Event(EventType.DEFEATED, unit.id(), null, null, 0));
            } else {
                remainingHealth.put(unit.id(), health);
            }
        }
        damageEvents.sort(Comparator.comparing(Event::unitId));
        defeatEvents.sort(Comparator.comparing(Event::unitId));

        int amberScore = validated.amberScore;
        int cobaltScore = validated.cobaltScore;
        List<Event> scoreEvents = new ArrayList<>();
        List<Event> amberScores = new ArrayList<>();
        List<Event> cobaltScores = new ArrayList<>();

        for (String unitId : remainingHealth.keySet().stream().sorted().toList()) {
            Hex pos = finalPositions.get(unitId);
            if (validated.terrain.get(pos) != Terrain.BEACON) {
                continue;
            }
            Unit unit = validated.unitsById.get(unitId);
            Event score = new Event(EventType.SCORE, unitId, null, pos, 1);
            if (unit.team() == Team.AMBER) {
                amberScore += 1;
                amberScores.add(score);
            } else {
                cobaltScore += 1;
                cobaltScores.add(score);
            }
        }
        scoreEvents.addAll(amberScores);
        scoreEvents.addAll(cobaltScores);

        GameStatus status;
        boolean amberWins = amberScore >= validated.scoreToWin;
        boolean cobaltWins = cobaltScore >= validated.scoreToWin;
        if (amberWins && cobaltWins) {
            status = GameStatus.DRAW;
        } else if (amberWins) {
            status = GameStatus.AMBER_WINS;
        } else if (cobaltWins) {
            status = GameStatus.COBALT_WINS;
        } else {
            status = GameStatus.ONGOING;
        }

        List<Unit> resultUnits = new ArrayList<>();
        for (String unitId : remainingHealth.keySet().stream().sorted().toList()) {
            Unit original = validated.unitsById.get(unitId);
            resultUnits.add(new Unit(
                    unitId,
                    original.team(),
                    finalPositions.get(unitId),
                    remainingHealth.get(unitId),
                    original.initiative(),
                    original.range(),
                    original.power()));
        }

        Map<Hex, Terrain> orderedTerrain = new LinkedHashMap<>();
        validated.terrain.entrySet().stream()
                .sorted(Comparator
                        .comparingInt((Map.Entry<Hex, Terrain> e) -> e.getKey().q())
                        .thenComparingInt(e -> e.getKey().r()))
                .forEach(e -> orderedTerrain.put(e.getKey(), e.getValue()));

        List<Event> events = new ArrayList<>();
        events.addAll(moveEvents);
        events.addAll(attackEvents);
        events.addAll(damageEvents);
        events.addAll(defeatEvents);
        events.addAll(scoreEvents);

        Board resultBoard = new Board(
                orderedTerrain,
                resultUnits,
                amberScore,
                cobaltScore,
                validated.scoreToWin);
        return new Resolution(resultBoard, events, status);
    }

    private static Map<String, Hex> resolveMovement(Validated validated, List<Event> moveEvents) {
        Map<Hex, List<String>> contenders = new HashMap<>();
        for (Order order : validated.ordersByUnit.values()) {
            if (order.type() != OrderType.MOVE) {
                continue;
            }
            contenders.computeIfAbsent(order.target(), ignored -> new ArrayList<>()).add(order.unitId());
        }

        Map<String, Hex> retained = new HashMap<>();
        Set<String> rejected = new HashSet<>();
        for (Map.Entry<Hex, List<String>> entry : contenders.entrySet()) {
            List<String> ids = entry.getValue();
            ids.sort(Comparator
                    .comparingInt((String id) -> validated.unitsById.get(id).initiative()).reversed()
                    .thenComparing(id -> id));
            String winner = ids.get(0);
            retained.put(winner, entry.getKey());
            for (int i = 1; i < ids.size(); i++) {
                rejected.add(ids.get(i));
            }
        }

        Map<String, Boolean> success = new HashMap<>();
        Set<String> visiting = new HashSet<>();
        for (String mover : retained.keySet()) {
            determineSuccess(mover, retained, validated.occupancy, success, visiting);
        }

        Map<String, Hex> finalPositions = new HashMap<>();
        for (Unit unit : validated.unitsById.values()) {
            finalPositions.put(unit.id(), unit.position());
        }

        List<Event> events = new ArrayList<>();
        for (String unitId : rejected.stream().sorted().toList()) {
            Hex dest = validated.ordersByUnit.get(unitId).target();
            events.add(new Event(EventType.MOVE_BLOCKED, unitId, null, dest, 0));
        }
        for (String unitId : retained.keySet().stream().sorted().toList()) {
            Hex dest = retained.get(unitId);
            if (Boolean.TRUE.equals(success.get(unitId))) {
                finalPositions.put(unitId, dest);
                events.add(new Event(EventType.MOVE, unitId, null, dest, 0));
            } else {
                events.add(new Event(EventType.MOVE_BLOCKED, unitId, null, dest, 0));
            }
        }
        events.sort(Comparator.comparing(Event::unitId));
        moveEvents.addAll(events);
        return finalPositions;
    }

    private static boolean determineSuccess(
            String mover,
            Map<String, Hex> retained,
            Map<Hex, String> occupancy,
            Map<String, Boolean> success,
            Set<String> visiting) {
        if (success.containsKey(mover)) {
            return success.get(mover);
        }
        if (!visiting.add(mover)) {
            // Closed cycle of retained movers succeeds.
            return true;
        }
        Hex dest = retained.get(mover);
        String occupant = occupancy.get(dest);
        boolean ok;
        if (occupant == null) {
            ok = true;
        } else if (!retained.containsKey(occupant)) {
            ok = false;
        } else if (occupant.equals(mover)) {
            ok = true;
        } else {
            ok = determineSuccess(occupant, retained, occupancy, success, visiting);
        }
        visiting.remove(mover);
        success.put(mover, ok);
        return ok;
    }

    private static void resolveAttacks(
            Validated validated,
            Map<String, Hex> finalPositions,
            Map<Hex, String> occupancy,
            List<Event> attackEvents,
            Map<String, Integer> damage) {
        List<Event> events = new ArrayList<>();
        for (String unitId : validated.unitsById.keySet().stream().sorted().toList()) {
            Order order = validated.ordersByUnit.get(unitId);
            if (order.type() != OrderType.ATTACK) {
                continue;
            }
            Unit attacker = validated.unitsById.get(unitId);
            Hex target = order.target();
            String defenderId = occupancy.get(target);
            if (defenderId == null) {
                events.add(new Event(EventType.ATTACK_MISS, unitId, null, target, 0));
                continue;
            }
            Unit defender = validated.unitsById.get(defenderId);
            if (defender.team() == attacker.team()) {
                events.add(new Event(EventType.ATTACK_MISS, unitId, null, target, 0));
            } else {
                events.add(new Event(
                        EventType.ATTACK_HIT,
                        unitId,
                        defenderId,
                        target,
                        attacker.power()));
                damage.merge(defenderId, attacker.power(), Integer::sum);
            }
        }
        events.sort(Comparator.comparing(Event::unitId));
        attackEvents.addAll(events);
    }

    private static Validated validate(Board board, List<Order> orders) {
        Map<Hex, Terrain> terrain = board.terrain();
        if (terrain.isEmpty()) {
            throw new IllegalArgumentException("terrain must be non-empty");
        }
        for (Map.Entry<Hex, Terrain> entry : terrain.entrySet()) {
            if (entry.getKey() == null || entry.getValue() == null) {
                throw new IllegalArgumentException("terrain entries must be non-null");
            }
        }
        if (board.scoreToWin() <= 0) {
            throw new IllegalArgumentException("scoreToWin must be positive");
        }
        if (board.amberScore() < 0 || board.cobaltScore() < 0) {
            throw new IllegalArgumentException("scores must be non-negative");
        }
        if (board.amberScore() >= board.scoreToWin() || board.cobaltScore() >= board.scoreToWin()) {
            throw new IllegalArgumentException("scores must be strictly below scoreToWin");
        }

        Map<String, Unit> unitsById = new LinkedHashMap<>();
        Map<Hex, String> occupancy = new HashMap<>();
        for (Unit unit : board.units()) {
            if (unit == null) {
                throw new IllegalArgumentException("units must be non-null");
            }
            if (!UNIT_ID.matcher(unit.id()).matches()) {
                throw new IllegalArgumentException("invalid unit id: " + unit.id());
            }
            if (unitsById.containsKey(unit.id())) {
                throw new IllegalArgumentException("duplicate unit id: " + unit.id());
            }
            if (unit.health() <= 0) {
                throw new IllegalArgumentException("health must be positive");
            }
            if (unit.initiative() < 0 || unit.range() < 0 || unit.power() < 0) {
                throw new IllegalArgumentException("initiative, range, and power must be non-negative");
            }
            Terrain cell = terrain.get(unit.position());
            if (cell == null) {
                throw new IllegalArgumentException("unit off board: " + unit.id());
            }
            if (cell == Terrain.WALL) {
                throw new IllegalArgumentException("unit on wall: " + unit.id());
            }
            if (occupancy.put(unit.position(), unit.id()) != null) {
                throw new IllegalArgumentException("duplicate unit position: " + unit.position());
            }
            unitsById.put(unit.id(), unit);
        }

        if (orders.size() != unitsById.size()) {
            throw new IllegalArgumentException("exactly one order per unit required");
        }
        Map<String, Order> ordersByUnit = new LinkedHashMap<>();
        for (Order order : orders) {
            if (order == null) {
                throw new IllegalArgumentException("orders must be non-null");
            }
            if (!unitsById.containsKey(order.unitId())) {
                throw new IllegalArgumentException("unknown order unit: " + order.unitId());
            }
            if (ordersByUnit.containsKey(order.unitId())) {
                throw new IllegalArgumentException("duplicate order for unit: " + order.unitId());
            }
            validateOrder(order, unitsById.get(order.unitId()), terrain);
            ordersByUnit.put(order.unitId(), order);
        }

        return new Validated(
                Map.copyOf(terrain),
                Map.copyOf(unitsById),
                Map.copyOf(occupancy),
                Map.copyOf(ordersByUnit),
                board.amberScore(),
                board.cobaltScore(),
                board.scoreToWin());
    }

    private static void validateOrder(Order order, Unit unit, Map<Hex, Terrain> terrain) {
        switch (order.type()) {
            case HOLD -> {
                if (order.target() != null) {
                    throw new IllegalArgumentException("HOLD requires null target");
                }
            }
            case MOVE -> {
                Hex target = order.target();
                if (target == null) {
                    throw new IllegalArgumentException("MOVE requires target");
                }
                Terrain cell = terrain.get(target);
                if (cell == null || cell == Terrain.WALL) {
                    throw new IllegalArgumentException("MOVE target not playable");
                }
                if (axialDistance(unit.position(), target) != 1) {
                    throw new IllegalArgumentException("MOVE target not adjacent");
                }
            }
            case ATTACK -> {
                Hex target = order.target();
                if (target == null) {
                    throw new IllegalArgumentException("ATTACK requires target");
                }
                Terrain cell = terrain.get(target);
                if (cell == null || cell == Terrain.WALL) {
                    throw new IllegalArgumentException("ATTACK target not playable");
                }
                if (axialDistance(unit.position(), target) > unit.range()) {
                    throw new IllegalArgumentException("ATTACK out of range");
                }
            }
        }
    }

    private static int axialDistance(Hex a, Hex b) {
        int dq = a.q() - b.q();
        int dr = a.r() - b.r();
        return (Math.abs(dq) + Math.abs(dr) + Math.abs(dq + dr)) / 2;
    }

    private record Validated(
            Map<Hex, Terrain> terrain,
            Map<String, Unit> unitsById,
            Map<Hex, String> occupancy,
            Map<String, Order> ordersByUnit,
            int amberScore,
            int cobaltScore,
            int scoreToWin
    ) {}
}
