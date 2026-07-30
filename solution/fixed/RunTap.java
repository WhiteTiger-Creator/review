package tools.uxr;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import p7.u3.VecRow;
import r4.n2.HopMap;
import v5.h1.BoundDump;
import v5.h1.BoundTap;
import v5.h1.EnvPack;

final class RunTap {
  private static final long ENV_HI = 0x7fffffffffffffffL;

  static List<Long> go(HopMap hops, List<VecRow> rows, Path side, int epoch) throws Exception {
    new BoundDump().csv(side.resolve("dump.csv"), rows);
    Files.deleteIfExists(side.resolve("span.soft"));
    BoundTap tap = new BoundTap();
    EnvPack env = new EnvPack(0L, ENV_HI);
    List<Long> spans = new ArrayList<>();
    for (VecRow row : rows) {
      spans.add(tap.span(hops, row, env, epoch));
    }
    return spans;
  }
}
