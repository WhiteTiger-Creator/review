package n3p;

import java.util.HashMap;
import java.util.Map;

public final class SideAux {
    private static final Map<String, Integer> HIST = new HashMap<>();

    private SideAux() {}

    public static void note(String key, int value) {
        HIST.put(key, value);
    }

    public static int lookup(String key) {
        return HIST.getOrDefault(key, -1);
    }
}
