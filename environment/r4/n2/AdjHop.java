package r4.n2;

import java.util.HashMap;
import java.util.Map;

/** Open hop adjacency table co-resident with LaneMux. */
public final class AdjHop {
  private final Map<String, String> edges = new HashMap<>();

  public AdjHop() {
    edges.put("1:a0", "a1");
    edges.put("1:a1", "a2");
    edges.put("1:a2", "a0");
    edges.put("2:b0", "b1");
    edges.put("2:b1", "b2");
    edges.put("2:b2", "b0");
    edges.put("3:c0", "c1");
    edges.put("3:c1", "c2");
    edges.put("3:c2", "c0");
    edges.put("4:d0", "d1");
    edges.put("4:d1", "d2");
    edges.put("4:d2", "d3");
    edges.put("4:d3", "d0");
  }

  public String start(int pad) {
    if (pad == 1) {
      return "a0";
    }
    if (pad == 2) {
      return "b0";
    }
    if (pad == 3) {
      return "c0";
    }
    return "d0";
  }

  public String next(int pad, String cur) {
    String k = pad + ":" + cur;
    String n = edges.get(k);
    if (n == null) {
      throw new IllegalStateException("no edge " + k);
    }
    return n;
  }

  /** Hold-arm rotate width published for each pad. */
  public int holdRotate(int pad) {
    if (pad == 1) {
      return 13;
    }
    if (pad == 2) {
      return 19;
    }
    if (pad == 3) {
      return 23;
    }
    return 29;
  }
}
