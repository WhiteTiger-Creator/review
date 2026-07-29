package r4.n2;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/** Walks open hops on packed slots and emits hop maps. */
public final class LaneMux {
  private final AdjHop table = new AdjHop();

  public HopMap walk(SlotView slots, int seed, Path side, int epoch) throws Exception {
    return new AuthCache().resolve(slots, seed, side, this, epoch);
  }

  /** Per-slot digest used by the side-cache resolver. */
  public long digestSlot(int pad, int seed, int arm, int epoch) {
    int walkSeed = seed;
    if (arm != 0) {
      walkSeed = seed ^ (((epoch + (pad * 3)) ^ (pad << 2)) & 0xff);
    }
    String cur = table.start(pad);
    String start = cur;
    long h = ((long) walkSeed) ^ (((long) pad) * 0xC2B2AE3DL);
    List<String> chain = new ArrayList<>();
    chain.add(cur);
    h = mixLabel(h, cur);
    do {
      cur = table.next(pad, cur);
      chain.add(cur);
      h = mixLabel(h, cur);
    } while (!cur.equals(start));
    long check = ((long) walkSeed) ^ (((long) pad) * 0xC2B2AE3DL);
    for (String lab : chain) {
      check = mixLabel(check, lab);
    }
    if (check != h) {
      throw new IllegalStateException("mix");
    }
    return h;
  }

  private static long mixLabel(long h, String lab) {
    for (int i = 0; i < lab.length(); i++) {
      h ^= lab.charAt(i);
      h = (h * 0x100000001B3L);
    }
    return h;
  }
}
