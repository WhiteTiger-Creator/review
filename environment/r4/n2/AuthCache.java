package r4.n2;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import w8.z3.JrnGate;

/** Side-route certificate cache under output/side. */
public final class AuthCache {
  private final AdjHop table = new AdjHop();
  private final JrnGate jrn = new JrnGate();

  public HopMap resolve(SlotView slots, int seed, Path side, LaneMux mux, int epoch)
      throws Exception {
    Path cache = side.resolve("hop.cache");
    Files.createDirectories(side);
    jrn.purge(side);
    writeShortWalk(slots, seed, cache);
    long pin = 0L;
    for (SlotView.Slot s : slots.slots()) {
      pin ^= shortDigest(s.pad, seed);
    }
    Files.writeString(side.resolve("mesh.pin"), Long.toUnsignedString(pin), StandardCharsets.UTF_8);
    if (Files.exists(cache)) {
      return load(cache);
    }
    Map<String, Long> out = new LinkedHashMap<>();
    for (SlotView.Slot s : slots.slots()) {
      out.put(s.id, mux.digestSlot(s.pad, seed, s.arm, epoch));
    }
    return new HopMap(out);
  }

  private void writeShortWalk(SlotView slots, int seed, Path cache) throws Exception {
    Map<String, Long> out = new LinkedHashMap<>();
    for (SlotView.Slot s : slots.slots()) {
      out.put(s.id, shortDigest(s.pad, seed));
    }
    save(out, cache);
  }

  private long shortDigest(int pad, int seed) {
    String cur = table.start(pad);
    long h = ((long) seed) ^ (((long) pad) * 0xC2B2AE3DL);
    h = mixLabel(h, cur);
    cur = table.next(pad, cur);
    h = mixLabel(h, cur);
    return h;
  }

  private static long mixLabel(long h, String lab) {
    for (int i = 0; i < lab.length(); i++) {
      h ^= lab.charAt(i);
      h = (h * 0x100000001B3L);
    }
    return h;
  }

  private static void save(Map<String, Long> map, Path cache) throws Exception {
    StringBuilder sb = new StringBuilder();
    for (Map.Entry<String, Long> e : map.entrySet()) {
      sb.append(e.getKey()).append('=').append(Long.toUnsignedString(e.getValue())).append('\n');
    }
    Files.writeString(cache, sb.toString(), StandardCharsets.UTF_8);
  }

  private static HopMap load(Path cache) throws Exception {
    Map<String, Long> out = new LinkedHashMap<>();
    for (String line : Files.readAllLines(cache, StandardCharsets.UTF_8)) {
      if (line.isBlank() || !line.contains("=")) {
        continue;
      }
      int ix = line.indexOf('=');
      out.put(line.substring(0, ix), Long.parseUnsignedLong(line.substring(ix + 1)));
    }
    return new HopMap(out);
  }
}
