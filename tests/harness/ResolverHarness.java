import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import dev.emberline.game.Board;
import dev.emberline.game.Event;
import dev.emberline.game.Hex;
import dev.emberline.game.Order;
import dev.emberline.game.OrderType;
import dev.emberline.game.Resolution;
import dev.emberline.game.Team;
import dev.emberline.game.Terrain;
import dev.emberline.game.TurnResolver;
import dev.emberline.game.Unit;

/**
 * Verifier harness: compact line protocol around the public Emberline API.
 *
 * <pre>
 * BOARD
 * T q r TERRAIN
 * U id TEAM q r health initiative range power
 * S amber cobalt scoreToWin
 * END
 * ORDERS
 * O unitId TYPE [q r]
 * END
 * RESOLVE
 * </pre>
 *
 * Output lines start with OK or ERROR.
 */
public final class ResolverHarness {
    private ResolverHarness() {}

    public static void main(String[] args) throws Exception {
        BufferedReader reader = new BufferedReader(
                new InputStreamReader(System.in, StandardCharsets.UTF_8));
        Map<Hex, Terrain> terrain = new LinkedHashMap<>();
        List<Unit> units = new ArrayList<>();
        List<Order> orders = new ArrayList<>();
        int amber = 0;
        int cobalt = 0;
        int scoreToWin = 1;
        String section = null;
        String line;
        while ((line = reader.readLine()) != null) {
            line = line.trim();
            if (line.isEmpty() || line.startsWith("#")) {
                continue;
            }
            switch (line) {
                case "BOARD" -> {
                    section = "BOARD";
                    terrain.clear();
                    units.clear();
                }
                case "ORDERS" -> {
                    section = "ORDERS";
                    orders.clear();
                }
                case "END" -> section = null;
                case "RESOLVE" -> {
                    try {
                        Map<Hex, Terrain> terrainCopy = new LinkedHashMap<>(terrain);
                        List<Unit> unitsCopy = new ArrayList<>(units);
                        List<Order> ordersCopy = new ArrayList<>(orders);
                        int terrainSize = terrainCopy.size();
                        int unitsSize = unitsCopy.size();
                        int ordersSize = ordersCopy.size();
                        Board boardCopy = new Board(terrainCopy, unitsCopy, amber, cobalt, scoreToWin);
                        Resolution resolution = TurnResolver.resolve(boardCopy, ordersCopy);
                        boolean inputsUntouched = terrainCopy.size() == terrainSize
                                && unitsCopy.size() == unitsSize
                                && ordersCopy.size() == ordersSize
                                && ordersCopy.equals(List.copyOf(orders));
                        writeOk(resolution, inputsUntouched);
                    } catch (IllegalArgumentException ex) {
                        System.out.println("ERROR IllegalArgumentException " + sanitize(ex.getMessage()));
                    } catch (Throwable ex) {
                        System.out.println("ERROR " + ex.getClass().getSimpleName() + " " + sanitize(ex.getMessage()));
                    }
                }
                default -> {
                    if (section == null) {
                        throw new IllegalArgumentException("command outside section: " + line);
                    }
                    String[] parts = line.split("\\s+");
                    if ("BOARD".equals(section)) {
                        parseBoardLine(parts, terrain, units);
                        if (parts[0].equals("S")) {
                            amber = Integer.parseInt(parts[1]);
                            cobalt = Integer.parseInt(parts[2]);
                            scoreToWin = Integer.parseInt(parts[3]);
                        }
                    } else if ("ORDERS".equals(section)) {
                        orders.add(parseOrder(parts));
                    }
                }
            }
        }
    }

    private static void parseBoardLine(
            String[] parts,
            Map<Hex, Terrain> terrain,
            List<Unit> units) {
        switch (parts[0]) {
            case "T" -> terrain.put(
                    new Hex(Integer.parseInt(parts[1]), Integer.parseInt(parts[2])),
                    Terrain.valueOf(parts[3]));
            case "U" -> units.add(new Unit(
                    parts[1],
                    Team.valueOf(parts[2]),
                    new Hex(Integer.parseInt(parts[3]), Integer.parseInt(parts[4])),
                    Integer.parseInt(parts[5]),
                    Integer.parseInt(parts[6]),
                    Integer.parseInt(parts[7]),
                    Integer.parseInt(parts[8])));
            case "S" -> {
                // handled by caller
            }
            default -> throw new IllegalArgumentException("bad board line");
        }
    }

    private static Order parseOrder(String[] parts) {
        if (!parts[0].equals("O")) {
            throw new IllegalArgumentException("bad order line");
        }
        OrderType type = OrderType.valueOf(parts[2]);
        Hex target = null;
        if (type == OrderType.HOLD) {
            // Optional q r after HOLD creates an intentionally invalid non-null target.
            if (parts.length >= 5) {
                target = new Hex(Integer.parseInt(parts[3]), Integer.parseInt(parts[4]));
            }
        } else {
            target = new Hex(Integer.parseInt(parts[3]), Integer.parseInt(parts[4]));
        }
        return new Order(parts[1], type, target);
    }

    private static void writeOk(Resolution resolution, boolean inputsUntouched) {
        System.out.println("OK");
        System.out.println("STATUS " + resolution.status().name());
        System.out.println("SCORES "
                + resolution.board().amberScore() + " "
                + resolution.board().cobaltScore() + " "
                + resolution.board().scoreToWin());
        System.out.println("INPUTS_UNTOUCHED " + inputsUntouched);
        // Probe returned collection mutability.
        boolean eventsImmutable;
        try {
            resolution.events().add(resolution.events().isEmpty()
                    ? null
                    : resolution.events().get(0));
            eventsImmutable = false;
        } catch (UnsupportedOperationException ex) {
            eventsImmutable = true;
        } catch (NullPointerException | IllegalArgumentException ex) {
            eventsImmutable = false;
        }
        boolean unitsImmutable;
        try {
            resolution.board().units().add(resolution.board().units().isEmpty()
                    ? null
                    : resolution.board().units().get(0));
            unitsImmutable = false;
        } catch (UnsupportedOperationException ex) {
            unitsImmutable = true;
        } catch (NullPointerException | IllegalArgumentException ex) {
            unitsImmutable = false;
        }
        boolean terrainImmutable;
        try {
            resolution.board().terrain().clear();
            terrainImmutable = false;
        } catch (UnsupportedOperationException ex) {
            terrainImmutable = true;
        }
        System.out.println("IMMUTABLE " + eventsImmutable + " " + unitsImmutable + " " + terrainImmutable);
        for (Unit unit : resolution.board().units()) {
            System.out.println("UNIT "
                    + unit.id() + " "
                    + unit.team().name() + " "
                    + unit.position().q() + " "
                    + unit.position().r() + " "
                    + unit.health() + " "
                    + unit.initiative() + " "
                    + unit.range() + " "
                    + unit.power());
        }
        for (Map.Entry<Hex, Terrain> entry : resolution.board().terrain().entrySet()) {
            System.out.println("TERRAIN "
                    + entry.getKey().q() + " "
                    + entry.getKey().r() + " "
                    + entry.getValue().name());
        }
        for (Event event : resolution.events()) {
            String related = event.relatedUnitId() == null ? "-" : event.relatedUnitId();
            String at = event.at() == null
                    ? "- -"
                    : (event.at().q() + " " + event.at().r());
            System.out.println("EVENT "
                    + event.type().name() + " "
                    + event.unitId() + " "
                    + related + " "
                    + at + " "
                    + event.amount());
        }
        System.out.println("END");
    }

    private static String sanitize(String message) {
        if (message == null) {
            return "";
        }
        return message.replace('\n', ' ').replace('\r', ' ');
    }
}
