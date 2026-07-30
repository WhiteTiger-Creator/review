package tools.uxr;

import java.nio.charset.StandardCharsets;
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
    BoundTap tap = new BoundTap();
    EnvPack env = new EnvPack(0L, ENV_HI);
    Path soft = side.resolve("span.soft");
    boolean softHold = Files.isRegularFile(soft);
    List<Long> spans = new ArrayList<>();
    for (VecRow row : rows) {
      if (row.arm != 0 && softHold) {
        long width = ((long) row.hi - (long) row.lo) & 0xffffffffL;
        spans.add(width);
      } else {
        spans.add(tap.span(hops, row, env, epoch));
      }
    }
    Files.writeString(soft, "1", StandardCharsets.UTF_8);
    return spans;
  }
}
