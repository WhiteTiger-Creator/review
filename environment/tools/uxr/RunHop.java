package tools.uxr;

import java.nio.file.Path;
import r4.n2.HopMap;
import r4.n2.LaneMux;
import r4.n2.LaneScan;
import r4.n2.SlotView;

final class RunHop {
  static HopMap go(SlotView slots, int seed, Path side, int epoch) throws Exception {
    new LaneScan().summarize(slots, side.resolve("scan.txt"));
    return new LaneMux().walk(slots, seed, side, epoch);
  }
}
