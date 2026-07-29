package r4.n2;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/** Slot digests keyed by row id. */
public final class HopMap {
  private final Map<String, Long> m;

  public HopMap(Map<String, Long> src) {
    this.m = Collections.unmodifiableMap(new LinkedHashMap<>(src));
  }

  public long get(String id) {
    Long v = m.get(id);
    if (v == null) {
      throw new IllegalArgumentException("missing " + id);
    }
    return v;
  }

  public Map<String, Long> all() {
    return m;
  }
}
