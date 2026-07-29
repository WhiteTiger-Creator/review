package r4.n2;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import w8.z3.JrnGate;

/** Side-route certificate cache under output/side. */
public final class AuthCache {
  private final JrnGate jrn = new JrnGate();

  public HopMap resolve(SlotView slots, int seed, Path side, LaneMux mux, int epoch)
      throws Exception {
    Path cache = side.resolve("hop.cache");
    Files.createDirectories(side);
    jrn.purge(side);
    Files.deleteIfExists(side.resolve("mesh.pin"));
    Map<String, Long> out = new LinkedHashMap<>();
    for (SlotView.Slot s : slots.slots()) {
      out.put(s.id, mux.digestSlot(s.pad, seed, s.arm, epoch));
    }
    save(seed, out, cache);
    return new HopMap(out);
  }

  private static void save(int seed, Map<String, Long> map, Path cache) throws Exception {
    StringBuilder sb = new StringBuilder();
    sb.append("seed=").append(Integer.toUnsignedString(seed)).append('\n');
    for (Map.Entry<String, Long> e : map.entrySet()) {
      sb.append(e.getKey()).append('=').append(Long.toUnsignedString(e.getValue())).append('\n');
    }
    Files.writeString(cache, sb.toString(), StandardCharsets.UTF_8);
  }
}
